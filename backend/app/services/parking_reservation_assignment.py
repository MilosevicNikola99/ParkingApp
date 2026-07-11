from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sqlalchemy.exc import IntegrityError

from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog, ParkingAssignmentTriggerSource
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_reservation import ParkingReservation
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.services.parking_application_ranking import (
    ParkingApplicationRankingAuditDetail,
    ParkingApplicationRankingService,
)


class ParkingReservationAssignmentServiceError(Exception):
    """Base class for reservation assignment business-rule failures."""


class ParkingReservationAssignmentAvailabilityNotFoundError(ParkingReservationAssignmentServiceError):
    pass


class ParkingReservationAssignmentAvailabilityNotOpenError(ParkingReservationAssignmentServiceError):
    pass


class ParkingReservationAssignmentNoPendingApplicationsError(ParkingReservationAssignmentServiceError):
    pass


class ParkingReservationAssignmentReservationExistsError(ParkingReservationAssignmentServiceError):
    pass


class ParkingReservationAssignmentIntegrityError(ParkingReservationAssignmentServiceError):
    pass


class ParkingReservationAssignmentAuditPersistenceError(ParkingReservationAssignmentServiceError):
    pass


class ParkingReservationAssignmentMethod(str, Enum):
    AUTOMATIC = "automatic"


@dataclass(frozen=True)
class ParkingReservationAssignmentAuditDetails:
    assignment_method: ParkingReservationAssignmentMethod
    selected_application_id: int
    rejected_application_ids: tuple[int, ...]
    candidate_rankings: tuple[ParkingApplicationRankingAuditDetail, ...]


@dataclass(frozen=True)
class ParkingReservationAssignmentResult:
    reservation: ParkingReservation
    audit_log: ParkingAssignmentAuditLog
    selected_application: ParkingApplication
    rejected_applications: list[ParkingApplication]
    availability: ParkingAvailability
    audit_details: ParkingReservationAssignmentAuditDetails


class ParkingReservationAssignmentService:
    RANKING_POLICY = "same_team_soft_limit_recent_wins_v1"

    def __init__(
        self,
        availability_repository: ParkingAvailabilityRepository,
        application_repository: ParkingApplicationRepository,
        reservation_repository: ParkingReservationRepository,
        ranking_service: ParkingApplicationRankingService | None = None,
        audit_log_repository: ParkingAssignmentAuditLogRepository | None = None,
    ) -> None:
        self.availability_repository = availability_repository
        self.application_repository = application_repository
        self.reservation_repository = reservation_repository
        self.ranking_service = ranking_service or ParkingApplicationRankingService(
            recent_win_count_provider=reservation_repository.count_recent_wins_by_user_ids,
        )
        self.audit_log_repository = audit_log_repository or ParkingAssignmentAuditLogRepository(reservation_repository.db)

    def assign_availability(
        self,
        availability_id: int,
        *,
        trigger_source: ParkingAssignmentTriggerSource = ParkingAssignmentTriggerSource.SYSTEM,
    ) -> ParkingReservationAssignmentResult:
        """Assign the highest-ranked pending application for an open availability."""
        availability = self.availability_repository.get_by_id_for_update(availability_id)
        if availability is None:
            raise ParkingReservationAssignmentAvailabilityNotFoundError()
        if availability.status is not ParkingAvailabilityStatus.OPEN:
            raise ParkingReservationAssignmentAvailabilityNotOpenError()

        existing_reservation = self.reservation_repository.get_by_availability_id(availability.id)
        if existing_reservation is not None:
            raise ParkingReservationAssignmentReservationExistsError()

        pending_applications = self.application_repository.list_pending_by_availability_id_for_update(availability.id)
        if not pending_applications:
            raise ParkingReservationAssignmentNoPendingApplicationsError()

        ranking_result = self.ranking_service.rank_applications_with_audit(availability, pending_applications)
        selected_application = ranking_result.selected_application
        applications_to_reject = [
            application for application in pending_applications if application.id != selected_application.id
        ]

        try:
            reservation = self.reservation_repository.create(
                availability_id=availability.id,
                application_id=selected_application.id,
                parking_spot_id=availability.parking_spot_id,
                reserved_for_user_id=selected_application.applicant_id,
                start_at=availability.start_at,
                end_at=availability.end_at,
            )
            selected_application = self.application_repository.update(
                selected_application,
                {"status": ParkingApplicationStatus.SELECTED},
            )
            rejected_applications: list[ParkingApplication] = []
            for application in applications_to_reject:
                rejected_applications.append(
                    self.application_repository.update(application, {"status": ParkingApplicationStatus.REJECTED}),
                )
            availability = self.availability_repository.update(
                availability,
                {"status": ParkingAvailabilityStatus.ASSIGNED},
            )
            try:
                audit_log = self.audit_log_repository.create(
                    availability_id=availability.id,
                    reservation_id=reservation.id,
                    selected_application_id=selected_application.id,
                    selected_user_id=selected_application.applicant_id,
                    rejected_application_ids=[application.id for application in rejected_applications],
                    ranking_policy=self.RANKING_POLICY,
                    ranking_details=self._serialize_ranking_details(ranking_result.audit_details),
                    trigger_source=trigger_source,
                )
            except IntegrityError:
                raise
            except Exception as exc:
                self.reservation_repository.db.rollback()
                raise ParkingReservationAssignmentAuditPersistenceError() from exc
        except IntegrityError as exc:
            self.reservation_repository.db.rollback()
            if self.reservation_repository.get_active_by_availability_id(availability_id) is not None:
                raise ParkingReservationAssignmentReservationExistsError() from exc

            raise ParkingReservationAssignmentIntegrityError() from exc

        return ParkingReservationAssignmentResult(
            reservation=reservation,
            audit_log=audit_log,
            selected_application=selected_application,
            rejected_applications=rejected_applications,
            availability=availability,
            audit_details=ParkingReservationAssignmentAuditDetails(
                assignment_method=ParkingReservationAssignmentMethod.AUTOMATIC,
                selected_application_id=selected_application.id,
                rejected_application_ids=tuple(application.id for application in rejected_applications),
                candidate_rankings=ranking_result.audit_details,
            ),
        )

    def _serialize_ranking_details(
        self,
        details: tuple[ParkingApplicationRankingAuditDetail, ...],
    ) -> list[dict[str, object]]:
        return [
            {
                "application_id": detail.application_id,
                "applicant_id": detail.applicant_id,
                "applicant_team_id": detail.applicant_team_id,
                "owner_team_id": detail.owner_team_id,
                "is_same_team_as_owner": detail.is_same_team_as_owner,
                "team_priority_active": detail.team_priority_active,
                "recent_win_count": detail.recent_win_count,
                "is_over_soft_limit": detail.is_over_soft_limit,
                "application_created_at": detail.application_created_at.isoformat(),
                "ranking_order_values": [
                    value.isoformat() if isinstance(value, datetime) else value
                    for value in detail.ranking_order_values
                ],
                "final_rank_position": detail.final_rank_position,
                "selected": detail.selected,
            }
            for detail in details
        ]

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog, ParkingAssignmentTriggerSource
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.models.user import UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.users import UserRepository
from app.services.parking_application_ranking import (
    ParkingApplicationRankingAuditDetail,
    ParkingApplicationRankingService,
)


class ParkingReassignmentServiceError(Exception):
    """Base class for explicit reassignment failures."""


class ParkingReassignmentAvailabilityNotFoundError(ParkingReassignmentServiceError):
    pass


class ParkingReassignmentPermissionError(ParkingReassignmentServiceError):
    pass


class ParkingReassignmentAvailabilityNotOpenError(ParkingReassignmentServiceError):
    pass


class ParkingReassignmentAvailabilityExpiredError(ParkingReassignmentServiceError):
    pass


class ParkingReassignmentActiveReservationExistsError(ParkingReassignmentServiceError):
    pass


class ParkingReassignmentCancelledReservationNotFoundError(ParkingReassignmentServiceError):
    pass


class ParkingReassignmentNoPendingApplicationsError(ParkingReassignmentServiceError):
    pass


class ParkingReassignmentIntegrityError(ParkingReassignmentServiceError):
    pass


class ParkingReassignmentAuditPersistenceError(ParkingReassignmentServiceError):
    pass


@dataclass(frozen=True)
class ParkingReassignmentResult:
    reservation: ParkingReservation
    previous_reservation: ParkingReservation
    audit_log: ParkingAssignmentAuditLog
    selected_application: ParkingApplication
    rejected_applications: list[ParkingApplication]
    availability: ParkingAvailability


class ParkingReassignmentService:
    RANKING_POLICY = "reassignment_same_team_soft_limit_recent_wins_v1"
    ALLOWED_TRIGGER_SOURCES = {
        ParkingAssignmentTriggerSource.MANUAL_OWNER,
        ParkingAssignmentTriggerSource.MANUAL_ADMIN,
        ParkingAssignmentTriggerSource.SCHEDULED,
    }

    def __init__(
        self,
        availability_repository: ParkingAvailabilityRepository,
        application_repository: ParkingApplicationRepository,
        reservation_repository: ParkingReservationRepository,
        audit_log_repository: ParkingAssignmentAuditLogRepository | None = None,
        user_repository: UserRepository | None = None,
        ranking_service: ParkingApplicationRankingService | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.availability_repository = availability_repository
        self.application_repository = application_repository
        self.reservation_repository = reservation_repository
        self.audit_log_repository = audit_log_repository or ParkingAssignmentAuditLogRepository(reservation_repository.db)
        self.user_repository = user_repository or UserRepository(reservation_repository.db)
        self.ranking_service = ranking_service or ParkingApplicationRankingService(
            recent_win_count_provider=reservation_repository.count_recent_wins_by_user_ids,
        )
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    def reassign_open_availability(
        self,
        availability_id: int,
        *,
        trigger_source: ParkingAssignmentTriggerSource,
        actor_user_id: int | None = None,
        reason: str | None = None,
    ) -> ParkingReassignmentResult:
        if trigger_source not in self.ALLOWED_TRIGGER_SOURCES:
            raise ParkingReassignmentPermissionError()

        availability = self.availability_repository.get_by_id_for_update(availability_id)
        if availability is None:
            raise ParkingReassignmentAvailabilityNotFoundError()

        self._validate_actor(availability, trigger_source, actor_user_id)
        if availability.status is not ParkingAvailabilityStatus.OPEN:
            raise ParkingReassignmentAvailabilityNotOpenError()
        if self._as_aware_utc(availability.end_at) <= self._now():
            raise ParkingReassignmentAvailabilityExpiredError()

        if self.reservation_repository.get_active_by_availability_id_for_update(availability.id) is not None:
            raise ParkingReassignmentActiveReservationExistsError()

        previous_reservation = self.reservation_repository.get_by_availability_id_for_update(availability.id)
        if previous_reservation is None or previous_reservation.status is not ParkingReservationStatus.CANCELLED:
            raise ParkingReassignmentCancelledReservationNotFoundError()

        pending_applications = self.application_repository.list_pending_by_availability_id_for_update(availability.id)
        if not pending_applications:
            raise ParkingReassignmentNoPendingApplicationsError()

        ranking_result = self.ranking_service.rank_applications_with_audit(availability, pending_applications)
        selected_application = ranking_result.selected_application
        applications_to_reject = [
            application for application in pending_applications if application.id != selected_application.id
        ]
        normalized_reason = self._normalize_optional_reason(reason)

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
            rejected_applications = [
                self.application_repository.update(
                    application,
                    {"status": ParkingApplicationStatus.REJECTED},
                )
                for application in applications_to_reject
            ]
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
                    ranking_details=[
                        {
                            "action": "reassignment",
                            "actor_user_id": actor_user_id,
                            "reason": normalized_reason,
                            "previous_reservation_id": previous_reservation.id,
                            "previous_application_id": previous_reservation.application_id,
                            "previous_user_id": previous_reservation.reserved_for_user_id,
                            "selected_application_id": selected_application.id,
                            "selected_user_id": selected_application.applicant_id,
                            "rejected_application_ids": [
                                application.id for application in rejected_applications
                            ],
                        },
                        *self._serialize_ranking_details(ranking_result.audit_details),
                    ],
                    trigger_source=trigger_source,
                )
            except IntegrityError:
                raise
            except Exception as exc:
                self.reservation_repository.db.rollback()
                raise ParkingReassignmentAuditPersistenceError() from exc
        except IntegrityError as exc:
            self.reservation_repository.db.rollback()
            if self.reservation_repository.get_active_by_availability_id(availability_id) is not None:
                raise ParkingReassignmentActiveReservationExistsError() from exc

            raise ParkingReassignmentIntegrityError() from exc
        except ParkingReassignmentServiceError:
            raise
        except Exception:
            self.reservation_repository.db.rollback()
            raise

        return ParkingReassignmentResult(
            reservation=reservation,
            previous_reservation=previous_reservation,
            audit_log=audit_log,
            selected_application=selected_application,
            rejected_applications=rejected_applications,
            availability=availability,
        )

    def _validate_actor(
        self,
        availability: ParkingAvailability,
        trigger_source: ParkingAssignmentTriggerSource,
        actor_user_id: int | None,
    ) -> None:
        if trigger_source is ParkingAssignmentTriggerSource.SCHEDULED:
            if actor_user_id is not None:
                raise ParkingReassignmentPermissionError()
            return
        if actor_user_id is None:
            raise ParkingReassignmentPermissionError()

        actor = self.user_repository.get_by_id(actor_user_id)
        if actor is None or not actor.is_active:
            raise ParkingReassignmentPermissionError()
        if trigger_source is ParkingAssignmentTriggerSource.MANUAL_OWNER:
            if availability.owner_id != actor.id:
                raise ParkingReassignmentPermissionError()
            return
        if trigger_source is ParkingAssignmentTriggerSource.MANUAL_ADMIN and actor.role is UserRole.ADMIN:
            return

        raise ParkingReassignmentPermissionError()

    def _serialize_ranking_details(
        self,
        details: tuple[ParkingApplicationRankingAuditDetail, ...],
    ) -> list[dict[str, object]]:
        return [
            {
                "action": "candidate_ranking",
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

    def _normalize_optional_reason(self, reason: str | None) -> str | None:
        if reason is None:
            return None

        normalized_reason = reason.strip()
        return normalized_reason or None

    def _now(self) -> datetime:
        return self._as_aware_utc(self.now_provider())

    def _as_aware_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

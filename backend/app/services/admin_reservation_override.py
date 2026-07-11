from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog, ParkingAssignmentTriggerSource
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.users import UserRepository


class AdminReservationOverrideServiceError(Exception):
    """Base class for admin reservation override failures."""


class AdminReservationOverrideReasonRequiredError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideAdminNotFoundError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideAdminInactiveError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverridePermissionError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideAvailabilityNotFoundError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideAvailabilityNotOpenError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideAvailabilityNotAssignedError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideApplicationNotFoundError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideApplicationAvailabilityMismatchError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideApplicationNotPendingError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideApplicantInactiveError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideApplicantNotFoundError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideApplicantAlreadyReservedError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideApplicationAlreadyReservedError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideReservationExistsError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideExistingReservationNotFoundError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideExistingReservationNotActiveError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideIntegrityError(AdminReservationOverrideServiceError):
    pass


class AdminReservationOverrideAuditPersistenceError(AdminReservationOverrideServiceError):
    pass


@dataclass(frozen=True)
class AdminReservationOverrideResult:
    reservation: ParkingReservation
    audit_log: ParkingAssignmentAuditLog
    selected_application: ParkingApplication
    rejected_applications: list[ParkingApplication]
    availability: ParkingAvailability


@dataclass(frozen=True)
class AdminReservationReplacementResult:
    reservation: ParkingReservation
    audit_log: ParkingAssignmentAuditLog
    previous_application: ParkingApplication
    selected_application: ParkingApplication
    rejected_applications: list[ParkingApplication]
    availability: ParkingAvailability


class AdminReservationOverrideService:
    RANKING_POLICY = "admin_override_manual_selection_v1"
    REPLACEMENT_POLICY = "admin_override_replacement_v1"

    def __init__(
        self,
        availability_repository: ParkingAvailabilityRepository,
        application_repository: ParkingApplicationRepository,
        reservation_repository: ParkingReservationRepository,
        audit_log_repository: ParkingAssignmentAuditLogRepository | None = None,
        user_repository: UserRepository | None = None,
    ) -> None:
        self.availability_repository = availability_repository
        self.application_repository = application_repository
        self.reservation_repository = reservation_repository
        self.audit_log_repository = audit_log_repository or ParkingAssignmentAuditLogRepository(reservation_repository.db)
        self.user_repository = user_repository or UserRepository(reservation_repository.db)

    def override_assign_availability(
        self,
        availability_id: int,
        application_id: int,
        admin_user_id: int,
        reason: str,
    ) -> AdminReservationOverrideResult:
        """Manually assign one pending application and persist the admin decision context."""
        normalized_reason = self._normalize_reason(reason)
        admin_user = self._get_active_admin(admin_user_id)

        availability = self.availability_repository.get_by_id_for_update(availability_id)
        if availability is None:
            raise AdminReservationOverrideAvailabilityNotFoundError()
        if availability.status is not ParkingAvailabilityStatus.OPEN:
            raise AdminReservationOverrideAvailabilityNotOpenError()

        if self.reservation_repository.get_by_availability_id(availability.id) is not None:
            raise AdminReservationOverrideReservationExistsError()

        requested_application = self.application_repository.get_by_id(application_id)
        if requested_application is None:
            raise AdminReservationOverrideApplicationNotFoundError()
        if requested_application.availability_id != availability.id:
            raise AdminReservationOverrideApplicationAvailabilityMismatchError()
        if requested_application.status is not ParkingApplicationStatus.PENDING:
            raise AdminReservationOverrideApplicationNotPendingError()
        if not requested_application.applicant.is_active:
            raise AdminReservationOverrideApplicantInactiveError()

        pending_applications = self.application_repository.list_pending_by_availability_id_for_update(availability.id)
        selected_application = next(
            (application for application in pending_applications if application.id == requested_application.id),
            None,
        )
        if selected_application is None:
            raise AdminReservationOverrideApplicationNotPendingError()

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
                            "assignment_method": "admin_override",
                            "selection_basis": "manual_admin_selection",
                            "admin_user_id": admin_user.id,
                            "override_reason": normalized_reason,
                            "selected_application_id": selected_application.id,
                            "selected_user_id": selected_application.applicant_id,
                            "considered_pending_application_ids": [
                                application.id for application in pending_applications
                            ],
                        },
                    ],
                    trigger_source=ParkingAssignmentTriggerSource.ADMIN_OVERRIDE,
                )
            except IntegrityError:
                raise
            except Exception as exc:
                self.reservation_repository.db.rollback()
                raise AdminReservationOverrideAuditPersistenceError() from exc
        except IntegrityError as exc:
            self.reservation_repository.db.rollback()
            if self.reservation_repository.get_active_by_availability_id(availability_id) is not None:
                raise AdminReservationOverrideReservationExistsError() from exc

            raise AdminReservationOverrideIntegrityError() from exc
        except AdminReservationOverrideServiceError:
            raise
        except Exception:
            self.reservation_repository.db.rollback()
            raise

        return AdminReservationOverrideResult(
            reservation=reservation,
            audit_log=audit_log,
            selected_application=selected_application,
            rejected_applications=rejected_applications,
            availability=availability,
        )

    def replace_existing_reservation(
        self,
        availability_id: int,
        application_id: int | None,
        admin_user_id: int,
        reason: str,
        *,
        applicant_id: int | None = None,
    ) -> AdminReservationReplacementResult:
        """Replace an active reservation in place and preserve both audit events."""
        normalized_reason = self._normalize_reason(reason)
        admin_user = self._get_active_admin(admin_user_id)
        if (application_id is None) == (applicant_id is None):
            raise AdminReservationOverrideIntegrityError()

        initial_active_reservation = self.reservation_repository.get_active_by_availability_id(availability_id)
        initial_reservation_snapshot = (
            None
            if initial_active_reservation is None
            else (
                initial_active_reservation.id,
                initial_active_reservation.application_id,
                initial_active_reservation.reserved_for_user_id,
                initial_active_reservation.status,
            )
        )
        availability = self.availability_repository.get_by_id_for_update(availability_id)
        if availability is None:
            raise AdminReservationOverrideAvailabilityNotFoundError()
        if availability.status is not ParkingAvailabilityStatus.ASSIGNED:
            raise AdminReservationOverrideAvailabilityNotAssignedError()

        reservation = self.reservation_repository.get_active_by_availability_id_for_update(availability.id)
        if reservation is None:
            existing_reservation = self.reservation_repository.get_by_availability_id_for_update(availability.id)
            if existing_reservation is None:
                raise AdminReservationOverrideExistingReservationNotFoundError()

            raise AdminReservationOverrideExistingReservationNotActiveError()
        if reservation.status is not ParkingReservationStatus.ACTIVE:
            raise AdminReservationOverrideExistingReservationNotActiveError()
        if self._active_reservation_changed(initial_reservation_snapshot, reservation):
            raise AdminReservationOverrideIntegrityError()

        previous_application_id = reservation.application_id
        previous_user_id = reservation.reserved_for_user_id
        if previous_application_id is None:
            raise AdminReservationOverrideIntegrityError()

        previous_application = self.application_repository.get_by_id(previous_application_id)
        if previous_application is None:
            raise AdminReservationOverrideIntegrityError()
        if application_id is not None:
            requested_application = self._get_pending_replacement_application(
                availability_id=availability.id,
                application_id=application_id,
                previous_application_id=previous_application_id,
            )
            candidate_action = "existing_pending_application"
            selection_basis = "manual_admin_replacement"
            requested_applicant_id = requested_application.applicant_id
        else:
            requested_application = None
            candidate_action = "created_application"
            selection_basis = "manual_admin_replacement_by_applicant"
            requested_applicant_id = self._validate_replacement_applicant(
                applicant_id=applicant_id,
                previous_user_id=previous_user_id,
            ).id

        try:
            if applicant_id is not None:
                requested_application, candidate_action = self._prepare_replacement_application_for_applicant(
                    availability_id=availability.id,
                    applicant_id=requested_applicant_id,
                )

            pending_applications = self.application_repository.list_pending_by_availability_id_for_update(
                availability.id,
            )
            selected_application = next(
                (application for application in pending_applications if application.id == requested_application.id),
                None,
            )
            if selected_application is None:
                raise AdminReservationOverrideApplicationNotPendingError()

            applications_to_reject = [
                application for application in pending_applications if application.id != selected_application.id
            ]
            previous_application = self.application_repository.update(
                previous_application,
                {"status": ParkingApplicationStatus.REJECTED},
            )
            selected_application = self.application_repository.update(
                selected_application,
                {"status": ParkingApplicationStatus.SELECTED},
            )
            rejected_applications = [previous_application]
            rejected_applications.extend(
                self.application_repository.update(
                    application,
                    {"status": ParkingApplicationStatus.REJECTED},
                )
                for application in applications_to_reject
            )
            reservation = self.reservation_repository.update(
                reservation,
                {
                    "application_id": selected_application.id,
                    "reserved_for_user_id": selected_application.applicant_id,
                    "status": ParkingReservationStatus.ACTIVE,
                },
            )
            audit_detail = {
                "action": "replacement",
                "assignment_method": "admin_override",
                "selection_basis": "manual_admin_replacement",
                "admin_user_id": admin_user.id,
                "override_reason": normalized_reason,
                "previous_reservation_id": reservation.id,
                "previous_application_id": previous_application_id,
                "previous_user_id": previous_user_id,
                "new_reservation_id": reservation.id,
                "selected_application_id": selected_application.id,
                "selected_user_id": selected_application.applicant_id,
                "considered_pending_application_ids": [
                    application.id for application in pending_applications
                ],
            }
            if applicant_id is not None:
                audit_detail.update(
                    {
                        "replacement_selection_basis": selection_basis,
                        "replacement_candidate_action": candidate_action,
                        "requested_applicant_id": requested_applicant_id,
                        "created_or_reactivated_application_id": selected_application.id,
                    },
                )
            try:
                audit_log = self.audit_log_repository.create(
                    availability_id=availability.id,
                    reservation_id=reservation.id,
                    selected_application_id=selected_application.id,
                    selected_user_id=selected_application.applicant_id,
                    rejected_application_ids=[application.id for application in rejected_applications],
                    ranking_policy=self.REPLACEMENT_POLICY,
                    ranking_details=[audit_detail],
                    trigger_source=ParkingAssignmentTriggerSource.ADMIN_OVERRIDE,
                )
            except IntegrityError:
                raise
            except Exception as exc:
                self.reservation_repository.db.rollback()
                raise AdminReservationOverrideAuditPersistenceError() from exc
        except IntegrityError as exc:
            self.reservation_repository.db.rollback()
            raise AdminReservationOverrideIntegrityError() from exc
        except AdminReservationOverrideServiceError:
            raise
        except Exception:
            self.reservation_repository.db.rollback()
            raise

        return AdminReservationReplacementResult(
            reservation=reservation,
            audit_log=audit_log,
            previous_application=previous_application,
            selected_application=selected_application,
            rejected_applications=rejected_applications,
            availability=availability,
        )

    def _get_pending_replacement_application(
        self,
        *,
        availability_id: int,
        application_id: int,
        previous_application_id: int,
    ) -> ParkingApplication:
        requested_application = self.application_repository.get_by_id(application_id)
        if requested_application is None:
            raise AdminReservationOverrideApplicationNotFoundError()
        if requested_application.availability_id != availability_id:
            raise AdminReservationOverrideApplicationAvailabilityMismatchError()
        if requested_application.id == previous_application_id:
            raise AdminReservationOverrideApplicationAlreadyReservedError()
        if requested_application.status is not ParkingApplicationStatus.PENDING:
            raise AdminReservationOverrideApplicationNotPendingError()
        if not requested_application.applicant.is_active:
            raise AdminReservationOverrideApplicantInactiveError()

        return requested_application

    def _validate_replacement_applicant(
        self,
        *,
        applicant_id: int | None,
        previous_user_id: int,
    ) -> User:
        if applicant_id is None:
            raise AdminReservationOverrideIntegrityError()

        applicant = self.user_repository.get_by_id(applicant_id)
        if applicant is None:
            raise AdminReservationOverrideApplicantNotFoundError()
        if not applicant.is_active:
            raise AdminReservationOverrideApplicantInactiveError()
        if applicant.id == previous_user_id:
            raise AdminReservationOverrideApplicantAlreadyReservedError()

        return applicant

    def _prepare_replacement_application_for_applicant(
        self,
        *,
        availability_id: int,
        applicant_id: int,
    ) -> tuple[ParkingApplication, str]:
        existing_application = self.application_repository.get_by_availability_and_applicant_for_update(
            availability_id=availability_id,
            applicant_id=applicant_id,
        )
        if existing_application is None:
            return (
                self.application_repository.create(
                    availability_id=availability_id,
                    applicant_id=applicant_id,
                    status=ParkingApplicationStatus.PENDING,
                    note="Admin replacement override candidate",
                ),
                "created_application",
            )

        if self.reservation_repository.get_by_application_id(existing_application.id) is not None:
            raise AdminReservationOverrideApplicationAlreadyReservedError()
        if existing_application.status is ParkingApplicationStatus.SELECTED:
            raise AdminReservationOverrideApplicationAlreadyReservedError()
        if existing_application.status is ParkingApplicationStatus.PENDING:
            return existing_application, "existing_pending_application"

        if existing_application.status in {
            ParkingApplicationStatus.REJECTED,
            ParkingApplicationStatus.CANCELLED,
        }:
            return (
                self.application_repository.update(
                    existing_application,
                    {"status": ParkingApplicationStatus.PENDING},
                ),
                "reactivated_existing_application",
            )

        raise AdminReservationOverrideApplicationNotPendingError()

    def _active_reservation_changed(
        self,
        initial_reservation_snapshot: tuple[int, int | None, int, ParkingReservationStatus] | None,
        locked_reservation: ParkingReservation,
    ) -> bool:
        if initial_reservation_snapshot is None:
            return False

        (
            initial_id,
            initial_application_id,
            initial_reserved_for_user_id,
            initial_status,
        ) = initial_reservation_snapshot

        return (
            initial_id != locked_reservation.id
            or initial_application_id != locked_reservation.application_id
            or initial_reserved_for_user_id != locked_reservation.reserved_for_user_id
            or initial_status is not locked_reservation.status
        )

    def _normalize_reason(self, reason: str) -> str:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise AdminReservationOverrideReasonRequiredError()

        return normalized_reason

    def _get_active_admin(self, admin_user_id: int) -> User:
        admin_user = self.user_repository.get_by_id(admin_user_id)
        if admin_user is None:
            raise AdminReservationOverrideAdminNotFoundError()
        if not admin_user.is_active:
            raise AdminReservationOverrideAdminInactiveError()
        if admin_user.role is not UserRole.ADMIN:
            raise AdminReservationOverridePermissionError()

        return admin_user

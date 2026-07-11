from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

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


class ParkingReservationCancellationServiceError(Exception):
    """Base class for reservation cancellation failures."""


class ParkingReservationCancellationNotFoundError(ParkingReservationCancellationServiceError):
    pass


class ParkingReservationCancellationNotActiveError(ParkingReservationCancellationServiceError):
    pass


class ParkingReservationCancellationPermissionError(ParkingReservationCancellationServiceError):
    pass


class ParkingReservationCancellationAdminReasonRequiredError(ParkingReservationCancellationServiceError):
    pass


class ParkingReservationCancellationIntegrityError(ParkingReservationCancellationServiceError):
    pass


class ParkingReservationCancellationAuditPersistenceError(ParkingReservationCancellationServiceError):
    pass


class ParkingReservationCancellationActorType(str, Enum):
    RESERVED_USER = "reserved_user"
    AVAILABILITY_OWNER = "availability_owner"
    ADMIN = "admin"


@dataclass(frozen=True)
class ParkingReservationCancellationResult:
    reservation: ParkingReservation
    availability: ParkingAvailability
    application: ParkingApplication
    actor_type: ParkingReservationCancellationActorType
    audit_log: ParkingAssignmentAuditLog | None


@dataclass(frozen=True)
class _LockedReservationContext:
    reservation: ParkingReservation
    availability: ParkingAvailability


@dataclass(frozen=True)
class _CancellationContext(_LockedReservationContext):
    application: ParkingApplication


class ParkingReservationCancellationService:
    AUDIT_POLICY = "reservation_cancellation_v1"

    def __init__(
        self,
        reservation_repository: ParkingReservationRepository,
        availability_repository: ParkingAvailabilityRepository,
        application_repository: ParkingApplicationRepository,
        audit_log_repository: ParkingAssignmentAuditLogRepository | None = None,
        user_repository: UserRepository | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.reservation_repository = reservation_repository
        self.availability_repository = availability_repository
        self.application_repository = application_repository
        self.audit_log_repository = audit_log_repository or ParkingAssignmentAuditLogRepository(reservation_repository.db)
        self.user_repository = user_repository or UserRepository(reservation_repository.db)
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    def cancel_for_user_or_owner(
        self,
        reservation_id: int,
        actor_user_id: int,
        reason: str | None = None,
    ) -> ParkingReservationCancellationResult:
        locked_context = self._lock_reservation_context(reservation_id)
        normalized_reason = self._normalize_optional_reason(reason)

        if locked_context.reservation.reserved_for_user_id == actor_user_id:
            self._ensure_active(locked_context.reservation)
            return self._cancel(
                self._lock_application(locked_context),
                actor_user_id=actor_user_id,
                actor_type=ParkingReservationCancellationActorType.RESERVED_USER,
                reason=normalized_reason,
                application_status=ParkingApplicationStatus.CANCELLED,
                trigger_source=None,
            )
        if locked_context.availability.owner_id == actor_user_id:
            self._ensure_active(locked_context.reservation)
            return self._cancel(
                self._lock_application(locked_context),
                actor_user_id=actor_user_id,
                actor_type=ParkingReservationCancellationActorType.AVAILABILITY_OWNER,
                reason=normalized_reason,
                application_status=ParkingApplicationStatus.REJECTED,
                trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            )

        raise ParkingReservationCancellationPermissionError()

    def cancel_my_reservation(
        self,
        reservation_id: int,
        user_id: int,
        reason: str | None = None,
    ) -> ParkingReservationCancellationResult:
        locked_context = self._lock_reservation_context(reservation_id)
        if locked_context.reservation.reserved_for_user_id != user_id:
            raise ParkingReservationCancellationPermissionError()
        self._ensure_active(locked_context.reservation)

        return self._cancel(
            self._lock_application(locked_context),
            actor_user_id=user_id,
            actor_type=ParkingReservationCancellationActorType.RESERVED_USER,
            reason=self._normalize_optional_reason(reason),
            application_status=ParkingApplicationStatus.CANCELLED,
            trigger_source=None,
        )

    def cancel_as_owner(
        self,
        reservation_id: int,
        owner_id: int,
        reason: str | None = None,
    ) -> ParkingReservationCancellationResult:
        locked_context = self._lock_reservation_context(reservation_id)
        if locked_context.availability.owner_id != owner_id:
            raise ParkingReservationCancellationPermissionError()
        self._ensure_active(locked_context.reservation)

        return self._cancel(
            self._lock_application(locked_context),
            actor_user_id=owner_id,
            actor_type=ParkingReservationCancellationActorType.AVAILABILITY_OWNER,
            reason=self._normalize_optional_reason(reason),
            application_status=ParkingApplicationStatus.REJECTED,
            trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
        )

    def cancel_as_admin(
        self,
        reservation_id: int,
        admin_user_id: int,
        reason: str,
    ) -> ParkingReservationCancellationResult:
        normalized_reason = self._normalize_admin_reason(reason)
        admin = self.user_repository.get_by_id(admin_user_id)
        if admin is None or not admin.is_active or admin.role is not UserRole.ADMIN:
            raise ParkingReservationCancellationPermissionError()

        locked_context = self._lock_reservation_context(reservation_id)
        self._ensure_active(locked_context.reservation)
        return self._cancel(
            self._lock_application(locked_context),
            actor_user_id=admin.id,
            actor_type=ParkingReservationCancellationActorType.ADMIN,
            reason=normalized_reason,
            application_status=ParkingApplicationStatus.REJECTED,
            trigger_source=ParkingAssignmentTriggerSource.ADMIN_OVERRIDE,
        )

    def _lock_reservation_context(self, reservation_id: int) -> _LockedReservationContext:
        initial_reservation = self.reservation_repository.get_by_id(reservation_id)
        if initial_reservation is None:
            raise ParkingReservationCancellationNotFoundError()
        initial_status = initial_reservation.status
        initial_application_id = initial_reservation.application_id
        initial_reserved_for_user_id = initial_reservation.reserved_for_user_id

        availability = self.availability_repository.get_by_id_for_update(initial_reservation.availability_id)
        if availability is None:
            raise ParkingReservationCancellationIntegrityError()

        reservation = self.reservation_repository.get_by_id_for_update(reservation_id)
        if reservation is None:
            raise ParkingReservationCancellationNotFoundError()
        if self._reservation_identity_changed(
            initial_status=initial_status,
            initial_application_id=initial_application_id,
            initial_reserved_for_user_id=initial_reserved_for_user_id,
            locked_reservation=reservation,
        ):
            raise ParkingReservationCancellationIntegrityError()

        return _LockedReservationContext(
            reservation=reservation,
            availability=availability,
        )

    def _reservation_identity_changed(
        self,
        *,
        initial_status: ParkingReservationStatus,
        initial_application_id: int | None,
        initial_reserved_for_user_id: int,
        locked_reservation: ParkingReservation,
    ) -> bool:
        return (
            initial_status is ParkingReservationStatus.ACTIVE
            and locked_reservation.status is ParkingReservationStatus.ACTIVE
            and (
                locked_reservation.application_id != initial_application_id
                or locked_reservation.reserved_for_user_id != initial_reserved_for_user_id
            )
        )

    def _lock_application(self, context: _LockedReservationContext) -> _CancellationContext:
        reservation = context.reservation
        availability = context.availability
        if reservation.application_id is None:
            raise ParkingReservationCancellationIntegrityError()

        application = self.application_repository.get_by_id_for_update(reservation.application_id)
        if application is None:
            raise ParkingReservationCancellationIntegrityError()
        if (
            application.availability_id != availability.id
            or application.applicant_id != reservation.reserved_for_user_id
            or application.status is not ParkingApplicationStatus.SELECTED
        ):
            raise ParkingReservationCancellationIntegrityError()

        return _CancellationContext(
            reservation=reservation,
            availability=availability,
            application=application,
        )

    def _ensure_active(self, reservation: ParkingReservation) -> None:
        if reservation.status is not ParkingReservationStatus.ACTIVE:
            raise ParkingReservationCancellationNotActiveError()

    def _cancel(
        self,
        context: _CancellationContext,
        *,
        actor_user_id: int,
        actor_type: ParkingReservationCancellationActorType,
        reason: str | None,
        application_status: ParkingApplicationStatus,
        trigger_source: ParkingAssignmentTriggerSource | None,
    ) -> ParkingReservationCancellationResult:
        availability_status = (
            ParkingAvailabilityStatus.OPEN
            if self._as_aware_utc(context.availability.end_at) > self._now()
            else ParkingAvailabilityStatus.EXPIRED
        )

        try:
            reservation = self.reservation_repository.update(
                context.reservation,
                {"status": ParkingReservationStatus.CANCELLED},
            )
            availability = self.availability_repository.update(
                context.availability,
                {"status": availability_status},
            )
            application = self.application_repository.update(
                context.application,
                {"status": application_status},
            )
            audit_log = self._create_audit_log(
                reservation=reservation,
                availability=availability,
                application=application,
                actor_user_id=actor_user_id,
                actor_type=actor_type,
                reason=reason,
                trigger_source=trigger_source,
            )
        except IntegrityError as exc:
            self.reservation_repository.db.rollback()
            raise ParkingReservationCancellationIntegrityError() from exc
        except ParkingReservationCancellationServiceError:
            raise
        except Exception:
            self.reservation_repository.db.rollback()
            raise

        return ParkingReservationCancellationResult(
            reservation=reservation,
            availability=availability,
            application=application,
            actor_type=actor_type,
            audit_log=audit_log,
        )

    def _create_audit_log(
        self,
        *,
        reservation: ParkingReservation,
        availability: ParkingAvailability,
        application: ParkingApplication,
        actor_user_id: int,
        actor_type: ParkingReservationCancellationActorType,
        reason: str | None,
        trigger_source: ParkingAssignmentTriggerSource | None,
    ) -> ParkingAssignmentAuditLog | None:
        if trigger_source is None:
            return None

        details: dict[str, object] = {
            "action": "cancellation",
            "cancellation_actor_type": actor_type.value,
            "actor_user_id": actor_user_id,
            "reason": reason,
            "reservation_id": reservation.id,
            "availability_id": availability.id,
            "previous_application_id": application.id,
            "previous_user_id": reservation.reserved_for_user_id,
            "reservation_status": reservation.status.value,
            "availability_status": availability.status.value,
            "application_status": application.status.value,
        }
        if actor_type is ParkingReservationCancellationActorType.ADMIN:
            details["admin_user_id"] = actor_user_id
        elif actor_type is ParkingReservationCancellationActorType.AVAILABILITY_OWNER:
            details["owner_user_id"] = actor_user_id

        try:
            return self.audit_log_repository.create(
                availability_id=availability.id,
                reservation_id=reservation.id,
                selected_application_id=application.id,
                selected_user_id=reservation.reserved_for_user_id,
                rejected_application_ids=(
                    [application.id]
                    if application.status is ParkingApplicationStatus.REJECTED
                    else []
                ),
                ranking_policy=self.AUDIT_POLICY,
                ranking_details=[details],
                trigger_source=trigger_source,
            )
        except IntegrityError:
            raise
        except Exception as exc:
            self.reservation_repository.db.rollback()
            raise ParkingReservationCancellationAuditPersistenceError() from exc

    def _normalize_optional_reason(self, reason: str | None) -> str | None:
        if reason is None:
            return None

        normalized_reason = reason.strip()
        return normalized_reason or None

    def _normalize_admin_reason(self, reason: str) -> str:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ParkingReservationCancellationAdminReasonRequiredError()

        return normalized_reason

    def _now(self) -> datetime:
        return self._as_aware_utc(self.now_provider())

    def _as_aware_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

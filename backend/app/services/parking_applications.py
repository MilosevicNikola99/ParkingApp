from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.schemas.parking_application import ParkingApplicationCreate


class ParkingApplicationServiceError(Exception):
    """Base class for parking application business-rule failures."""


class ParkingApplicationAvailabilityNotFoundError(ParkingApplicationServiceError):
    pass


class ParkingApplicationAvailabilityNotOpenError(ParkingApplicationServiceError):
    pass


class ParkingApplicationAvailabilityExpiredError(ParkingApplicationServiceError):
    pass


class ParkingApplicationInactiveApplicantError(ParkingApplicationServiceError):
    pass


class ParkingApplicationInactiveParkingSpotError(ParkingApplicationServiceError):
    pass


class ParkingApplicationOwnerCannotApplyError(ParkingApplicationServiceError):
    pass


class ParkingApplicationDuplicateError(ParkingApplicationServiceError):
    pass


class ParkingApplicationNotFoundError(ParkingApplicationServiceError):
    pass


class ParkingApplicationPermissionError(ParkingApplicationServiceError):
    pass


class ParkingApplicationStatusTransitionError(ParkingApplicationServiceError):
    pass


class ParkingApplicationService:
    def __init__(
        self,
        application_repository: ParkingApplicationRepository,
        availability_repository: ParkingAvailabilityRepository,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.application_repository = application_repository
        self.availability_repository = availability_repository
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    def apply_for_availability(
        self,
        application_create: ParkingApplicationCreate,
        current_user: User,
    ) -> ParkingApplication:
        if not current_user.is_active:
            raise ParkingApplicationInactiveApplicantError()

        availability = self.availability_repository.get_by_id_for_update(application_create.availability_id)
        if availability is None:
            raise ParkingApplicationAvailabilityNotFoundError()

        self._validate_availability_can_accept_application(availability, current_user)

        existing_application = self.application_repository.get_by_availability_and_applicant(
            availability_id=availability.id,
            applicant_id=current_user.id,
        )
        if existing_application is not None:
            raise ParkingApplicationDuplicateError()

        try:
            return self.application_repository.create(
                availability_id=availability.id,
                applicant_id=current_user.id,
                note=application_create.note,
            )
        except IntegrityError as exc:
            self.application_repository.db.rollback()
            raise ParkingApplicationDuplicateError() from exc

    def list_my_applications(
        self,
        current_user: User,
        *,
        skip: int = 0,
        limit: int = 100,
        status: ParkingApplicationStatus | None = None,
    ) -> list[ParkingApplication]:
        return self.application_repository.list_by_applicant_id(
            current_user.id,
            skip=skip,
            limit=limit,
            status=status,
        )

    def get_application_for_user(self, application_id: int, current_user: User) -> ParkingApplication:
        application = self.application_repository.get_by_id(application_id)
        if application is None:
            raise ParkingApplicationNotFoundError()
        if self._can_view_application(application, current_user):
            return application

        raise ParkingApplicationPermissionError()

    def cancel_my_application(self, application_id: int, current_user: User) -> ParkingApplication:
        application = self.application_repository.get_by_id(application_id)
        if application is None:
            raise ParkingApplicationNotFoundError()
        if application.applicant_id != current_user.id:
            raise ParkingApplicationPermissionError()
        if application.status is not ParkingApplicationStatus.PENDING:
            raise ParkingApplicationStatusTransitionError()

        return self.application_repository.update(
            application,
            {"status": ParkingApplicationStatus.CANCELLED},
        )

    def _validate_availability_can_accept_application(
        self,
        availability: ParkingAvailability,
        current_user: User,
    ) -> None:
        if availability.status is not ParkingAvailabilityStatus.OPEN:
            raise ParkingApplicationAvailabilityNotOpenError()
        if self._as_aware_utc(availability.end_at) <= self._now():
            raise ParkingApplicationAvailabilityExpiredError()
        if availability.owner_id == current_user.id:
            raise ParkingApplicationOwnerCannotApplyError()
        if availability.parking_spot is not None and not availability.parking_spot.is_active:
            raise ParkingApplicationInactiveParkingSpotError()

    def _can_view_application(self, application: ParkingApplication, current_user: User) -> bool:
        return application.applicant_id == current_user.id or current_user.role is UserRole.ADMIN

    def _now(self) -> datetime:
        now = self.now_provider()
        return self._as_aware_utc(now)

    def _as_aware_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

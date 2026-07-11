from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.core.config import Settings, get_settings
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.user import User, UserRole
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.schemas.parking_availability import ParkingAvailabilityCreate


class ParkingAvailabilityServiceError(Exception):
    """Base class for parking availability business-rule failures."""


class ParkingSpotNotFoundError(ParkingAvailabilityServiceError):
    pass


class InactiveParkingSpotError(ParkingAvailabilityServiceError):
    pass


class ParkingAvailabilityPermissionError(ParkingAvailabilityServiceError):
    pass


class ParkingAvailabilityOverlapError(ParkingAvailabilityServiceError):
    pass


class ParkingAvailabilityTimeError(ParkingAvailabilityServiceError):
    pass


class ParkingAvailabilityNotFoundError(ParkingAvailabilityServiceError):
    pass


class ParkingAvailabilityStatusTransitionError(ParkingAvailabilityServiceError):
    pass


class ParkingAvailabilityService:
    def __init__(
        self,
        availability_repository: ParkingAvailabilityRepository,
        parking_spot_repository: ParkingSpotRepository,
        settings: Settings | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.availability_repository = availability_repository
        self.parking_spot_repository = parking_spot_repository
        self.settings = settings or get_settings()
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    def create_availability(
        self,
        availability_create: ParkingAvailabilityCreate,
        current_user: User,
    ) -> ParkingAvailability:
        parking_spot = self.parking_spot_repository.get_by_id(availability_create.parking_spot_id)
        if parking_spot is None:
            raise ParkingSpotNotFoundError()
        if not parking_spot.is_active:
            raise InactiveParkingSpotError()
        if parking_spot.owner_id != current_user.id:
            raise ParkingAvailabilityPermissionError()

        self._validate_not_in_past(availability_create.start_at, availability_create.end_at)
        self._ensure_no_blocking_overlap(
            parking_spot_id=parking_spot.id,
            start_at=availability_create.start_at,
            end_at=availability_create.end_at,
        )

        now = self._now()
        return self.availability_repository.create(
            parking_spot_id=parking_spot.id,
            owner_id=current_user.id,
            start_at=availability_create.start_at,
            end_at=availability_create.end_at,
            note=availability_create.note,
            priority_until=now + timedelta(hours=self.settings.same_team_priority_window_hours),
        )

    def get_availability_for_user(self, availability_id: int, current_user: User) -> ParkingAvailability:
        availability = self.availability_repository.get_by_id(availability_id)
        if availability is None:
            raise ParkingAvailabilityNotFoundError()
        if self._can_view_availability(availability, current_user):
            return availability

        raise ParkingAvailabilityPermissionError()

    def list_my_availabilities(
        self,
        current_user: User,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ParkingAvailability]:
        return self.availability_repository.list_by_owner_id(current_user.id, skip=skip, limit=limit)

    def list_open_availabilities(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        parking_spot_id: int | None = None,
        owner_id: int | None = None,
    ) -> list[ParkingAvailability]:
        return self.availability_repository.list_open(
            skip=skip,
            limit=limit,
            parking_spot_id=parking_spot_id,
            owner_id=owner_id,
        )

    def cancel_availability(self, availability_id: int, current_user: User) -> ParkingAvailability:
        availability = self.availability_repository.get_by_id(availability_id)
        if availability is None:
            raise ParkingAvailabilityNotFoundError()
        if not self._can_manage_availability(availability, current_user):
            raise ParkingAvailabilityPermissionError()
        if availability.status is not ParkingAvailabilityStatus.OPEN:
            raise ParkingAvailabilityStatusTransitionError()

        return self.availability_repository.update(
            availability,
            {"status": ParkingAvailabilityStatus.CANCELLED},
        )

    def _now(self) -> datetime:
        now = self.now_provider()
        if now.tzinfo is None or now.utcoffset() is None:
            return now.replace(tzinfo=UTC)

        return now

    def _validate_not_in_past(self, start_at: datetime, end_at: datetime) -> None:
        now = self._now()
        if end_at <= now:
            raise ParkingAvailabilityTimeError("Availability end time cannot be in the past")
        if start_at < now:
            raise ParkingAvailabilityTimeError("Availability start time cannot be in the past")

    def _ensure_no_blocking_overlap(
        self,
        *,
        parking_spot_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> None:
        overlaps = self.availability_repository.list_blocking_overlaps_for_spot(
            parking_spot_id=parking_spot_id,
            start_at=start_at,
            end_at=end_at,
        )
        if overlaps:
            raise ParkingAvailabilityOverlapError()

    def _can_view_availability(self, availability: ParkingAvailability, current_user: User) -> bool:
        if availability.status is ParkingAvailabilityStatus.OPEN:
            return True

        return self._can_manage_availability(availability, current_user)

    def _can_manage_availability(self, availability: ParkingAvailability, current_user: User) -> bool:
        return availability.owner_id == current_user.id or current_user.role is UserRole.ADMIN

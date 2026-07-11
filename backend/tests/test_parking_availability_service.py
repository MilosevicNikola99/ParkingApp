from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.core.config import Settings
from app.db.base import Base
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_spot import ParkingSpot
from app.models.user import User, UserRole
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.users import UserRepository
from app.schemas.parking_availability import ParkingAvailabilityCreate
from app.services.parking_availabilities import (
    InactiveParkingSpotError,
    ParkingAvailabilityOverlapError,
    ParkingAvailabilityPermissionError,
    ParkingAvailabilityService,
    ParkingAvailabilityStatusTransitionError,
    ParkingAvailabilityTimeError,
    ParkingSpotNotFoundError,
)

TEST_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
TEST_SETTINGS = Settings(same_team_priority_window_hours=2)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def service(db_session: Session) -> ParkingAvailabilityService:
    return ParkingAvailabilityService(
        availability_repository=ParkingAvailabilityRepository(db_session),
        parking_spot_repository=ParkingSpotRepository(db_session),
        settings=TEST_SETTINGS,
        now_provider=lambda: TEST_NOW,
    )


def utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value

    return value.astimezone(UTC).replace(tzinfo=None)


def create_user(
    db_session: Session,
    *,
    email: str,
    username: str,
    role: UserRole = UserRole.PARKING_OWNER,
) -> User:
    return UserRepository(db_session).create(
        email=email,
        username=username,
        first_name="Test",
        last_name="User",
        hashed_password="hashed-password",
        role=role,
    )


def create_owner(db_session: Session) -> User:
    return create_user(db_session, email="owner@example.com", username="owner")


def create_other_owner(db_session: Session) -> User:
    return create_user(db_session, email="other.owner@example.com", username="otherowner")


def create_admin(db_session: Session) -> User:
    return create_user(db_session, email="admin@example.com", username="admin", role=UserRole.ADMIN)


def create_parking_spot(
    db_session: Session,
    *,
    owner_id: int,
    code: str = "A-12",
    is_active: bool = True,
) -> ParkingSpot:
    return ParkingSpotRepository(db_session).create(
        code=code,
        location="Garage P1",
        owner_id=owner_id,
        is_active=is_active,
    )


def availability_create(
    parking_spot_id: int,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> ParkingAvailabilityCreate:
    start = start_at or TEST_NOW + timedelta(hours=1)
    end = end_at or TEST_NOW + timedelta(hours=5)
    return ParkingAvailabilityCreate(
        parking_spot_id=parking_spot_id,
        start_at=start,
        end_at=end,
        note="Remote work day",
    )


def create_existing_availability(
    db_session: Session,
    *,
    parking_spot_id: int,
    owner_id: int,
    status: ParkingAvailabilityStatus = ParkingAvailabilityStatus.OPEN,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> ParkingAvailability:
    return ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at or TEST_NOW + timedelta(hours=1),
        end_at=end_at or TEST_NOW + timedelta(hours=5),
        status=status,
    )


def test_owner_can_create_availability_for_own_active_parking_spot(
    service: ParkingAvailabilityService,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)

    availability = service.create_availability(availability_create(parking_spot.id), owner)

    assert availability.parking_spot_id == parking_spot.id
    assert availability.owner_id == owner.id
    assert availability.status is ParkingAvailabilityStatus.OPEN
    assert availability.note == "Remote work day"
    assert availability.priority_until is not None
    assert utc_naive(availability.priority_until) == utc_naive(TEST_NOW + timedelta(hours=2))


def test_non_owner_cannot_create_availability_for_another_users_spot(
    service: ParkingAvailabilityService,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    other_owner = create_other_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)

    with pytest.raises(ParkingAvailabilityPermissionError):
        service.create_availability(availability_create(parking_spot.id), other_owner)


def test_missing_parking_spot_raises_clean_service_error(service: ParkingAvailabilityService, db_session: Session) -> None:
    owner = create_owner(db_session)

    with pytest.raises(ParkingSpotNotFoundError):
        service.create_availability(availability_create(999), owner)


def test_inactive_parking_spot_cannot_be_published(
    service: ParkingAvailabilityService,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id, is_active=False)

    with pytest.raises(InactiveParkingSpotError):
        service.create_availability(availability_create(parking_spot.id), owner)


@pytest.mark.parametrize(
    "blocking_status",
    [ParkingAvailabilityStatus.OPEN, ParkingAvailabilityStatus.ASSIGNED],
)
def test_overlapping_open_or_assigned_availability_is_rejected(
    service: ParkingAvailabilityService,
    db_session: Session,
    blocking_status: ParkingAvailabilityStatus,
) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    create_existing_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        status=blocking_status,
    )

    with pytest.raises(ParkingAvailabilityOverlapError):
        service.create_availability(
            availability_create(
                parking_spot.id,
                start_at=TEST_NOW + timedelta(hours=2),
                end_at=TEST_NOW + timedelta(hours=3),
            ),
            owner,
        )


def test_overlapping_cancelled_availability_does_not_block(
    service: ParkingAvailabilityService,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    create_existing_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        status=ParkingAvailabilityStatus.CANCELLED,
    )

    availability = service.create_availability(
        availability_create(
            parking_spot.id,
            start_at=TEST_NOW + timedelta(hours=2),
            end_at=TEST_NOW + timedelta(hours=3),
        ),
        owner,
    )

    assert availability.status is ParkingAvailabilityStatus.OPEN


def test_end_at_in_the_past_is_rejected(service: ParkingAvailabilityService, db_session: Session) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)

    with pytest.raises(ParkingAvailabilityTimeError):
        service.create_availability(
            availability_create(
                parking_spot.id,
                start_at=TEST_NOW - timedelta(hours=3),
                end_at=TEST_NOW - timedelta(hours=1),
            ),
            owner,
        )


def test_open_availability_can_be_viewed_by_any_authenticated_user(
    service: ParkingAvailabilityService,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    employee = create_user(db_session, email="employee@example.com", username="employee", role=UserRole.EMPLOYEE)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_existing_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)

    assert service.get_availability_for_user(availability.id, employee).id == availability.id


def test_non_owner_cannot_view_non_open_availability_but_admin_can(
    service: ParkingAvailabilityService,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    employee = create_user(db_session, email="employee@example.com", username="employee", role=UserRole.EMPLOYEE)
    admin = create_admin(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_existing_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        status=ParkingAvailabilityStatus.ASSIGNED,
    )

    with pytest.raises(ParkingAvailabilityPermissionError):
        service.get_availability_for_user(availability.id, employee)

    assert service.get_availability_for_user(availability.id, admin).id == availability.id


def test_owner_and_admin_can_cancel_open_availability(
    service: ParkingAvailabilityService,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    admin = create_admin(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    owner_availability = create_existing_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)
    admin_availability = create_existing_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        start_at=TEST_NOW + timedelta(days=1),
        end_at=TEST_NOW + timedelta(days=1, hours=4),
    )

    assert service.cancel_availability(owner_availability.id, owner).status is ParkingAvailabilityStatus.CANCELLED
    assert service.cancel_availability(admin_availability.id, admin).status is ParkingAvailabilityStatus.CANCELLED


def test_non_owner_cannot_cancel_and_cancelled_cannot_be_cancelled_again(
    service: ParkingAvailabilityService,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    other_owner = create_other_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_existing_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)

    with pytest.raises(ParkingAvailabilityPermissionError):
        service.cancel_availability(availability.id, other_owner)

    service.cancel_availability(availability.id, owner)

    with pytest.raises(ParkingAvailabilityStatusTransitionError):
        service.cancel_availability(availability.id, owner)

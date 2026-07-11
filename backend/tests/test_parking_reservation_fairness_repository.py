from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
from app.models.parking_application import ParkingApplicationStatus
from app.models.parking_reservation import ParkingReservationStatus
from app.models.user import UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.users import UserRepository

TEST_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_count_recent_wins_by_user_ids_filters_status_and_start_at_window(db_session: Session) -> None:
    user_repository = UserRepository(db_session)
    owner = user_repository.create(
        email="fairness.owner@example.com",
        username="fairnessowner",
        first_name="Fairness",
        last_name="Owner",
        hashed_password="hashed-password",
        role=UserRole.PARKING_OWNER,
    )
    applicant = user_repository.create(
        email="fairness.applicant@example.com",
        username="fairnessapplicant",
        first_name="Fairness",
        last_name="Applicant",
        hashed_password="hashed-password",
        role=UserRole.EMPLOYEE,
    )
    applicant_without_wins = user_repository.create(
        email="fairness.zero@example.com",
        username="fairnesszero",
        first_name="Fairness",
        last_name="Zero",
        hashed_password="hashed-password",
        role=UserRole.EMPLOYEE,
    )
    parking_spot = ParkingSpotRepository(db_session).create(code="FR-01", owner_id=owner.id)

    def create_reservation(suffix: str, start_at: datetime, status: ParkingReservationStatus) -> None:
        availability = ParkingAvailabilityRepository(db_session).create(
            parking_spot_id=parking_spot.id,
            owner_id=owner.id,
            start_at=start_at,
            end_at=start_at + timedelta(hours=4),
        )
        application = ParkingApplicationRepository(db_session).create(
            availability_id=availability.id,
            applicant_id=applicant.id,
            status=ParkingApplicationStatus.SELECTED,
            note=suffix,
        )
        ParkingReservationRepository(db_session).create(
            availability_id=availability.id,
            application_id=application.id,
            parking_spot_id=parking_spot.id,
            reserved_for_user_id=applicant.id,
            start_at=start_at,
            end_at=start_at + timedelta(hours=4),
            status=status,
        )

    create_reservation("recent-active", TEST_NOW - timedelta(days=1), ParkingReservationStatus.ACTIVE)
    create_reservation("recent-completed", TEST_NOW - timedelta(days=10), ParkingReservationStatus.COMPLETED)
    create_reservation("recent-cancelled", TEST_NOW - timedelta(days=2), ParkingReservationStatus.CANCELLED)
    create_reservation("outside-window", TEST_NOW - timedelta(days=31), ParkingReservationStatus.COMPLETED)

    counts = ParkingReservationRepository(db_session).count_recent_wins_by_user_ids(
        [applicant.id, applicant_without_wins.id, applicant.id],
        TEST_NOW - timedelta(days=30),
    )

    assert counts == {
        applicant.id: 2,
        applicant_without_wins.id: 0,
    }


def test_count_recent_wins_by_user_ids_returns_empty_map_for_empty_input(db_session: Session) -> None:
    assert ParkingReservationRepository(db_session).count_recent_wins_by_user_ids([], TEST_NOW) == {}

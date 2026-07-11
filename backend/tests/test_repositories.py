from collections.abc import Generator

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
from app.models.parking_availability import ParkingAvailabilityStatus
from app.models.parking_application import ParkingApplicationStatus
from app.models.parking_reservation import ParkingReservationStatus
from app.models.user import UserRole
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.teams import TeamRepository
from app.repositories.users import UserRepository


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value

    return value.astimezone(UTC).replace(tzinfo=None)


def test_team_repository_create_and_get_by_id(db_session: Session) -> None:
    repository = TeamRepository(db_session)

    team = repository.create(name="Engineering", description="Product engineering")

    fetched = repository.get_by_id(team.id)

    assert fetched is not None
    assert fetched.id == team.id
    assert fetched.name == "Engineering"
    assert fetched.description == "Product engineering"


def test_team_repository_get_by_name_and_missing_records(db_session: Session) -> None:
    repository = TeamRepository(db_session)
    repository.create(name="Engineering")

    assert repository.get_by_name("Engineering") is not None
    assert repository.get_by_name("Missing") is None
    assert repository.get_by_id(999) is None


def test_team_repository_list_supports_pagination(db_session: Session) -> None:
    repository = TeamRepository(db_session)
    repository.create(name="Engineering")
    repository.create(name="Finance")
    repository.create(name="Operations")

    teams = repository.list(skip=1, limit=1)

    assert [team.name for team in teams] == ["Finance"]


def test_team_repository_update_changes_only_provided_fields(db_session: Session) -> None:
    repository = TeamRepository(db_session)
    team = repository.create(name="Engineering", description="Original")

    updated = repository.update(team, {"name": "Platform"})

    assert updated.name == "Platform"
    assert updated.description == "Original"


def test_team_repository_update_allows_explicit_none(db_session: Session) -> None:
    repository = TeamRepository(db_session)
    team = repository.create(name="Engineering", description="Original")

    updated = repository.update(team, {"description": None})

    assert updated.description is None


def test_team_repository_delete_removes_record(db_session: Session) -> None:
    repository = TeamRepository(db_session)
    team = repository.create(name="Engineering")

    assert repository.delete(team) is True
    assert repository.get_by_id(team.id) is None


def test_team_repository_unique_name_constraint(db_session: Session) -> None:
    repository = TeamRepository(db_session)
    repository.create(name="Engineering")
    db_session.commit()

    with pytest.raises(IntegrityError):
        repository.create(name="Engineering")


def test_user_repository_create_user_with_team_and_get_by_id(db_session: Session) -> None:
    team_repository = TeamRepository(db_session)
    user_repository = UserRepository(db_session)
    team = team_repository.create(name="Engineering")

    user = user_repository.create(
        email="ada.lovelace@example.com",
        username="alovelace",
        first_name="Ada",
        last_name="Lovelace",
        hashed_password="hashed-password",
        role=UserRole.PARKING_OWNER,
        team_id=team.id,
    )

    fetched = user_repository.get_by_id(user.id)

    assert fetched is not None
    assert fetched.email == "ada.lovelace@example.com"
    assert fetched.team is not None
    assert fetched.team.name == "Engineering"
    assert fetched.role is UserRole.PARKING_OWNER


def test_user_repository_get_by_email_username_and_missing_records(db_session: Session) -> None:
    repository = UserRepository(db_session)
    repository.create(
        email="grace.hopper@example.com",
        username="ghopper",
        first_name="Grace",
        last_name="Hopper",
        hashed_password="hashed-password",
    )

    assert repository.get_by_email("grace.hopper@example.com") is not None
    assert repository.get_by_username("ghopper") is not None
    assert repository.get_by_email("missing@example.com") is None
    assert repository.get_by_username("missing") is None
    assert repository.get_by_id(999) is None


def test_user_repository_list_and_list_by_team_id(db_session: Session) -> None:
    team_repository = TeamRepository(db_session)
    user_repository = UserRepository(db_session)
    engineering = team_repository.create(name="Engineering")
    finance = team_repository.create(name="Finance")
    user_repository.create(
        email="ada.lovelace@example.com",
        username="alovelace",
        first_name="Ada",
        last_name="Lovelace",
        hashed_password="hashed-password",
        team_id=engineering.id,
    )
    user_repository.create(
        email="grace.hopper@example.com",
        username="ghopper",
        first_name="Grace",
        last_name="Hopper",
        hashed_password="hashed-password",
        team_id=engineering.id,
    )
    user_repository.create(
        email="katherine.johnson@example.com",
        username="kjohnson",
        first_name="Katherine",
        last_name="Johnson",
        hashed_password="hashed-password",
        team_id=finance.id,
    )

    paged_users = user_repository.list(skip=1, limit=1)
    engineering_users = user_repository.list_by_team_id(engineering.id)

    assert [user.username for user in paged_users] == ["ghopper"]
    assert [user.username for user in engineering_users] == ["alovelace", "ghopper"]
    assert all(user.team is not None for user in engineering_users)


def test_user_repository_update_changes_only_provided_fields(db_session: Session) -> None:
    repository = UserRepository(db_session)
    user = repository.create(
        email="ada.lovelace@example.com",
        username="alovelace",
        first_name="Ada",
        last_name="Lovelace",
        hashed_password="old-hash",
    )

    updated = repository.update(
        user,
        {
            "first_name": "Augusta",
            "hashed_password": "new-hash",
            "unknown_field": "ignored",
        },
    )

    assert updated.first_name == "Augusta"
    assert updated.last_name == "Lovelace"
    assert updated.hashed_password == "new-hash"
    assert not hasattr(updated, "unknown_field")


def test_user_repository_update_allows_explicit_none_for_team_id(db_session: Session) -> None:
    team_repository = TeamRepository(db_session)
    user_repository = UserRepository(db_session)
    team = team_repository.create(name="Engineering")
    user = user_repository.create(
        email="ada.lovelace@example.com",
        username="alovelace",
        first_name="Ada",
        last_name="Lovelace",
        hashed_password="hashed-password",
        team_id=team.id,
    )

    updated = user_repository.update(user, {"team_id": None})

    assert updated.team_id is None


def test_user_repository_delete_removes_record(db_session: Session) -> None:
    repository = UserRepository(db_session)
    user = repository.create(
        email="ada.lovelace@example.com",
        username="alovelace",
        first_name="Ada",
        last_name="Lovelace",
        hashed_password="hashed-password",
    )

    assert repository.delete(user) is True
    assert repository.get_by_id(user.id) is None


def test_user_repository_unique_email_and_username_constraints(db_session: Session) -> None:
    repository = UserRepository(db_session)
    repository.create(
        email="ada.lovelace@example.com",
        username="alovelace",
        first_name="Ada",
        last_name="Lovelace",
        hashed_password="hashed-password",
    )
    db_session.commit()

    with pytest.raises(IntegrityError):
        repository.create(
            email="ada.lovelace@example.com",
            username="different",
            first_name="Ada",
            last_name="Different",
            hashed_password="hashed-password",
        )

    db_session.rollback()

    with pytest.raises(IntegrityError):
        repository.create(
            email="different@example.com",
            username="alovelace",
            first_name="Different",
            last_name="User",
            hashed_password="hashed-password",
        )


def test_parking_spot_repository_create_with_owner_and_get_by_id(db_session: Session) -> None:
    user_repository = UserRepository(db_session)
    parking_spot_repository = ParkingSpotRepository(db_session)
    owner = user_repository.create(
        email="owner@example.com",
        username="owner",
        first_name="Parking",
        last_name="Owner",
        hashed_password="hashed-password",
        role=UserRole.PARKING_OWNER,
    )

    parking_spot = parking_spot_repository.create(
        code="A-12",
        location="Garage P1",
        description="Near elevator",
        owner_id=owner.id,
    )

    fetched = parking_spot_repository.get_by_id(parking_spot.id)

    assert fetched is not None
    assert fetched.code == "A-12"
    assert fetched.owner is not None
    assert fetched.owner.id == owner.id
    assert fetched.is_active is True


def test_parking_spot_repository_get_by_code_and_missing_records(db_session: Session) -> None:
    repository = ParkingSpotRepository(db_session)
    repository.create(code="A-12")

    assert repository.get_by_code("A-12") is not None
    assert repository.get_by_code("Missing") is None
    assert repository.get_by_id(999) is None


def test_parking_spot_repository_list_and_list_by_owner_id(db_session: Session) -> None:
    user_repository = UserRepository(db_session)
    parking_spot_repository = ParkingSpotRepository(db_session)
    owner = user_repository.create(
        email="owner@example.com",
        username="owner",
        first_name="Parking",
        last_name="Owner",
        hashed_password="hashed-password",
        role=UserRole.PARKING_OWNER,
    )
    other_owner = user_repository.create(
        email="other.owner@example.com",
        username="otherowner",
        first_name="Other",
        last_name="Owner",
        hashed_password="hashed-password",
        role=UserRole.PARKING_OWNER,
    )
    parking_spot_repository.create(code="A-12", owner_id=owner.id)
    parking_spot_repository.create(code="A-13", owner_id=owner.id)
    parking_spot_repository.create(code="B-01", owner_id=other_owner.id)

    paged_spots = parking_spot_repository.list(skip=1, limit=1)
    owner_spots = parking_spot_repository.list_by_owner_id(owner.id)

    assert [spot.code for spot in paged_spots] == ["A-13"]
    assert [spot.code for spot in owner_spots] == ["A-12", "A-13"]
    assert all(spot.owner is not None for spot in owner_spots)


def test_parking_spot_repository_update_changes_only_provided_fields(db_session: Session) -> None:
    repository = ParkingSpotRepository(db_session)
    parking_spot = repository.create(code="A-12", location="Garage P1", description="Original")

    updated = repository.update(
        parking_spot,
        {
            "code": "A-14",
            "location": "Garage P2",
            "is_active": False,
            "unknown_field": "ignored",
        },
    )

    assert updated.code == "A-14"
    assert updated.location == "Garage P2"
    assert updated.description == "Original"
    assert updated.is_active is False
    assert not hasattr(updated, "unknown_field")


def test_parking_spot_repository_update_allows_explicit_none_for_optional_fields(db_session: Session) -> None:
    user_repository = UserRepository(db_session)
    parking_spot_repository = ParkingSpotRepository(db_session)
    owner = user_repository.create(
        email="owner@example.com",
        username="owner",
        first_name="Parking",
        last_name="Owner",
        hashed_password="hashed-password",
        role=UserRole.PARKING_OWNER,
    )
    parking_spot = parking_spot_repository.create(
        code="A-12",
        location="Garage P1",
        description="Original",
        owner_id=owner.id,
    )

    updated = parking_spot_repository.update(
        parking_spot,
        {
            "location": None,
            "description": None,
            "owner_id": None,
        },
    )

    assert updated.location is None
    assert updated.description is None
    assert updated.owner_id is None


def test_parking_spot_repository_delete_removes_record(db_session: Session) -> None:
    repository = ParkingSpotRepository(db_session)
    parking_spot = repository.create(code="A-12")

    assert repository.delete(parking_spot) is True
    assert repository.get_by_id(parking_spot.id) is None


def test_parking_spot_repository_unique_code_constraint(db_session: Session) -> None:
    repository = ParkingSpotRepository(db_session)
    repository.create(code="A-12")
    db_session.commit()

    with pytest.raises(IntegrityError):
        repository.create(code="A-12")


def create_owner_and_parking_spot(db_session: Session) -> tuple[int, int]:
    user_repository = UserRepository(db_session)
    parking_spot_repository = ParkingSpotRepository(db_session)
    owner = user_repository.create(
        email="availability.owner@example.com",
        username="availabilityowner",
        first_name="Availability",
        last_name="Owner",
        hashed_password="hashed-password",
        role=UserRole.PARKING_OWNER,
    )
    parking_spot = parking_spot_repository.create(code="A-12", owner_id=owner.id)
    return owner.id, parking_spot.id


def test_parking_availability_repository_create_and_get_by_id(db_session: Session) -> None:
    owner_id, parking_spot_id = create_owner_and_parking_spot(db_session)
    repository = ParkingAvailabilityRepository(db_session)
    start_at = datetime.now(UTC)
    end_at = start_at + timedelta(hours=8)
    priority_until = start_at + timedelta(hours=2)

    availability = repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at,
        end_at=end_at,
        note="Remote day",
        priority_until=priority_until,
    )

    fetched = repository.get_by_id(availability.id)

    assert fetched is not None
    assert fetched.parking_spot_id == parking_spot_id
    assert fetched.owner_id == owner_id
    assert fetched.status is ParkingAvailabilityStatus.OPEN
    assert fetched.note == "Remote day"
    assert fetched.priority_until is not None
    assert utc_naive(fetched.priority_until) == utc_naive(priority_until)
    assert fetched.parking_spot is not None
    assert fetched.owner is not None


def test_parking_availability_repository_missing_record_returns_none(db_session: Session) -> None:
    assert ParkingAvailabilityRepository(db_session).get_by_id(999) is None


def test_parking_availability_repository_list_methods(db_session: Session) -> None:
    owner_id, parking_spot_id = create_owner_and_parking_spot(db_session)
    user_repository = UserRepository(db_session)
    parking_spot_repository = ParkingSpotRepository(db_session)
    other_owner = user_repository.create(
        email="other.availability.owner@example.com",
        username="otheravailabilityowner",
        first_name="Other",
        last_name="Owner",
        hashed_password="hashed-password",
        role=UserRole.PARKING_OWNER,
    )
    other_spot = parking_spot_repository.create(code="B-01", owner_id=other_owner.id)
    repository = ParkingAvailabilityRepository(db_session)
    start_at = datetime.now(UTC)
    first = repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )
    second = repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at + timedelta(days=1),
        end_at=start_at + timedelta(days=1, hours=4),
        status=ParkingAvailabilityStatus.CANCELLED,
    )
    repository.create(
        parking_spot_id=other_spot.id,
        owner_id=other_owner.id,
        start_at=start_at + timedelta(days=2),
        end_at=start_at + timedelta(days=2, hours=4),
    )

    assert [availability.id for availability in repository.list(skip=1, limit=1)] == [second.id]
    assert [availability.id for availability in repository.list_by_parking_spot_id(parking_spot_id)] == [
        first.id,
        second.id,
    ]
    assert [availability.id for availability in repository.list_by_owner_id(owner_id)] == [first.id, second.id]
    assert [availability.id for availability in repository.list(owner_id=owner_id)] == [first.id, second.id]
    assert [availability.id for availability in repository.list(parking_spot_id=parking_spot_id)] == [
        first.id,
        second.id,
    ]
    assert [availability.id for availability in repository.list_open(owner_id=owner_id)] == [first.id]
    assert [availability.status for availability in repository.list_open()] == [
        ParkingAvailabilityStatus.OPEN,
        ParkingAvailabilityStatus.OPEN,
    ]


def test_parking_availability_repository_update_changes_only_provided_fields(db_session: Session) -> None:
    owner_id, parking_spot_id = create_owner_and_parking_spot(db_session)
    repository = ParkingAvailabilityRepository(db_session)
    start_at = datetime.now(UTC)
    availability = repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
        note="Original",
    )
    new_end_at = start_at + timedelta(hours=6)

    updated = repository.update(
        availability,
        {
            "end_at": new_end_at,
            "status": ParkingAvailabilityStatus.CANCELLED,
            "note": None,
            "unknown_field": "ignored",
        },
    )

    assert utc_naive(updated.start_at) == utc_naive(start_at)
    assert utc_naive(updated.end_at) == utc_naive(new_end_at)
    assert updated.status is ParkingAvailabilityStatus.CANCELLED
    assert updated.note is None
    assert not hasattr(updated, "unknown_field")


def test_parking_availability_repository_list_overlapping_for_spot(db_session: Session) -> None:
    owner_id, parking_spot_id = create_owner_and_parking_spot(db_session)
    repository = ParkingAvailabilityRepository(db_session)
    start_at = datetime.now(UTC)
    overlapping = repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )
    repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at + timedelta(hours=5),
        end_at=start_at + timedelta(hours=6),
    )

    results = repository.list_overlapping_for_spot(
        parking_spot_id=parking_spot_id,
        start_at=start_at + timedelta(hours=2),
        end_at=start_at + timedelta(hours=3),
    )

    assert [availability.id for availability in results] == [overlapping.id]


def test_parking_availability_repository_list_blocking_overlaps_ignores_cancelled_and_expired(
    db_session: Session,
) -> None:
    owner_id, parking_spot_id = create_owner_and_parking_spot(db_session)
    repository = ParkingAvailabilityRepository(db_session)
    start_at = datetime.now(UTC)
    open_availability = repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
        status=ParkingAvailabilityStatus.OPEN,
    )
    assigned_availability = repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at + timedelta(hours=6),
        end_at=start_at + timedelta(hours=8),
        status=ParkingAvailabilityStatus.ASSIGNED,
    )
    repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at + timedelta(hours=10),
        end_at=start_at + timedelta(hours=12),
        status=ParkingAvailabilityStatus.CANCELLED,
    )
    repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at + timedelta(hours=14),
        end_at=start_at + timedelta(hours=16),
        status=ParkingAvailabilityStatus.EXPIRED,
    )

    results = repository.list_blocking_overlaps_for_spot(
        parking_spot_id=parking_spot_id,
        start_at=start_at + timedelta(hours=1),
        end_at=start_at + timedelta(hours=15),
    )

    assert [availability.id for availability in results] == [open_availability.id, assigned_availability.id]


def test_parking_availability_repository_delete_removes_record(db_session: Session) -> None:
    owner_id, parking_spot_id = create_owner_and_parking_spot(db_session)
    repository = ParkingAvailabilityRepository(db_session)
    start_at = datetime.now(UTC)
    availability = repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )

    assert repository.delete(availability) is True
    assert repository.get_by_id(availability.id) is None


def create_application_context(db_session: Session) -> tuple[int, int, int, int]:
    owner_id, parking_spot_id = create_owner_and_parking_spot(db_session)
    user_repository = UserRepository(db_session)
    applicant = user_repository.create(
        email="application.applicant@example.com",
        username="applicationapplicant",
        first_name="Application",
        last_name="Applicant",
        hashed_password="hashed-password",
        role=UserRole.EMPLOYEE,
    )
    start_at = datetime.now(UTC)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )
    return owner_id, parking_spot_id, availability.id, applicant.id


def test_parking_application_repository_create_and_get_by_id(db_session: Session) -> None:
    _, _, availability_id, applicant_id = create_application_context(db_session)
    repository = ParkingApplicationRepository(db_session)

    application = repository.create(
        availability_id=availability_id,
        applicant_id=applicant_id,
        note="Need parking for a client visit",
    )

    fetched = repository.get_by_id(application.id)

    assert fetched is not None
    assert fetched.availability_id == availability_id
    assert fetched.applicant_id == applicant_id
    assert fetched.status is ParkingApplicationStatus.PENDING
    assert fetched.note == "Need parking for a client visit"
    assert fetched.availability is not None
    assert fetched.applicant is not None


def test_parking_application_repository_missing_records_return_none(db_session: Session) -> None:
    repository = ParkingApplicationRepository(db_session)

    assert repository.get_by_id(999) is None
    assert repository.get_by_availability_and_applicant(availability_id=999, applicant_id=999) is None


def test_parking_application_repository_get_by_availability_and_applicant(db_session: Session) -> None:
    _, _, availability_id, applicant_id = create_application_context(db_session)
    repository = ParkingApplicationRepository(db_session)
    application = repository.create(availability_id=availability_id, applicant_id=applicant_id)

    fetched = repository.get_by_availability_and_applicant(
        availability_id=availability_id,
        applicant_id=applicant_id,
    )

    assert fetched is not None
    assert fetched.id == application.id


def test_parking_application_repository_list_methods(db_session: Session) -> None:
    owner_id, parking_spot_id, availability_id, applicant_id = create_application_context(db_session)
    user_repository = UserRepository(db_session)
    availability_repository = ParkingAvailabilityRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    start_at = datetime.now(UTC)
    second_availability = availability_repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at + timedelta(days=1),
        end_at=start_at + timedelta(days=1, hours=4),
    )
    other_applicant = user_repository.create(
        email="other.application.applicant@example.com",
        username="otherapplicationapplicant",
        first_name="Other",
        last_name="Applicant",
        hashed_password="hashed-password",
        role=UserRole.EMPLOYEE,
    )
    first = application_repository.create(
        availability_id=availability_id,
        applicant_id=applicant_id,
    )
    second = application_repository.create(
        availability_id=second_availability.id,
        applicant_id=applicant_id,
        status=ParkingApplicationStatus.CANCELLED,
    )
    third = application_repository.create(
        availability_id=availability_id,
        applicant_id=other_applicant.id,
    )

    assert [application.id for application in application_repository.list(skip=1, limit=1)] == [second.id]
    assert [application.id for application in application_repository.list(status=ParkingApplicationStatus.CANCELLED)] == [
        second.id,
    ]
    assert [
        application.id
        for application in application_repository.list(
            availability_id=availability_id,
            status=ParkingApplicationStatus.PENDING,
        )
    ] == [first.id, third.id]
    assert application_repository.list(
        availability_id=availability_id,
        status=ParkingApplicationStatus.CANCELLED,
    ) == []
    assert [application.id for application in application_repository.list_by_availability_id(availability_id)] == [
        first.id,
        third.id,
    ]
    assert [application.id for application in application_repository.list_by_applicant_id(applicant_id)] == [
        first.id,
        second.id,
    ]
    assert [
        application.id
        for application in application_repository.list_by_applicant_id(
            applicant_id,
            status=ParkingApplicationStatus.CANCELLED,
        )
    ] == [second.id]
    assert [
        application.id for application in application_repository.list_pending_by_availability_id(availability_id)
    ] == [
        first.id,
        third.id,
    ]


def test_parking_application_repository_update_changes_only_provided_fields(db_session: Session) -> None:
    _, _, availability_id, applicant_id = create_application_context(db_session)
    repository = ParkingApplicationRepository(db_session)
    application = repository.create(
        availability_id=availability_id,
        applicant_id=applicant_id,
        note="Original note",
    )

    updated = repository.update(
        application,
        {
            "status": ParkingApplicationStatus.SELECTED,
            "note": None,
            "unknown_field": "ignored",
        },
    )

    assert updated.status is ParkingApplicationStatus.SELECTED
    assert updated.note is None
    assert not hasattr(updated, "unknown_field")


def test_parking_application_repository_delete_removes_record(db_session: Session) -> None:
    _, _, availability_id, applicant_id = create_application_context(db_session)
    repository = ParkingApplicationRepository(db_session)
    application = repository.create(availability_id=availability_id, applicant_id=applicant_id)

    assert repository.delete(application) is True
    assert repository.get_by_id(application.id) is None


def test_parking_application_repository_prevents_duplicate_applicant_per_availability(
    db_session: Session,
) -> None:
    _, _, availability_id, applicant_id = create_application_context(db_session)
    repository = ParkingApplicationRepository(db_session)
    repository.create(availability_id=availability_id, applicant_id=applicant_id)
    db_session.commit()

    with pytest.raises(IntegrityError):
        repository.create(availability_id=availability_id, applicant_id=applicant_id)


def test_parking_application_repository_allows_same_applicant_for_different_availabilities(
    db_session: Session,
) -> None:
    owner_id, parking_spot_id, availability_id, applicant_id = create_application_context(db_session)
    availability_repository = ParkingAvailabilityRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    start_at = datetime.now(UTC)
    second_availability = availability_repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at + timedelta(days=1),
        end_at=start_at + timedelta(days=1, hours=4),
    )

    first = application_repository.create(availability_id=availability_id, applicant_id=applicant_id)
    second = application_repository.create(availability_id=second_availability.id, applicant_id=applicant_id)

    assert first.id is not None
    assert second.id is not None
    assert first.availability_id != second.availability_id


def test_parking_application_repository_allows_different_applicants_for_same_availability(
    db_session: Session,
) -> None:
    _, _, availability_id, applicant_id = create_application_context(db_session)
    other_applicant = UserRepository(db_session).create(
        email="other.application.applicant@example.com",
        username="otherapplicationapplicant",
        first_name="Other",
        last_name="Applicant",
        hashed_password="hashed-password",
        role=UserRole.EMPLOYEE,
    )
    repository = ParkingApplicationRepository(db_session)

    first = repository.create(availability_id=availability_id, applicant_id=applicant_id)
    second = repository.create(availability_id=availability_id, applicant_id=other_applicant.id)

    assert first.id is not None
    assert second.id is not None
    assert first.applicant_id != second.applicant_id


def create_reservation_context(db_session: Session, *, suffix: str = "one") -> tuple[int, int, int, int, int]:
    user_repository = UserRepository(db_session)
    parking_spot_repository = ParkingSpotRepository(db_session)
    availability_repository = ParkingAvailabilityRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    owner = user_repository.create(
        email=f"reservation.owner.{suffix}@example.com",
        username=f"reservationowner{suffix}",
        first_name="Reservation",
        last_name="Owner",
        hashed_password="hashed-password",
        role=UserRole.PARKING_OWNER,
    )
    applicant = user_repository.create(
        email=f"reservation.applicant.{suffix}@example.com",
        username=f"reservationapplicant{suffix}",
        first_name="Reservation",
        last_name="Applicant",
        hashed_password="hashed-password",
        role=UserRole.EMPLOYEE,
    )
    parking_spot = parking_spot_repository.create(code=f"R-{suffix}", owner_id=owner.id)
    start_at = datetime.now(UTC)
    availability = availability_repository.create(
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )
    application = application_repository.create(
        availability_id=availability.id,
        applicant_id=applicant.id,
        status=ParkingApplicationStatus.SELECTED,
    )
    return owner.id, parking_spot.id, availability.id, applicant.id, application.id


def test_parking_reservation_repository_create_and_get_by_id(db_session: Session) -> None:
    _, parking_spot_id, availability_id, applicant_id, application_id = create_reservation_context(db_session)
    repository = ParkingReservationRepository(db_session)
    start_at = datetime.now(UTC)
    end_at = start_at + timedelta(hours=4)

    reservation = repository.create(
        availability_id=availability_id,
        application_id=application_id,
        parking_spot_id=parking_spot_id,
        reserved_for_user_id=applicant_id,
        start_at=start_at,
        end_at=end_at,
    )

    fetched = repository.get_by_id(reservation.id)

    assert fetched is not None
    assert fetched.availability_id == availability_id
    assert fetched.application_id == application_id
    assert fetched.parking_spot_id == parking_spot_id
    assert fetched.reserved_for_user_id == applicant_id
    assert fetched.status is ParkingReservationStatus.ACTIVE
    assert fetched.availability is not None
    assert fetched.application is not None
    assert fetched.parking_spot is not None
    assert fetched.reserved_for_user is not None


def test_parking_reservation_repository_missing_records_return_none(db_session: Session) -> None:
    repository = ParkingReservationRepository(db_session)

    assert repository.get_by_id(999) is None
    assert repository.get_by_availability_id(999) is None
    assert repository.get_by_application_id(999) is None


def test_parking_reservation_repository_get_by_availability_and_application(
    db_session: Session,
) -> None:
    _, parking_spot_id, availability_id, applicant_id, application_id = create_reservation_context(db_session)
    repository = ParkingReservationRepository(db_session)
    start_at = datetime.now(UTC)
    reservation = repository.create(
        availability_id=availability_id,
        application_id=application_id,
        parking_spot_id=parking_spot_id,
        reserved_for_user_id=applicant_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )

    assert repository.get_by_availability_id(availability_id).id == reservation.id
    assert repository.get_by_application_id(application_id).id == reservation.id


def test_parking_reservation_repository_list_methods(db_session: Session) -> None:
    owner_id, parking_spot_id, availability_id, applicant_id, application_id = create_reservation_context(db_session)
    availability_repository = ParkingAvailabilityRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    repository = ParkingReservationRepository(db_session)
    start_at = datetime.now(UTC)
    first = repository.create(
        availability_id=availability_id,
        application_id=application_id,
        parking_spot_id=parking_spot_id,
        reserved_for_user_id=applicant_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )
    second_availability = availability_repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at + timedelta(days=1),
        end_at=start_at + timedelta(days=1, hours=4),
    )
    second_application = application_repository.create(
        availability_id=second_availability.id,
        applicant_id=applicant_id,
        status=ParkingApplicationStatus.SELECTED,
    )
    second = repository.create(
        availability_id=second_availability.id,
        application_id=second_application.id,
        parking_spot_id=parking_spot_id,
        reserved_for_user_id=applicant_id,
        start_at=start_at + timedelta(days=1),
        end_at=start_at + timedelta(days=1, hours=4),
        status=ParkingReservationStatus.COMPLETED,
    )
    _, other_spot_id, other_availability_id, other_applicant_id, other_application_id = create_reservation_context(
        db_session,
        suffix="two",
    )
    third = repository.create(
        availability_id=other_availability_id,
        application_id=other_application_id,
        parking_spot_id=other_spot_id,
        reserved_for_user_id=other_applicant_id,
        start_at=start_at + timedelta(days=2),
        end_at=start_at + timedelta(days=2, hours=4),
    )

    assert [reservation.id for reservation in repository.list(skip=1, limit=1)] == [second.id]
    assert [reservation.id for reservation in repository.list(status=ParkingReservationStatus.COMPLETED)] == [
        second.id,
    ]
    assert [reservation.id for reservation in repository.list_by_parking_spot_id(parking_spot_id)] == [
        first.id,
        second.id,
    ]
    assert [reservation.id for reservation in repository.list_by_reserved_for_user_id(applicant_id)] == [
        first.id,
        second.id,
    ]
    assert [reservation.id for reservation in repository.list_active_by_user_id(applicant_id)] == [first.id]
    assert [reservation.id for reservation in repository.list_active_by_parking_spot_id(parking_spot_id)] == [
        first.id,
    ]
    assert [reservation.id for reservation in repository.list_active_by_user_id(other_applicant_id)] == [third.id]


def test_parking_reservation_repository_update_changes_only_provided_fields(db_session: Session) -> None:
    _, parking_spot_id, availability_id, applicant_id, application_id = create_reservation_context(db_session)
    repository = ParkingReservationRepository(db_session)
    start_at = datetime.now(UTC)
    reservation = repository.create(
        availability_id=availability_id,
        application_id=application_id,
        parking_spot_id=parking_spot_id,
        reserved_for_user_id=applicant_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )

    updated = repository.update(
        reservation,
        {
            "status": ParkingReservationStatus.CANCELLED,
            "unknown_field": "ignored",
        },
    )

    assert updated.status is ParkingReservationStatus.CANCELLED
    assert not hasattr(updated, "unknown_field")


def test_parking_reservation_repository_delete_removes_record(db_session: Session) -> None:
    _, parking_spot_id, availability_id, applicant_id, application_id = create_reservation_context(db_session)
    repository = ParkingReservationRepository(db_session)
    start_at = datetime.now(UTC)
    reservation = repository.create(
        availability_id=availability_id,
        application_id=application_id,
        parking_spot_id=parking_spot_id,
        reserved_for_user_id=applicant_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )

    assert repository.delete(reservation) is True
    assert repository.get_by_id(reservation.id) is None


def test_parking_reservation_repository_prevents_duplicate_active_reservation_for_same_availability(
    db_session: Session,
) -> None:
    _, parking_spot_id, availability_id, applicant_id, application_id = create_reservation_context(db_session)
    repository = ParkingReservationRepository(db_session)
    start_at = datetime.now(UTC)
    repository.create(
        availability_id=availability_id,
        application_id=application_id,
        parking_spot_id=parking_spot_id,
        reserved_for_user_id=applicant_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )
    db_session.commit()

    with pytest.raises(IntegrityError):
        repository.create(
            availability_id=availability_id,
            application_id=None,
            parking_spot_id=parking_spot_id,
            reserved_for_user_id=applicant_id,
            start_at=start_at + timedelta(days=1),
            end_at=start_at + timedelta(days=1, hours=4),
        )


def test_parking_reservation_repository_preserves_history_and_returns_current_active_reservation(
    db_session: Session,
) -> None:
    _, parking_spot_id, availability_id, applicant_id, application_id = create_reservation_context(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    user_repository = UserRepository(db_session)
    repository = ParkingReservationRepository(db_session)
    start_at = datetime.now(UTC)
    cancelled = repository.create(
        availability_id=availability_id,
        application_id=application_id,
        parking_spot_id=parking_spot_id,
        reserved_for_user_id=applicant_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
        status=ParkingReservationStatus.CANCELLED,
    )
    replacement_applicant = user_repository.create(
        email="reservation.history@example.com",
        username="reservationhistory",
        first_name="Reservation",
        last_name="History",
        hashed_password="hashed-password",
        role=UserRole.EMPLOYEE,
    )
    replacement_application = application_repository.create(
        availability_id=availability_id,
        applicant_id=replacement_applicant.id,
        status=ParkingApplicationStatus.SELECTED,
    )
    active = repository.create(
        availability_id=availability_id,
        application_id=replacement_application.id,
        parking_spot_id=parking_spot_id,
        reserved_for_user_id=replacement_applicant.id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )

    assert repository.get_by_availability_id(availability_id).id == active.id
    assert repository.get_active_by_availability_id(availability_id).id == active.id
    assert repository.get_latest_cancelled_by_availability_id(availability_id).id == cancelled.id
    assert [reservation.id for reservation in repository.list_by_availability_id(availability_id)] == [
        active.id,
        cancelled.id,
    ]


def test_parking_reservation_repository_lists_filtered_history_newest_first(
    db_session: Session,
) -> None:
    _, parking_spot_id, availability_id, applicant_id, application_id = create_reservation_context(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    user_repository = UserRepository(db_session)
    repository = ParkingReservationRepository(db_session)
    start_at = datetime.now(UTC)
    cancelled = repository.create(
        availability_id=availability_id,
        application_id=application_id,
        parking_spot_id=parking_spot_id,
        reserved_for_user_id=applicant_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
        status=ParkingReservationStatus.CANCELLED,
    )
    current_user = user_repository.create(
        email="reservation.current.history@example.com",
        username="reservationcurrenthistory",
        first_name="Reservation",
        last_name="Current",
        hashed_password="hashed-password",
        role=UserRole.EMPLOYEE,
    )
    current_application = application_repository.create(
        availability_id=availability_id,
        applicant_id=current_user.id,
        status=ParkingApplicationStatus.SELECTED,
    )
    active = repository.create(
        availability_id=availability_id,
        application_id=current_application.id,
        parking_spot_id=parking_spot_id,
        reserved_for_user_id=current_user.id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )
    _, other_spot_id, other_availability_id, other_applicant_id, other_application_id = create_reservation_context(
        db_session,
        suffix="history-filter-other",
    )
    other = repository.create(
        availability_id=other_availability_id,
        application_id=other_application_id,
        parking_spot_id=other_spot_id,
        reserved_for_user_id=other_applicant_id,
        start_at=start_at + timedelta(days=1),
        end_at=start_at + timedelta(days=1, hours=4),
        status=ParkingReservationStatus.COMPLETED,
    )

    assert [reservation.id for reservation in repository.list_history(availability_id=availability_id)] == [
        active.id,
        cancelled.id,
    ]
    assert [
        reservation.id
        for reservation in repository.list_history(
            availability_id=availability_id,
            current_active=True,
        )
    ] == [active.id]
    assert [
        reservation.id
        for reservation in repository.list_history(
            availability_id=availability_id,
            current_active=False,
        )
    ] == [cancelled.id]
    assert [
        reservation.id
        for reservation in repository.list_history(
            status=ParkingReservationStatus.COMPLETED,
            reserved_for_user_id=other_applicant_id,
            parking_spot_id=other_spot_id,
        )
    ] == [other.id]


def test_parking_reservation_repository_prevents_duplicate_reservation_for_same_application(
    db_session: Session,
) -> None:
    owner_id, parking_spot_id, availability_id, applicant_id, application_id = create_reservation_context(db_session)
    availability_repository = ParkingAvailabilityRepository(db_session)
    repository = ParkingReservationRepository(db_session)
    start_at = datetime.now(UTC)
    repository.create(
        availability_id=availability_id,
        application_id=application_id,
        parking_spot_id=parking_spot_id,
        reserved_for_user_id=applicant_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )
    second_availability = availability_repository.create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start_at + timedelta(days=1),
        end_at=start_at + timedelta(days=1, hours=4),
    )
    db_session.commit()

    with pytest.raises(IntegrityError):
        repository.create(
            availability_id=second_availability.id,
            application_id=application_id,
            parking_spot_id=parking_spot_id,
            reserved_for_user_id=applicant_id,
            start_at=start_at + timedelta(days=1),
            end_at=start_at + timedelta(days=1, hours=4),
        )

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_spot import ParkingSpot
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.teams import TeamRepository
from app.repositories.users import UserRepository
from app.schemas.parking_application import ParkingApplicationCreate
from app.services.parking_applications import (
    ParkingApplicationAvailabilityExpiredError,
    ParkingApplicationAvailabilityNotFoundError,
    ParkingApplicationAvailabilityNotOpenError,
    ParkingApplicationDuplicateError,
    ParkingApplicationInactiveApplicantError,
    ParkingApplicationOwnerCannotApplyError,
    ParkingApplicationPermissionError,
    ParkingApplicationService,
    ParkingApplicationStatusTransitionError,
)

TEST_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def service(db_session: Session) -> ParkingApplicationService:
    return ParkingApplicationService(
        application_repository=ParkingApplicationRepository(db_session),
        availability_repository=ParkingAvailabilityRepository(db_session),
        now_provider=lambda: TEST_NOW,
    )


def create_user(
    db_session: Session,
    *,
    email: str,
    username: str,
    role: UserRole = UserRole.EMPLOYEE,
    is_active: bool = True,
    team_id: int | None = None,
) -> User:
    return UserRepository(db_session).create(
        email=email,
        username=username,
        first_name="Test",
        last_name="User",
        hashed_password="hashed-password",
        role=role,
        is_active=is_active,
        team_id=team_id,
    )


def create_owner(db_session: Session, *, team_id: int | None = None) -> User:
    return create_user(
        db_session,
        email="owner@example.com",
        username="owner",
        role=UserRole.PARKING_OWNER,
        team_id=team_id,
    )


def create_applicant(
    db_session: Session,
    *,
    email: str = "employee@example.com",
    username: str = "employee",
    is_active: bool = True,
    team_id: int | None = None,
) -> User:
    return create_user(
        db_session,
        email=email,
        username=username,
        is_active=is_active,
        team_id=team_id,
    )


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


def create_availability(
    db_session: Session,
    *,
    owner_id: int,
    parking_spot_id: int,
    status: ParkingAvailabilityStatus = ParkingAvailabilityStatus.OPEN,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    priority_until: datetime | None = None,
) -> ParkingAvailability:
    start = start_at or TEST_NOW + timedelta(hours=1)
    end = end_at or TEST_NOW + timedelta(hours=5)
    return ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start,
        end_at=end,
        status=status,
        priority_until=priority_until,
    )


def create_open_availability_context(db_session: Session) -> tuple[User, User, ParkingAvailability]:
    owner = create_owner(db_session)
    applicant = create_applicant(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, owner_id=owner.id, parking_spot_id=parking_spot.id)
    return owner, applicant, availability


def application_create(availability_id: int) -> ParkingApplicationCreate:
    return ParkingApplicationCreate(availability_id=availability_id, note="Need parking for a client visit")


def create_application(
    db_session: Session,
    *,
    availability_id: int,
    applicant_id: int,
    status: ParkingApplicationStatus = ParkingApplicationStatus.PENDING,
) -> ParkingApplication:
    return ParkingApplicationRepository(db_session).create(
        availability_id=availability_id,
        applicant_id=applicant_id,
        status=status,
        note="Existing application",
    )


def test_authenticated_user_can_apply_for_open_future_availability(
    service: ParkingApplicationService,
    db_session: Session,
) -> None:
    _, applicant, availability = create_open_availability_context(db_session)

    application = service.apply_for_availability(application_create(availability.id), applicant)

    assert application.availability_id == availability.id
    assert application.applicant_id == applicant.id
    assert application.status is ParkingApplicationStatus.PENDING
    assert application.note == "Need parking for a client visit"


def test_applying_to_missing_availability_raises_clean_error(
    service: ParkingApplicationService,
    db_session: Session,
) -> None:
    applicant = create_applicant(db_session)

    with pytest.raises(ParkingApplicationAvailabilityNotFoundError):
        service.apply_for_availability(application_create(999), applicant)


def test_applying_to_non_open_availability_is_rejected(
    service: ParkingApplicationService,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    applicant = create_applicant(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(
        db_session,
        owner_id=owner.id,
        parking_spot_id=parking_spot.id,
        status=ParkingAvailabilityStatus.ASSIGNED,
    )

    with pytest.raises(ParkingApplicationAvailabilityNotOpenError):
        service.apply_for_availability(application_create(availability.id), applicant)


def test_applying_to_expired_availability_is_rejected(
    service: ParkingApplicationService,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    applicant = create_applicant(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(
        db_session,
        owner_id=owner.id,
        parking_spot_id=parking_spot.id,
        end_at=TEST_NOW - timedelta(minutes=1),
    )

    with pytest.raises(ParkingApplicationAvailabilityExpiredError):
        service.apply_for_availability(application_create(availability.id), applicant)


def test_owner_cannot_apply_to_own_availability(service: ParkingApplicationService, db_session: Session) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, owner_id=owner.id, parking_spot_id=parking_spot.id)

    with pytest.raises(ParkingApplicationOwnerCannotApplyError):
        service.apply_for_availability(application_create(availability.id), owner)


def test_duplicate_application_is_rejected(service: ParkingApplicationService, db_session: Session) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    with pytest.raises(ParkingApplicationDuplicateError):
        service.apply_for_availability(application_create(availability.id), applicant)


def test_inactive_applicant_cannot_apply(service: ParkingApplicationService, db_session: Session) -> None:
    owner = create_owner(db_session)
    applicant = create_applicant(db_session, is_active=False)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, owner_id=owner.id, parking_spot_id=parking_spot.id)

    with pytest.raises(ParkingApplicationInactiveApplicantError):
        service.apply_for_availability(application_create(availability.id), applicant)


def test_non_team_applicant_can_apply_during_priority_window(
    service: ParkingApplicationService,
    db_session: Session,
) -> None:
    team_repository = TeamRepository(db_session)
    owner_team = team_repository.create(name="Engineering")
    applicant_team = team_repository.create(name="Finance")
    owner = create_owner(db_session, team_id=owner_team.id)
    applicant = create_applicant(db_session, team_id=applicant_team.id)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(
        db_session,
        owner_id=owner.id,
        parking_spot_id=parking_spot.id,
        priority_until=TEST_NOW + timedelta(hours=2),
    )

    application = service.apply_for_availability(application_create(availability.id), applicant)

    assert application.id is not None
    assert application.applicant_id == applicant.id


def test_authenticated_user_can_list_own_applications_with_status_filter(
    service: ParkingApplicationService,
    db_session: Session,
) -> None:
    owner, applicant, availability = create_open_availability_context(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id, code="B-01")
    second_availability = create_availability(
        db_session,
        owner_id=owner.id,
        parking_spot_id=parking_spot.id,
        start_at=TEST_NOW + timedelta(days=1),
        end_at=TEST_NOW + timedelta(days=1, hours=4),
    )
    pending = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)
    cancelled = create_application(
        db_session,
        availability_id=second_availability.id,
        applicant_id=applicant.id,
        status=ParkingApplicationStatus.CANCELLED,
    )

    all_applications = service.list_my_applications(applicant)
    filtered_applications = service.list_my_applications(applicant, status=ParkingApplicationStatus.CANCELLED)

    assert [application.id for application in all_applications] == [pending.id, cancelled.id]
    assert [application.id for application in filtered_applications] == [cancelled.id]


def test_authenticated_user_and_admin_can_view_allowed_applications(
    service: ParkingApplicationService,
    db_session: Session,
) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    admin = create_admin(db_session)
    application = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    assert service.get_application_for_user(application.id, applicant).id == application.id
    assert service.get_application_for_user(application.id, admin).id == application.id


def test_non_applicant_cannot_view_another_users_application(
    service: ParkingApplicationService,
    db_session: Session,
) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    other_user = create_applicant(db_session, email="other@example.com", username="other")
    application = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    with pytest.raises(ParkingApplicationPermissionError):
        service.get_application_for_user(application.id, other_user)


def test_applicant_can_cancel_pending_application(service: ParkingApplicationService, db_session: Session) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    application = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    cancelled = service.cancel_my_application(application.id, applicant)

    assert cancelled.status is ParkingApplicationStatus.CANCELLED
    assert ParkingApplicationRepository(db_session).get_by_id(application.id) is not None


def test_applicant_cannot_cancel_non_pending_application(
    service: ParkingApplicationService,
    db_session: Session,
) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=applicant.id,
        status=ParkingApplicationStatus.SELECTED,
    )

    with pytest.raises(ParkingApplicationStatusTransitionError):
        service.cancel_my_application(application.id, applicant)


def test_user_cannot_cancel_another_users_application(
    service: ParkingApplicationService,
    db_session: Session,
) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    other_user = create_applicant(db_session, email="other@example.com", username="other")
    application = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    with pytest.raises(ParkingApplicationPermissionError):
        service.cancel_my_application(application.id, other_user)

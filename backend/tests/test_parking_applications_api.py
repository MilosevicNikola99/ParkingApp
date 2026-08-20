from collections.abc import Generator
from datetime import UTC, datetime, timedelta
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_spot import ParkingSpot
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.teams import TeamRepository
from app.repositories.users import UserRepository


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def app_with_db(db_session: Session) -> Generator[FastAPI, None, None]:
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
def client(app_with_db: FastAPI) -> TestClient:
    return TestClient(app_with_db)


def create_test_user(
    db_session: Session,
    *,
    email: str,
    username: str,
    role: UserRole = UserRole.EMPLOYEE,
    is_active: bool = True,
    team_id: int | None = None,
) -> User:
    user = UserRepository(db_session).create(
        email=email,
        username=username,
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("valid-password"),
        role=role,
        is_active=is_active,
        team_id=team_id,
    )
    db_session.commit()
    return user


def create_owner(db_session: Session, *, team_id: int | None = None) -> User:
    return create_test_user(
        db_session,
        email="owner@example.com",
        username="owner",
        role=UserRole.PARKING_OWNER,
        team_id=team_id,
    )


def create_employee(
    db_session: Session,
    *,
    email: str = "employee@example.com",
    username: str = "employee",
    is_active: bool = True,
    team_id: int | None = None,
) -> User:
    return create_test_user(
        db_session,
        email=email,
        username=username,
        is_active=is_active,
        team_id=team_id,
    )


def create_admin(db_session: Session) -> User:
    return create_test_user(db_session, email="admin@example.com", username="admin", role=UserRole.ADMIN)


def create_parking_spot(
    db_session: Session,
    *,
    owner_id: int,
    code: str = "A-12",
    is_active: bool = True,
) -> ParkingSpot:
    parking_spot = ParkingSpotRepository(db_session).create(
        code=code,
        location="Garage P1",
        owner_id=owner_id,
        is_active=is_active,
    )
    db_session.commit()
    return parking_spot


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
    start = start_at or datetime.now(UTC) + timedelta(hours=1)
    end = end_at or start + timedelta(hours=4)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start,
        end_at=end,
        status=status,
        priority_until=priority_until,
    )
    db_session.commit()
    return availability


def create_application(
    db_session: Session,
    *,
    availability_id: int,
    applicant_id: int,
    status: ParkingApplicationStatus = ParkingApplicationStatus.PENDING,
) -> ParkingApplication:
    application = ParkingApplicationRepository(db_session).create(
        availability_id=availability_id,
        applicant_id=applicant_id,
        status=status,
        note="Existing application",
    )
    db_session.commit()
    return application


def create_open_availability_context(db_session: Session) -> tuple[User, User, ParkingAvailability]:
    owner = create_owner(db_session)
    applicant = create_employee(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, owner_id=owner.id, parking_spot_id=parking_spot.id)
    return owner, applicant, availability


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def application_payload(availability_id: int) -> dict[str, int | str]:
    return {
        "availability_id": availability_id,
        "note": "Need parking for a client visit",
    }


def assert_no_sensitive_fields(payload: dict[str, object]) -> None:
    assert payload["availability"]["parking_spot"]["code"]
    assert payload["applicant"]["email"]
    serialized_payload = json.dumps(payload)
    assert "hashed_password" not in serialized_payload
    assert "password" not in serialized_payload


def test_authenticated_user_can_apply_for_open_future_availability(
    client: TestClient,
    db_session: Session,
) -> None:
    _, applicant, availability = create_open_availability_context(db_session)

    response = client.post(
        "/parking-applications",
        json=application_payload(availability.id),
        headers=bearer_header(applicant),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["availability_id"] == availability.id
    assert body["applicant_id"] == applicant.id
    assert body["status"] == "pending"
    assert body["note"] == "Need parking for a client visit"
    assert_no_sensitive_fields(body)


def test_applying_to_missing_availability_returns_404(client: TestClient, db_session: Session) -> None:
    applicant = create_employee(db_session)

    response = client.post(
        "/parking-applications",
        json=application_payload(999),
        headers=bearer_header(applicant),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking availability not found"}


def test_applying_to_non_open_availability_returns_409(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    applicant = create_employee(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(
        db_session,
        owner_id=owner.id,
        parking_spot_id=parking_spot.id,
        status=ParkingAvailabilityStatus.ASSIGNED,
    )

    response = client.post(
        "/parking-applications",
        json=application_payload(availability.id),
        headers=bearer_header(applicant),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking availability is not open"}


def test_applying_to_expired_availability_returns_409(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    applicant = create_employee(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(
        db_session,
        owner_id=owner.id,
        parking_spot_id=parking_spot.id,
        start_at=datetime.now(UTC) - timedelta(hours=4),
        end_at=datetime.now(UTC) - timedelta(hours=1),
    )

    response = client.post(
        "/parking-applications",
        json=application_payload(availability.id),
        headers=bearer_header(applicant),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking availability has expired"}


def test_owner_cannot_apply_to_own_availability(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, owner_id=owner.id, parking_spot_id=parking_spot.id)

    response = client.post(
        "/parking-applications",
        json=application_payload(availability.id),
        headers=bearer_header(owner),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_duplicate_application_returns_409(client: TestClient, db_session: Session) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    response = client.post(
        "/parking-applications",
        json=application_payload(availability.id),
        headers=bearer_header(applicant),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking application already exists"}


def test_inactive_applicant_cannot_apply_through_current_user_dependency(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    inactive_applicant = create_employee(db_session, is_active=False)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, owner_id=owner.id, parking_spot_id=parking_spot.id)

    response = client.post(
        "/parking-applications",
        json=application_payload(availability.id),
        headers=bearer_header(inactive_applicant),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_non_team_applicant_can_apply_during_priority_window(client: TestClient, db_session: Session) -> None:
    team_repository = TeamRepository(db_session)
    owner_team = team_repository.create(name="Engineering")
    applicant_team = team_repository.create(name="Finance")
    db_session.commit()
    owner = create_owner(db_session, team_id=owner_team.id)
    applicant = create_employee(db_session, team_id=applicant_team.id)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(
        db_session,
        owner_id=owner.id,
        parking_spot_id=parking_spot.id,
        priority_until=datetime.now(UTC) + timedelta(hours=2),
    )

    response = client.post(
        "/parking-applications",
        json=application_payload(availability.id),
        headers=bearer_header(applicant),
    )

    assert response.status_code == 201
    assert response.json()["applicant_id"] == applicant.id


def test_authenticated_user_can_list_own_applications_with_status_filter(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, applicant, availability = create_open_availability_context(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id, code="B-01")
    second_availability = create_availability(
        db_session,
        owner_id=owner.id,
        parking_spot_id=parking_spot.id,
        start_at=datetime.now(UTC) + timedelta(days=1),
    )
    pending = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)
    cancelled = create_application(
        db_session,
        availability_id=second_availability.id,
        applicant_id=applicant.id,
        status=ParkingApplicationStatus.CANCELLED,
    )

    all_response = client.get("/parking-applications/my", headers=bearer_header(applicant))
    filtered_response = client.get("/parking-applications/my?status=cancelled", headers=bearer_header(applicant))

    assert all_response.status_code == 200
    assert filtered_response.status_code == 200
    assert [application["id"] for application in all_response.json()] == [pending.id, cancelled.id]
    assert [application["id"] for application in filtered_response.json()] == [cancelled.id]


def test_authenticated_user_can_view_own_application(client: TestClient, db_session: Session) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    application = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    response = client.get(f"/parking-applications/{application.id}", headers=bearer_header(applicant))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == application.id
    assert_no_sensitive_fields(body)


def test_admin_can_view_any_application(client: TestClient, db_session: Session) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    admin = create_admin(db_session)
    application = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    response = client.get(f"/parking-applications/{application.id}", headers=bearer_header(admin))

    assert response.status_code == 200
    assert response.json()["id"] == application.id


def test_non_applicant_cannot_view_another_users_application(client: TestClient, db_session: Session) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    other_user = create_employee(db_session, email="other@example.com", username="other")
    application = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    response = client.get(f"/parking-applications/{application.id}", headers=bearer_header(other_user))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_applicant_can_cancel_pending_application(client: TestClient, db_session: Session) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    application = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    response = client.patch(f"/parking-applications/{application.id}/cancel", headers=bearer_header(applicant))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert ParkingApplicationRepository(db_session).get_by_id(application.id) is not None


def test_applicant_cannot_cancel_non_pending_application(client: TestClient, db_session: Session) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=applicant.id,
        status=ParkingApplicationStatus.SELECTED,
    )

    response = client.patch(f"/parking-applications/{application.id}/cancel", headers=bearer_header(applicant))

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking application cannot be cancelled"}


def test_user_cannot_cancel_another_users_application(client: TestClient, db_session: Session) -> None:
    _, applicant, availability = create_open_availability_context(db_session)
    other_user = create_employee(db_session, email="other@example.com", username="other")
    application = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    response = client.patch(f"/parking-applications/{application.id}/cancel", headers=bearer_header(other_user))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_missing_application_returns_404(client: TestClient, db_session: Session) -> None:
    applicant = create_employee(db_session)

    response = client.get("/parking-applications/999", headers=bearer_header(applicant))

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking application not found"}


def test_missing_token_returns_401(client: TestClient) -> None:
    response = client.get("/parking-applications/my")

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_invalid_token_returns_401(client: TestClient) -> None:
    response = client.get("/parking-applications/my", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}

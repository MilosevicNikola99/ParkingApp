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
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_availability import ParkingAvailability
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.users import UserRepository

TEST_NOW = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)


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


def create_user(
    db_session: Session,
    suffix: str,
    *,
    role: UserRole = UserRole.EMPLOYEE,
) -> User:
    return UserRepository(db_session).create(
        email=f"admin.applications.{suffix}@example.com",
        username=f"adminapplications{suffix}",
        first_name="Admin",
        last_name="Applications",
        hashed_password="hashed-password",
        role=role,
    )


def create_availability(db_session: Session, suffix: str, *, start_offset_days: int = 0) -> ParkingAvailability:
    owner = create_user(db_session, f"owner{suffix}", role=UserRole.PARKING_OWNER)
    spot = ParkingSpotRepository(db_session).create(code=f"APL-{suffix}", owner_id=owner.id)
    start_at = TEST_NOW + timedelta(days=start_offset_days, hours=1)
    return ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=spot.id,
        owner_id=owner.id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=8),
    )


def create_application(
    db_session: Session,
    availability: ParkingAvailability,
    suffix: str,
    *,
    status: ParkingApplicationStatus = ParkingApplicationStatus.PENDING,
) -> ParkingApplication:
    applicant = create_user(db_session, suffix)
    return ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=applicant.id,
        status=status,
        note=f"Application {suffix}",
    )


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def assert_safe_application_response(payload: dict[str, object]) -> None:
    assert set(payload) == {
        "id",
        "availability_id",
        "applicant_id",
        "status",
        "note",
        "created_at",
        "updated_at",
    }
    serialized_payload = json.dumps(payload)
    assert "applicant" not in payload
    assert "hashed_password" not in serialized_payload
    assert "password" not in serialized_payload
    assert "token" not in serialized_payload


def test_admin_can_list_parking_applications(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    availability = create_availability(db_session, "one")
    first = create_application(db_session, availability, "first")
    second = create_application(
        db_session,
        availability,
        "second",
        status=ParkingApplicationStatus.CANCELLED,
    )

    response = client.get("/admin/parking-applications", headers=bearer_header(admin))

    assert response.status_code == 200
    body = response.json()
    assert [application["id"] for application in body] == [first.id, second.id]
    for application in body:
        assert_safe_application_response(application)


def test_admin_can_filter_applications_by_availability_and_status(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    target_availability = create_availability(db_session, "target")
    other_availability = create_availability(db_session, "other", start_offset_days=1)
    target_pending = create_application(db_session, target_availability, "targetpending")
    create_application(
        db_session,
        target_availability,
        "targetcancelled",
        status=ParkingApplicationStatus.CANCELLED,
    )
    create_application(db_session, other_availability, "otherpending")

    response = client.get(
        (
            "/admin/parking-applications"
            f"?availability_id={target_availability.id}&status={ParkingApplicationStatus.PENDING.value}"
        ),
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    assert [application["id"] for application in response.json()] == [target_pending.id]


def test_admin_can_paginate_parking_applications(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    availability = create_availability(db_session, "pagination")
    first = create_application(db_session, availability, "first")
    second = create_application(db_session, availability, "second")

    response = client.get(
        "/admin/parking-applications?skip=1&limit=1",
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    assert first.id != second.id
    assert [application["id"] for application in response.json()] == [second.id]


@pytest.mark.parametrize(
    "query",
    [
        "?availability_id=0",
        "?skip=-1",
        "?limit=0",
        "?limit=1001",
        "?status=unknown",
    ],
)
def test_invalid_filters_return_422(
    client: TestClient,
    db_session: Session,
    query: str,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    response = client.get(f"/admin/parking-applications{query}", headers=bearer_header(admin))

    assert response.status_code == 422


@pytest.mark.parametrize("role", [UserRole.EMPLOYEE, UserRole.PARKING_OWNER])
def test_non_admin_receives_403(client: TestClient, db_session: Session, role: UserRole) -> None:
    user = create_user(db_session, role.value, role=role)

    response = client.get("/admin/parking-applications", headers=bearer_header(user))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer invalid-token"},
    ],
)
def test_missing_or_invalid_token_returns_401(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get("/admin/parking-applications", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_admin_application_list_is_registered_with_bearer_security(app_with_db: FastAPI) -> None:
    operation = app_with_db.openapi()["paths"]["/admin/parking-applications"]["get"]

    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert "200" in operation["responses"]
    assert "422" in operation["responses"]

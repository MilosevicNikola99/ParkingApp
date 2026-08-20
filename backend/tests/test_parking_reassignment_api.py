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
from app.models.parking_assignment_audit_log import ParkingAssignmentTriggerSource
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.users import UserRepository

TEST_NOW = datetime.now(UTC)


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
        email=f"reassignment.api.{suffix}@example.com",
        username=f"reassignmentapi{suffix}",
        first_name="Reassignment",
        last_name="API",
        hashed_password="hashed-password",
        role=role,
    )


def create_application(
    db_session: Session,
    availability: ParkingAvailability,
    suffix: str,
    *,
    status: ParkingApplicationStatus,
) -> ParkingApplication:
    applicant = create_user(db_session, suffix)
    return ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=applicant.id,
        status=status,
    )


def create_cancelled_context(
    db_session: Session,
    suffix: str,
    *,
    availability_status: ParkingAvailabilityStatus = ParkingAvailabilityStatus.OPEN,
    end_at: datetime | None = None,
) -> tuple[User, ParkingAvailability, ParkingReservation]:
    owner = create_user(db_session, f"owner{suffix}", role=UserRole.PARKING_OWNER)
    previous_user = create_user(db_session, f"previous{suffix}")
    spot = ParkingSpotRepository(db_session).create(code=f"REAPI-{suffix}", owner_id=owner.id)
    resolved_end_at = end_at or TEST_NOW + timedelta(hours=8)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=spot.id,
        owner_id=owner.id,
        start_at=resolved_end_at - timedelta(hours=4),
        end_at=resolved_end_at,
        status=availability_status,
    )
    previous_application = ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=previous_user.id,
        status=ParkingApplicationStatus.CANCELLED,
    )
    previous_reservation = ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=previous_application.id,
        parking_spot_id=spot.id,
        reserved_for_user_id=previous_user.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
        status=ParkingReservationStatus.CANCELLED,
    )
    return owner, availability, previous_reservation


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def endpoint(availability_id: int) -> str:
    return f"/parking-availabilities/{availability_id}/reassign"


def assert_safe_reservation_response(payload: dict[str, object]) -> None:
    assert set(payload) == {
        "id",
        "availability_id",
        "application_id",
        "parking_spot_id",
        "reserved_for_user_id",
        "start_at",
        "end_at",
        "status",
        "created_at",
        "updated_at",
        "parking_spot",
        "reserved_for_user",
    }
    serialized_payload = json.dumps(payload)
    assert "audit" not in serialized_payload
    assert "reason" not in serialized_payload
    assert "password" not in serialized_payload
    assert "token" not in serialized_payload


def test_owner_can_explicitly_reassign_after_cancellation(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, availability, previous_reservation = create_cancelled_context(db_session, "owner")
    first = create_application(db_session, availability, "first", status=ParkingApplicationStatus.PENDING)
    second = create_application(db_session, availability, "second", status=ParkingApplicationStatus.PENDING)

    response = client.post(
        endpoint(availability.id),
        json={"reason": "  Reassign requested  "},
        headers=bearer_header(owner),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] != previous_reservation.id
    assert body["application_id"] == first.id
    assert body["status"] == ParkingReservationStatus.ACTIVE.value
    assert_safe_reservation_response(body)
    assert ParkingApplicationRepository(db_session).get_by_id(first.id).status is ParkingApplicationStatus.SELECTED
    assert ParkingApplicationRepository(db_session).get_by_id(second.id).status is ParkingApplicationStatus.REJECTED
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability.id).status is (
        ParkingAvailabilityStatus.ASSIGNED
    )
    history = ParkingReservationRepository(db_session).list_by_availability_id(availability.id)
    assert [reservation.id for reservation in history] == [body["id"], previous_reservation.id]
    assert history[1].status is ParkingReservationStatus.CANCELLED
    audit_log = ParkingAssignmentAuditLogRepository(db_session).get_by_availability_id(availability.id)
    assert audit_log is not None
    assert audit_log.trigger_source is ParkingAssignmentTriggerSource.MANUAL_OWNER
    assert audit_log.ranking_details[0]["action"] == "reassignment"
    assert audit_log.ranking_details[0]["reason"] == "Reassign requested"
    assert audit_log.ranking_details[0]["actor_user_id"] == owner.id
    assert audit_log.ranking_details[0]["previous_reservation_id"] == previous_reservation.id


def test_admin_can_reassign_without_request_body(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _ = create_cancelled_context(db_session, "admin")
    application = create_application(db_session, availability, "applicant", status=ParkingApplicationStatus.PENDING)

    response = client.post(endpoint(availability.id), headers=bearer_header(admin))

    assert response.status_code == 201
    assert response.json()["application_id"] == application.id
    audit_log = ParkingAssignmentAuditLogRepository(db_session).get_by_availability_id(availability.id)
    assert audit_log is not None
    assert audit_log.trigger_source is ParkingAssignmentTriggerSource.MANUAL_ADMIN
    assert audit_log.ranking_details[0]["reason"] is None
    assert audit_log.ranking_details[0]["actor_user_id"] == admin.id


def test_unrelated_user_cannot_reassign(client: TestClient, db_session: Session) -> None:
    unrelated = create_user(db_session, "unrelated")
    _, availability, _ = create_cancelled_context(db_session, "forbidden")
    create_application(db_session, availability, "applicant", status=ParkingApplicationStatus.PENDING)

    response = client.post(endpoint(availability.id), json={}, headers=bearer_header(unrelated))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_missing_availability_returns_404(client: TestClient, db_session: Session) -> None:
    owner = create_user(db_session, "owner", role=UserRole.PARKING_OWNER)

    response = client.post(endpoint(999), json={}, headers=bearer_header(owner))

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking availability not found"}


def test_non_open_and_expired_availability_return_409(client: TestClient, db_session: Session) -> None:
    assigned_owner, assigned, _ = create_cancelled_context(
        db_session,
        "assigned",
        availability_status=ParkingAvailabilityStatus.ASSIGNED,
    )
    expired_owner, expired, _ = create_cancelled_context(
        db_session,
        "expired",
        end_at=TEST_NOW - timedelta(minutes=1),
    )
    assigned_id = assigned.id
    expired_id = expired.id
    assigned_owner_id = assigned_owner.id
    expired_owner_id = expired_owner.id
    db_session.commit()

    assigned_response = client.post(
        endpoint(assigned_id),
        json={},
        headers=bearer_header(UserRepository(db_session).get_by_id(assigned_owner_id)),
    )
    expired_response = client.post(
        endpoint(expired_id),
        json={},
        headers=bearer_header(UserRepository(db_session).get_by_id(expired_owner_id)),
    )

    assert assigned_response.status_code == 409
    assert assigned_response.json() == {"detail": "Parking availability is not open"}
    assert expired_response.status_code == 409
    assert expired_response.json() == {"detail": "Parking availability has expired"}


def test_active_reservation_and_no_pending_applications_return_409(
    client: TestClient,
    db_session: Session,
) -> None:
    active_owner, active_availability, _ = create_cancelled_context(db_session, "active")
    active_application = create_application(
        db_session,
        active_availability,
        "activeapplicant",
        status=ParkingApplicationStatus.SELECTED,
    )
    ParkingReservationRepository(db_session).create(
        availability_id=active_availability.id,
        application_id=active_application.id,
        parking_spot_id=active_availability.parking_spot_id,
        reserved_for_user_id=active_application.applicant_id,
        start_at=active_availability.start_at,
        end_at=active_availability.end_at,
    )
    no_pending_owner, no_pending_availability, _ = create_cancelled_context(db_session, "nopending")
    active_availability_id = active_availability.id
    no_pending_availability_id = no_pending_availability.id
    active_owner_id = active_owner.id
    no_pending_owner_id = no_pending_owner.id
    db_session.commit()

    active_response = client.post(
        endpoint(active_availability_id),
        json={},
        headers=bearer_header(UserRepository(db_session).get_by_id(active_owner_id)),
    )
    no_pending_response = client.post(
        endpoint(no_pending_availability_id),
        json={},
        headers=bearer_header(UserRepository(db_session).get_by_id(no_pending_owner_id)),
    )

    assert active_response.status_code == 409
    assert active_response.json() == {"detail": "Active parking reservation already exists"}
    assert no_pending_response.status_code == 409
    assert no_pending_response.json() == {"detail": "No pending parking applications"}


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer invalid-token"},
    ],
)
def test_missing_or_invalid_token_returns_401(client: TestClient, headers: dict[str, str]) -> None:
    response = client.post(endpoint(1), json={}, headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_reassignment_endpoint_is_registered_with_bearer_security(app_with_db: FastAPI) -> None:
    operation = app_with_db.openapi()["paths"]["/parking-availabilities/{availability_id}/reassign"]["post"]

    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert "201" in operation["responses"]
    assert "422" in operation["responses"]

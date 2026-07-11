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
        email=f"cancellation.api.{suffix}@example.com",
        username=f"cancellationapi{suffix}",
        first_name="Cancellation",
        last_name="API",
        hashed_password="hashed-password",
        role=role,
    )


def create_context(
    db_session: Session,
    suffix: str,
    *,
    reservation_status: ParkingReservationStatus = ParkingReservationStatus.ACTIVE,
) -> tuple[User, User, ParkingAvailability, ParkingApplication, ParkingReservation, ParkingApplication]:
    owner = create_user(db_session, f"owner{suffix}", role=UserRole.PARKING_OWNER)
    reserved_user = create_user(db_session, f"reserved{suffix}")
    pending_user = create_user(db_session, f"pending{suffix}")
    spot = ParkingSpotRepository(db_session).create(code=f"CA-{suffix}", owner_id=owner.id)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=spot.id,
        owner_id=owner.id,
        start_at=TEST_NOW + timedelta(hours=1),
        end_at=TEST_NOW + timedelta(hours=9),
        status=ParkingAvailabilityStatus.ASSIGNED,
    )
    selected_application = ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=reserved_user.id,
        status=ParkingApplicationStatus.SELECTED,
    )
    pending_application = ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=pending_user.id,
        status=ParkingApplicationStatus.PENDING,
    )
    reservation = ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=selected_application.id,
        parking_spot_id=spot.id,
        reserved_for_user_id=reserved_user.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
        status=reservation_status,
    )
    return owner, reserved_user, availability, selected_application, reservation, pending_application


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


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
    }
    serialized_payload = json.dumps(payload)
    assert "audit" not in serialized_payload
    assert "reason" not in serialized_payload
    assert "password" not in serialized_payload
    assert "token" not in serialized_payload


def test_reserved_user_can_cancel_own_reservation_without_replacement(
    client: TestClient,
    db_session: Session,
) -> None:
    _, reserved_user, availability, selected_application, reservation, pending_application = create_context(
        db_session,
        "user",
    )

    response = client.patch(
        f"/parking-reservations/{reservation.id}/cancel",
        json={"reason": "  Personal schedule change  "},
        headers=bearer_header(reserved_user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == ParkingReservationStatus.CANCELLED.value
    assert_safe_reservation_response(response.json())
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability.id).status is ParkingAvailabilityStatus.OPEN
    assert ParkingApplicationRepository(db_session).get_by_id(selected_application.id).status is (
        ParkingApplicationStatus.CANCELLED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(pending_application.id).status is (
        ParkingApplicationStatus.PENDING
    )
    assert ParkingAssignmentAuditLogRepository(db_session).list(reservation_id=reservation.id) == []


def test_reserved_user_can_cancel_without_request_body(client: TestClient, db_session: Session) -> None:
    _, reserved_user, _, _, reservation, _ = create_context(db_session, "nobody")

    response = client.patch(
        f"/parking-reservations/{reservation.id}/cancel",
        headers=bearer_header(reserved_user),
    )

    assert response.status_code == 200
    assert response.json()["status"] == ParkingReservationStatus.CANCELLED.value


def test_availability_owner_can_cancel_reservation_and_create_audit(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, _, _, selected_application, reservation, _ = create_context(db_session, "owner")

    response = client.patch(
        f"/parking-reservations/{reservation.id}/cancel",
        json={"reason": "  Owner unavailable  "},
        headers=bearer_header(owner),
    )

    assert response.status_code == 200
    assert ParkingApplicationRepository(db_session).get_by_id(selected_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )
    audit_log = ParkingAssignmentAuditLogRepository(db_session).get_by_reservation_id(reservation.id)
    assert audit_log is not None
    assert audit_log.trigger_source is ParkingAssignmentTriggerSource.MANUAL_OWNER
    assert audit_log.ranking_details[0]["reason"] == "Owner unavailable"
    assert audit_log.ranking_details[0]["owner_user_id"] == owner.id


def test_admin_can_cancel_any_active_reservation_with_reason_and_audit(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, reserved_user, availability, selected_application, reservation, pending_application = create_context(
        db_session,
        "admin",
    )

    response = client.patch(
        f"/admin/parking-reservations/{reservation.id}/cancel",
        json={"reason": "  Policy exception  "},
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    assert_safe_reservation_response(response.json())
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability.id).status is ParkingAvailabilityStatus.OPEN
    assert ParkingApplicationRepository(db_session).get_by_id(selected_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(pending_application.id).status is (
        ParkingApplicationStatus.PENDING
    )
    audit_log = ParkingAssignmentAuditLogRepository(db_session).get_by_reservation_id(reservation.id)
    assert audit_log is not None
    assert audit_log.trigger_source is ParkingAssignmentTriggerSource.ADMIN_OVERRIDE
    assert audit_log.ranking_details[0]["action"] == "cancellation"
    assert audit_log.ranking_details[0]["reason"] == "Policy exception"
    assert audit_log.ranking_details[0]["admin_user_id"] == admin.id
    assert audit_log.ranking_details[0]["previous_application_id"] == selected_application.id
    assert audit_log.ranking_details[0]["previous_user_id"] == reserved_user.id


@pytest.mark.parametrize("request_payload", [{}, {"reason": ""}, {"reason": "   "}])
def test_admin_cancellation_requires_non_blank_reason(
    client: TestClient,
    db_session: Session,
    request_payload: dict[str, object],
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    response = client.patch(
        "/admin/parking-reservations/1/cancel",
        json=request_payload,
        headers=bearer_header(admin),
    )

    assert response.status_code == 422


def test_unrelated_user_cannot_cancel_reservation(client: TestClient, db_session: Session) -> None:
    unrelated = create_user(db_session, "unrelated")
    _, _, _, _, reservation, _ = create_context(db_session, "forbidden")

    response = client.patch(
        f"/parking-reservations/{reservation.id}/cancel",
        json={},
        headers=bearer_header(unrelated),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_missing_reservation_returns_404(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session, "user")

    response = client.patch(
        "/parking-reservations/999/cancel",
        json={},
        headers=bearer_header(user),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking reservation not found"}


def test_non_active_reservation_returns_409(client: TestClient, db_session: Session) -> None:
    _, reserved_user, _, _, reservation, _ = create_context(
        db_session,
        "inactive",
        reservation_status=ParkingReservationStatus.CANCELLED,
    )

    response = client.patch(
        f"/parking-reservations/{reservation.id}/cancel",
        json={},
        headers=bearer_header(reserved_user),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking reservation is not active"}


def test_unrelated_user_receives_403_before_inactive_status_is_disclosed(
    client: TestClient,
    db_session: Session,
) -> None:
    unrelated = create_user(db_session, "inactiveunrelated")
    _, _, _, _, reservation, _ = create_context(
        db_session,
        "inactiveprivate",
        reservation_status=ParkingReservationStatus.CANCELLED,
    )

    response = client.patch(
        f"/parking-reservations/{reservation.id}/cancel",
        json={},
        headers=bearer_header(unrelated),
    )

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
    response = client.patch("/parking-reservations/1/cancel", json={}, headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


@pytest.mark.parametrize("role", [UserRole.EMPLOYEE, UserRole.PARKING_OWNER])
def test_non_admin_cannot_access_admin_cancellation(
    client: TestClient,
    db_session: Session,
    role: UserRole,
) -> None:
    user = create_user(db_session, role.value, role=role)

    response = client.patch(
        "/admin/parking-reservations/1/cancel",
        json={"reason": "Reason"},
        headers=bearer_header(user),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_cancellation_endpoints_are_registered_with_bearer_security(app_with_db: FastAPI) -> None:
    paths = app_with_db.openapi()["paths"]
    public_operation = paths["/parking-reservations/{reservation_id}/cancel"]["patch"]
    admin_operation = paths["/admin/parking-reservations/{reservation_id}/cancel"]["patch"]

    assert public_operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert admin_operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert "200" in public_operation["responses"]
    assert "422" in public_operation["responses"]
    assert "200" in admin_operation["responses"]
    assert "422" in admin_operation["responses"]

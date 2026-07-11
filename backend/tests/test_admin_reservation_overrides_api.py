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
from app.models.parking_reservation import ParkingReservation
from app.models.parking_spot import ParkingSpot
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.users import UserRepository
from app.routers.admin_reservation_overrides import http_exception_for_override_error
from app.services.admin_reservation_override import (
    AdminReservationOverrideAdminInactiveError,
    AdminReservationOverrideAdminNotFoundError,
    AdminReservationOverrideApplicantInactiveError,
    AdminReservationOverrideApplicationAlreadyReservedError,
    AdminReservationOverrideApplicationAvailabilityMismatchError,
    AdminReservationOverrideApplicationNotFoundError,
    AdminReservationOverrideApplicationNotPendingError,
    AdminReservationOverrideAuditPersistenceError,
    AdminReservationOverrideAvailabilityNotAssignedError,
    AdminReservationOverrideAvailabilityNotFoundError,
    AdminReservationOverrideAvailabilityNotOpenError,
    AdminReservationOverrideExistingReservationNotActiveError,
    AdminReservationOverrideExistingReservationNotFoundError,
    AdminReservationOverrideIntegrityError,
    AdminReservationOverridePermissionError,
    AdminReservationOverrideReasonRequiredError,
    AdminReservationOverrideReservationExistsError,
)

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
    is_active: bool = True,
) -> User:
    return UserRepository(db_session).create(
        email=f"override.api.{suffix}@example.com",
        username=f"overrideapi{suffix}",
        first_name="Override",
        last_name="API",
        hashed_password="hashed-password",
        role=role,
        is_active=is_active,
    )


def create_context(
    db_session: Session,
    suffix: str,
    *,
    status: ParkingAvailabilityStatus = ParkingAvailabilityStatus.OPEN,
) -> tuple[ParkingSpot, ParkingAvailability]:
    owner = create_user(db_session, f"owner{suffix}", role=UserRole.PARKING_OWNER)
    parking_spot = ParkingSpotRepository(db_session).create(code=f"OA-{suffix}", owner_id=owner.id)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        start_at=TEST_NOW + timedelta(hours=1),
        end_at=TEST_NOW + timedelta(hours=9),
        status=status,
    )
    return parking_spot, availability


def create_application(
    db_session: Session,
    availability: ParkingAvailability,
    applicant: User,
    *,
    status: ParkingApplicationStatus = ParkingApplicationStatus.PENDING,
    created_at: datetime | None = None,
) -> ParkingApplication:
    application = ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=applicant.id,
        status=status,
    )
    if created_at is not None:
        application.created_at = created_at
        application.updated_at = created_at
        db_session.flush()
        db_session.refresh(application)

    return application


def create_existing_reservation(
    db_session: Session,
    *,
    parking_spot: ParkingSpot,
    availability: ParkingAvailability,
    application: ParkingApplication,
) -> ParkingReservation:
    return ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=application.id,
        parking_spot_id=parking_spot.id,
        reserved_for_user_id=application.applicant_id,
        start_at=availability.start_at,
        end_at=availability.end_at,
    )


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def endpoint(availability_id: int) -> str:
    return f"/admin/parking-availabilities/{availability_id}/override-assign"


def payload(application_id: int, reason: str = "Accessibility requirement") -> dict[str, object]:
    return {"application_id": application_id, "reason": reason}


def assert_safe_reservation_response(response_payload: dict[str, object]) -> None:
    assert set(response_payload) == {
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
    serialized_payload = json.dumps(response_payload)
    assert "audit" not in serialized_payload
    assert "reason" not in serialized_payload
    assert "password" not in serialized_payload
    assert "token" not in serialized_payload


def test_admin_can_override_assign_requested_application_and_create_audit(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    parking_spot, availability = create_context(db_session, "success")
    older_applicant = create_user(db_session, "older")
    requested_applicant = create_user(db_session, "requested")
    older_application = create_application(
        db_session,
        availability,
        older_applicant,
        created_at=TEST_NOW,
    )
    requested_application = create_application(
        db_session,
        availability,
        requested_applicant,
        created_at=TEST_NOW + timedelta(minutes=10),
    )

    response = client.post(
        endpoint(availability.id),
        json=payload(requested_application.id, "  Accessibility requirement  "),
        headers=bearer_header(admin),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["availability_id"] == availability.id
    assert body["application_id"] == requested_application.id
    assert body["parking_spot_id"] == parking_spot.id
    assert body["reserved_for_user_id"] == requested_applicant.id
    assert body["status"] == "active"
    assert_safe_reservation_response(body)
    assert ParkingApplicationRepository(db_session).get_by_id(requested_application.id).status is (
        ParkingApplicationStatus.SELECTED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(older_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability.id).status is (
        ParkingAvailabilityStatus.ASSIGNED
    )
    audit_log = ParkingAssignmentAuditLogRepository(db_session).get_by_availability_id(availability.id)
    assert audit_log is not None
    assert audit_log.reservation_id == body["id"]
    assert audit_log.selected_application_id == requested_application.id
    assert audit_log.selected_user_id == requested_applicant.id
    assert audit_log.rejected_application_ids == [older_application.id]
    assert audit_log.trigger_source is ParkingAssignmentTriggerSource.ADMIN_OVERRIDE
    assert audit_log.ranking_details[0]["override_reason"] == "Accessibility requirement"
    assert audit_log.ranking_details[0]["admin_user_id"] == admin.id


@pytest.mark.parametrize(
    "request_payload",
    [
        {"application_id": 1},
        {"application_id": 1, "reason": ""},
        {"application_id": 1, "reason": "   "},
    ],
)
def test_missing_or_blank_reason_returns_422(
    client: TestClient,
    db_session: Session,
    request_payload: dict[str, object],
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    response = client.post(endpoint(1), json=request_payload, headers=bearer_header(admin))

    assert response.status_code == 422


def test_non_positive_application_id_returns_422(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    response = client.post(endpoint(1), json=payload(0), headers=bearer_header(admin))

    assert response.status_code == 422


def test_missing_availability_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    response = client.post(endpoint(999), json=payload(1), headers=bearer_header(admin))

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking availability not found"}


def test_non_open_availability_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "closed", status=ParkingAvailabilityStatus.CANCELLED)

    response = client.post(endpoint(availability.id), json=payload(1), headers=bearer_header(admin))

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking availability is not open"}


def test_missing_application_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "missingapp")

    response = client.post(endpoint(availability.id), json=payload(999), headers=bearer_header(admin))

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking application not found"}


def test_application_from_another_availability_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "target")
    _, other_availability = create_context(db_session, "other")
    applicant = create_user(db_session, "applicant")
    other_application = create_application(db_session, other_availability, applicant)

    response = client.post(
        endpoint(availability.id),
        json=payload(other_application.id),
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking application does not belong to availability"}


def test_non_pending_application_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "nonpending")
    applicant = create_user(db_session, "applicant")
    application = create_application(
        db_session,
        availability,
        applicant,
        status=ParkingApplicationStatus.CANCELLED,
    )

    response = client.post(endpoint(availability.id), json=payload(application.id), headers=bearer_header(admin))

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking application is not pending"}


def test_inactive_applicant_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "inactive")
    applicant = create_user(db_session, "applicant", is_active=False)
    application = create_application(db_session, availability, applicant)

    response = client.post(endpoint(availability.id), json=payload(application.id), headers=bearer_header(admin))

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking applicant is inactive"}


def test_existing_reservation_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    parking_spot, availability = create_context(db_session, "existing")
    applicant = create_user(db_session, "applicant")
    application = create_application(db_session, availability, applicant)
    create_existing_reservation(
        db_session,
        parking_spot=parking_spot,
        availability=availability,
        application=application,
    )

    response = client.post(endpoint(availability.id), json=payload(application.id), headers=bearer_header(admin))

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking reservation already exists"}


@pytest.mark.parametrize("role", [UserRole.EMPLOYEE, UserRole.PARKING_OWNER])
def test_non_admin_receives_403(client: TestClient, db_session: Session, role: UserRole) -> None:
    user = create_user(db_session, role.value, role=role)

    response = client.post(endpoint(1), json=payload(1), headers=bearer_header(user))

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
    response = client.post(endpoint(1), json=payload(1), headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (AdminReservationOverrideReasonRequiredError(), 400, "Override reason is required"),
        (AdminReservationOverrideAvailabilityNotFoundError(), 404, "Parking availability not found"),
        (AdminReservationOverrideApplicationNotFoundError(), 404, "Parking application not found"),
        (AdminReservationOverrideAvailabilityNotOpenError(), 409, "Parking availability is not open"),
        (AdminReservationOverrideAvailabilityNotAssignedError(), 409, "Parking availability is not assigned"),
        (
            AdminReservationOverrideApplicationAvailabilityMismatchError(),
            409,
            "Parking application does not belong to availability",
        ),
        (AdminReservationOverrideApplicationAlreadyReservedError(), 409, "Parking application is already reserved"),
        (AdminReservationOverrideApplicationNotPendingError(), 409, "Parking application is not pending"),
        (AdminReservationOverrideApplicantInactiveError(), 409, "Parking applicant is inactive"),
        (AdminReservationOverrideReservationExistsError(), 409, "Parking reservation already exists"),
        (AdminReservationOverrideExistingReservationNotFoundError(), 409, "Active parking reservation not found"),
        (AdminReservationOverrideExistingReservationNotActiveError(), 409, "Parking reservation is not active"),
        (AdminReservationOverrideIntegrityError(), 409, "Parking reservation override conflict"),
        (AdminReservationOverrideAuditPersistenceError(), 409, "Parking reservation override conflict"),
        (AdminReservationOverrideAdminNotFoundError(), 403, "Not enough permissions"),
        (AdminReservationOverrideAdminInactiveError(), 403, "Not enough permissions"),
        (AdminReservationOverridePermissionError(), 403, "Not enough permissions"),
    ],
)
def test_override_service_errors_map_to_clean_http_responses(
    error: Exception,
    expected_status: int,
    expected_detail: str,
) -> None:
    mapped_error = http_exception_for_override_error(error)

    assert mapped_error.status_code == expected_status
    assert mapped_error.detail == expected_detail

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
from app.models.parking_spot import ParkingSpot
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.users import UserRepository
from app.services.admin_reservation_override import AdminReservationOverrideService

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
        email=f"replacement.api.{suffix}@example.com",
        username=f"replacementapi{suffix}",
        first_name="Replacement",
        last_name="API",
        hashed_password="hashed-password",
        role=role,
        is_active=is_active,
    )


def create_application(
    db_session: Session,
    availability: ParkingAvailability,
    applicant: User,
    *,
    status: ParkingApplicationStatus,
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


def create_assigned_context(
    db_session: Session,
    suffix: str,
    *,
    availability_status: ParkingAvailabilityStatus = ParkingAvailabilityStatus.ASSIGNED,
    reservation_status: ParkingReservationStatus = ParkingReservationStatus.ACTIVE,
    include_reservation: bool = True,
) -> tuple[ParkingSpot, ParkingAvailability, User, ParkingApplication, ParkingReservation | None]:
    owner = create_user(db_session, f"owner{suffix}", role=UserRole.PARKING_OWNER)
    previous_user = create_user(db_session, f"previous{suffix}")
    spot = ParkingSpotRepository(db_session).create(code=f"RA-{suffix}", owner_id=owner.id)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=spot.id,
        owner_id=owner.id,
        start_at=TEST_NOW + timedelta(hours=1),
        end_at=TEST_NOW + timedelta(hours=9),
        status=availability_status,
    )
    previous_application = create_application(
        db_session,
        availability,
        previous_user,
        status=ParkingApplicationStatus.SELECTED,
    )
    reservation = None
    if include_reservation:
        reservation = ParkingReservationRepository(db_session).create(
            availability_id=availability.id,
            application_id=previous_application.id,
            parking_spot_id=spot.id,
            reserved_for_user_id=previous_user.id,
            start_at=availability.start_at,
            end_at=availability.end_at,
            status=reservation_status,
        )

    return spot, availability, previous_user, previous_application, reservation


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def endpoint(availability_id: int) -> str:
    return f"/admin/parking-availabilities/{availability_id}/replace-reservation"


def payload(application_id: int, reason: str = "Coverage change") -> dict[str, object]:
    return {"application_id": application_id, "reason": reason}


def applicant_payload(applicant_id: int, reason: str = "Coverage change") -> dict[str, object]:
    return {"applicant_id": applicant_id, "reason": reason}


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


def test_admin_can_replace_reservation_with_requested_pending_application(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, previous_user, previous_application, reservation = create_assigned_context(db_session, "success")
    normally_ranked_user = create_user(db_session, "normallyranked")
    replacement_user = create_user(db_session, "requested")
    normally_ranked_application = create_application(
        db_session,
        availability,
        normally_ranked_user,
        status=ParkingApplicationStatus.PENDING,
        created_at=TEST_NOW,
    )
    replacement_application = create_application(
        db_session,
        availability,
        replacement_user,
        status=ParkingApplicationStatus.PENDING,
        created_at=TEST_NOW + timedelta(minutes=10),
    )

    response = client.post(
        endpoint(availability.id),
        json=payload(replacement_application.id, "  Coverage change  "),
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert reservation is not None
    assert body["id"] == reservation.id
    assert body["availability_id"] == availability.id
    assert body["application_id"] == replacement_application.id
    assert body["reserved_for_user_id"] == replacement_user.id
    assert body["status"] == ParkingReservationStatus.ACTIVE.value
    assert_safe_reservation_response(body)

    application_repository = ParkingApplicationRepository(db_session)
    assert application_repository.get_by_id(previous_application.id).status is ParkingApplicationStatus.REJECTED
    assert application_repository.get_by_id(replacement_application.id).status is ParkingApplicationStatus.SELECTED
    assert application_repository.get_by_id(normally_ranked_application.id).status is ParkingApplicationStatus.REJECTED
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability.id).status is ParkingAvailabilityStatus.ASSIGNED

    audit_log = ParkingAssignmentAuditLogRepository(db_session).get_by_availability_id(availability.id)
    assert audit_log is not None
    assert audit_log.reservation_id == reservation.id
    assert audit_log.trigger_source is ParkingAssignmentTriggerSource.ADMIN_OVERRIDE
    assert audit_log.ranking_policy == AdminReservationOverrideService.REPLACEMENT_POLICY
    assert set(audit_log.rejected_application_ids) == {
        previous_application.id,
        normally_ranked_application.id,
    }
    assert audit_log.ranking_details[0]["action"] == "replacement"
    assert audit_log.ranking_details[0]["override_reason"] == "Coverage change"
    assert audit_log.ranking_details[0]["admin_user_id"] == admin.id
    assert audit_log.ranking_details[0]["previous_application_id"] == previous_application.id
    assert audit_log.ranking_details[0]["previous_user_id"] == previous_user.id


def test_admin_can_replace_reservation_by_applicant_id_without_pending_application(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, previous_user, previous_application, reservation = create_assigned_context(
        db_session,
        "applicant",
    )
    replacement_user = create_user(db_session, "replacement")

    response = client.post(
        endpoint(availability.id),
        json=applicant_payload(replacement_user.id, "  Applicant selected by admin  "),
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert reservation is not None
    assert body["id"] == reservation.id
    assert body["reserved_for_user_id"] == replacement_user.id
    assert body["status"] == ParkingReservationStatus.ACTIVE.value
    assert_safe_reservation_response(body)

    application_repository = ParkingApplicationRepository(db_session)
    replacement_application = application_repository.get_by_availability_and_applicant(
        availability_id=availability.id,
        applicant_id=replacement_user.id,
    )
    assert replacement_application is not None
    assert replacement_application.status is ParkingApplicationStatus.SELECTED
    assert body["application_id"] == replacement_application.id
    assert application_repository.get_by_id(previous_application.id).status is ParkingApplicationStatus.REJECTED

    audit_log = ParkingAssignmentAuditLogRepository(db_session).get_by_availability_id(availability.id)
    assert audit_log is not None
    audit_detail = audit_log.ranking_details[0]
    assert audit_detail["action"] == "replacement"
    assert audit_detail["override_reason"] == "Applicant selected by admin"
    assert audit_detail["admin_user_id"] == admin.id
    assert audit_detail["previous_application_id"] == previous_application.id
    assert audit_detail["previous_user_id"] == previous_user.id
    assert audit_detail["selected_application_id"] == replacement_application.id
    assert audit_detail["selected_user_id"] == replacement_user.id
    assert audit_detail["requested_applicant_id"] == replacement_user.id
    assert audit_detail["replacement_selection_basis"] == "manual_admin_replacement_by_applicant"
    assert audit_detail["replacement_candidate_action"] == "created_application"


def test_admin_can_replace_reservation_by_applicant_id_with_rejected_application(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _ = create_assigned_context(db_session, "reactivate")
    replacement_user = create_user(db_session, "reactivated")
    rejected_application = create_application(
        db_session,
        availability,
        replacement_user,
        status=ParkingApplicationStatus.REJECTED,
    )

    response = client.post(
        endpoint(availability.id),
        json=applicant_payload(replacement_user.id),
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["application_id"] == rejected_application.id
    assert body["reserved_for_user_id"] == replacement_user.id
    assert (
        ParkingApplicationRepository(db_session).get_by_id(rejected_application.id).status
        is ParkingApplicationStatus.SELECTED
    )
    audit_log = ParkingAssignmentAuditLogRepository(db_session).get_by_availability_id(availability.id)
    assert audit_log.ranking_details[0]["replacement_candidate_action"] == "reactivated_existing_application"


def test_replacement_by_applicant_id_rejects_current_reserved_user(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, previous_user, _, _ = create_assigned_context(db_session, "currentuser")

    response = client.post(
        endpoint(availability.id),
        json=applicant_payload(previous_user.id),
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking applicant is already reserved"}


def test_missing_replacement_applicant_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _ = create_assigned_context(db_session, "missingapplicant")

    response = client.post(endpoint(availability.id), json=applicant_payload(999), headers=bearer_header(admin))

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking applicant not found"}


def test_inactive_replacement_applicant_by_id_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _ = create_assigned_context(db_session, "inactiveapplicantid")
    applicant = create_user(db_session, "inactivebyid", is_active=False)

    response = client.post(
        endpoint(availability.id),
        json=applicant_payload(applicant.id),
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking applicant is inactive"}


def test_replacement_with_both_application_and_applicant_returns_422(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    response = client.post(
        endpoint(1),
        json={"application_id": 1, "applicant_id": 1, "reason": "Invalid selector"},
        headers=bearer_header(admin),
    )

    assert response.status_code == 422


def test_replacement_without_application_or_applicant_returns_422(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    response = client.post(
        endpoint(1),
        json={"reason": "Invalid selector"},
        headers=bearer_header(admin),
    )

    assert response.status_code == 422


def test_non_positive_applicant_id_returns_422(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    response = client.post(endpoint(1), json=applicant_payload(0), headers=bearer_header(admin))

    assert response.status_code == 422


def test_employee_still_cannot_apply_to_assigned_availability(
    client: TestClient,
    db_session: Session,
) -> None:
    _, availability, _, _, _ = create_assigned_context(db_session, "employeeapply")
    applicant = create_user(db_session, "employeeapply")

    response = client.post(
        "/parking-applications",
        json={"availability_id": availability.id, "note": "Need parking"},
        headers=bearer_header(applicant),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking availability is not open"}


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


def test_availability_not_assigned_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _ = create_assigned_context(
        db_session,
        "open",
        availability_status=ParkingAvailabilityStatus.OPEN,
        include_reservation=False,
    )

    response = client.post(endpoint(availability.id), json=payload(1), headers=bearer_header(admin))

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking availability is not assigned"}


def test_missing_existing_reservation_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _ = create_assigned_context(db_session, "missingreservation", include_reservation=False)

    response = client.post(endpoint(availability.id), json=payload(1), headers=bearer_header(admin))

    assert response.status_code == 409
    assert response.json() == {"detail": "Active parking reservation not found"}


def test_existing_reservation_not_active_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _ = create_assigned_context(
        db_session,
        "inactive",
        reservation_status=ParkingReservationStatus.CANCELLED,
    )

    response = client.post(endpoint(availability.id), json=payload(1), headers=bearer_header(admin))

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking reservation is not active"}


def test_missing_replacement_application_returns_404(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _ = create_assigned_context(db_session, "missingapplication")

    response = client.post(endpoint(availability.id), json=payload(999), headers=bearer_header(admin))

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking application not found"}


def test_replacement_application_from_another_availability_returns_409(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _ = create_assigned_context(db_session, "target")
    _, other_availability, _, _, _ = create_assigned_context(db_session, "other")
    applicant = create_user(db_session, "otherapplicant")
    other_application = create_application(
        db_session,
        other_availability,
        applicant,
        status=ParkingApplicationStatus.PENDING,
    )

    response = client.post(
        endpoint(availability.id),
        json=payload(other_application.id),
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking application does not belong to availability"}


def test_non_pending_replacement_application_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _ = create_assigned_context(db_session, "nonpending")
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


def test_inactive_replacement_applicant_returns_409(client: TestClient, db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _ = create_assigned_context(db_session, "inactiveapplicant")
    applicant = create_user(db_session, "applicant", is_active=False)
    application = create_application(
        db_session,
        availability,
        applicant,
        status=ParkingApplicationStatus.PENDING,
    )

    response = client.post(endpoint(availability.id), json=payload(application.id), headers=bearer_header(admin))

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking applicant is inactive"}


def test_replacing_with_currently_selected_application_returns_409(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, previous_application, _ = create_assigned_context(db_session, "alreadyselected")

    response = client.post(
        endpoint(availability.id),
        json=payload(previous_application.id),
        headers=bearer_header(admin),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking application is already reserved"}


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


def test_replacement_endpoint_is_registered_with_bearer_security(app_with_db: FastAPI) -> None:
    operation = app_with_db.openapi()["paths"][
        "/admin/parking-availabilities/{availability_id}/replace-reservation"
    ]["post"]

    assert operation["requestBody"]["required"] is True
    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert "200" in operation["responses"]
    assert "422" in operation["responses"]

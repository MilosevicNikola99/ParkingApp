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
) -> User:
    user = UserRepository(db_session).create(
        email=email,
        username=username,
        first_name="Test",
        last_name="User",
        hashed_password=hash_password("valid-password"),
        role=role,
        is_active=is_active,
    )
    db_session.commit()
    return user


def create_owner(
    db_session: Session,
    *,
    email: str = "owner@example.com",
    username: str = "owner",
) -> User:
    return create_test_user(db_session, email=email, username=username, role=UserRole.PARKING_OWNER)


def create_employee(
    db_session: Session,
    *,
    email: str = "employee@example.com",
    username: str = "employee",
) -> User:
    return create_test_user(db_session, email=email, username=username)


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
    parking_spot_id: int,
    owner_id: int,
    status: ParkingAvailabilityStatus = ParkingAvailabilityStatus.OPEN,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> ParkingAvailability:
    start = start_at or datetime.now(UTC) + timedelta(hours=1)
    end = end_at or start + timedelta(hours=4)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=start,
        end_at=end,
        status=status,
        note="Published availability",
    )
    db_session.commit()
    return availability


def create_application(
    db_session: Session,
    *,
    availability_id: int,
    applicant_id: int,
    status: ParkingApplicationStatus = ParkingApplicationStatus.PENDING,
    created_at: datetime | None = None,
) -> ParkingApplication:
    application = ParkingApplicationRepository(db_session).create(
        availability_id=availability_id,
        applicant_id=applicant_id,
        status=status,
        note="Assignment request",
    )
    if created_at is not None:
        application.created_at = created_at
        application.updated_at = created_at
        db_session.flush()

    db_session.commit()
    db_session.refresh(application)
    return application


def create_reservation(
    db_session: Session,
    *,
    availability: ParkingAvailability,
    application: ParkingApplication,
) -> ParkingReservation:
    reservation = ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=application.id,
        parking_spot_id=availability.parking_spot_id,
        reserved_for_user_id=application.applicant_id,
        start_at=availability.start_at,
        end_at=availability.end_at,
    )
    db_session.commit()
    db_session.refresh(reservation)
    return reservation


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def availability_payload(
    parking_spot_id: int,
    *,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> dict[str, int | str]:
    start = start_at or datetime.now(UTC) + timedelta(hours=1)
    end = end_at or start + timedelta(hours=4)
    return {
        "parking_spot_id": parking_spot_id,
        "start_at": start.isoformat(),
        "end_at": end.isoformat(),
        "note": "Remote work day",
    }


def assert_no_sensitive_fields(payload: dict[str, object]) -> None:
    if "parking_spot_id" in payload:
        assert payload["owner"]["email"]
        assert payload["parking_spot"]["code"]
    serialized_payload = json.dumps(payload)
    assert "hashed_password" not in serialized_payload
    assert "password" not in serialized_payload


def test_owner_can_create_availability_for_own_active_parking_spot(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)

    response = client.post(
        "/parking-availabilities",
        json=availability_payload(parking_spot.id),
        headers=bearer_header(owner),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["parking_spot_id"] == parking_spot.id
    assert body["owner_id"] == owner.id
    assert body["status"] == "open"
    assert body["priority_until"] is not None
    assert_no_sensitive_fields(body)


def test_non_owner_cannot_create_availability_for_another_users_spot(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    other_owner = create_owner(db_session, email="other.owner@example.com", username="otherowner")
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)

    response = client.post(
        "/parking-availabilities",
        json=availability_payload(parking_spot.id),
        headers=bearer_header(other_owner),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_owner_can_list_only_own_active_parking_spots(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    other_owner = create_owner(db_session, email="other.owner@example.com", username="otherowner")
    active_spot = create_parking_spot(db_session, owner_id=owner.id, code="OWN-ACTIVE")
    create_parking_spot(db_session, owner_id=owner.id, code="OWN-INACTIVE", is_active=False)
    create_parking_spot(db_session, owner_id=other_owner.id, code="OTHER-ACTIVE")

    response = client.get("/parking-spots/mine", headers=bearer_header(owner))

    assert response.status_code == 200
    assert [spot["id"] for spot in response.json()] == [active_spot.id]
    assert response.json()[0]["code"] == "OWN-ACTIVE"
    assert response.json()[0]["location"] == "Garage P1"
    assert response.json()[0]["is_active"] is True
    assert_no_sensitive_fields(response.json()[0])


def test_employee_owned_parking_spot_list_is_empty(client: TestClient, db_session: Session) -> None:
    employee = create_employee(db_session)
    owner = create_owner(db_session)
    create_parking_spot(db_session, owner_id=owner.id)

    response = client.get("/parking-spots/mine", headers=bearer_header(employee))

    assert response.status_code == 200
    assert response.json() == []


def test_owned_parking_spot_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/parking-spots/mine")

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}

def test_missing_parking_spot_returns_404(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)

    response = client.post(
        "/parking-availabilities",
        json=availability_payload(999),
        headers=bearer_header(owner),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking spot not found"}


def test_inactive_parking_spot_cannot_be_published(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id, is_active=False)

    response = client.post(
        "/parking-availabilities",
        json=availability_payload(parking_spot.id),
        headers=bearer_header(owner),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking spot is inactive"}


@pytest.mark.parametrize(
    "blocking_status",
    [ParkingAvailabilityStatus.OPEN, ParkingAvailabilityStatus.ASSIGNED],
)
def test_overlapping_open_or_assigned_availability_is_rejected(
    client: TestClient,
    db_session: Session,
    blocking_status: ParkingAvailabilityStatus,
) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    start = datetime.now(UTC) + timedelta(hours=2)
    create_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        status=blocking_status,
        start_at=start,
        end_at=start + timedelta(hours=4),
    )

    response = client.post(
        "/parking-availabilities",
        json=availability_payload(
            parking_spot.id,
            start_at=start + timedelta(hours=1),
            end_at=start + timedelta(hours=2),
        ),
        headers=bearer_header(owner),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking availability overlaps with an existing availability"}


def test_overlapping_cancelled_availability_does_not_block(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    start = datetime.now(UTC) + timedelta(hours=2)
    create_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        status=ParkingAvailabilityStatus.CANCELLED,
        start_at=start,
        end_at=start + timedelta(hours=4),
    )

    response = client.post(
        "/parking-availabilities",
        json=availability_payload(
            parking_spot.id,
            start_at=start + timedelta(hours=1),
            end_at=start + timedelta(hours=2),
        ),
        headers=bearer_header(owner),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "open"


def test_end_at_in_the_past_is_rejected(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)

    response = client.post(
        "/parking-availabilities",
        json=availability_payload(
            parking_spot.id,
            start_at=datetime.now(UTC) - timedelta(hours=3),
            end_at=datetime.now(UTC) - timedelta(hours=1),
        ),
        headers=bearer_header(owner),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Availability end time cannot be in the past"}


def test_authenticated_user_can_list_open_availabilities(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    employee = create_employee(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    open_availability = create_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        status=ParkingAvailabilityStatus.OPEN,
    )
    create_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        status=ParkingAvailabilityStatus.CANCELLED,
        start_at=datetime.now(UTC) + timedelta(days=1),
    )

    response = client.get("/parking-availabilities", headers=bearer_header(employee))

    assert response.status_code == 200
    body = response.json()
    assert [availability["id"] for availability in body] == [open_availability.id]
    assert_no_sensitive_fields(body[0])


def test_authenticated_owner_can_list_own_availabilities(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    other_owner = create_owner(db_session, email="other.owner@example.com", username="otherowner")
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    other_spot = create_parking_spot(db_session, owner_id=other_owner.id, code="B-01")
    own_open = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)
    own_cancelled = create_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        status=ParkingAvailabilityStatus.CANCELLED,
        start_at=datetime.now(UTC) + timedelta(days=1),
    )
    create_availability(db_session, parking_spot_id=other_spot.id, owner_id=other_owner.id)

    response = client.get("/parking-availabilities/my", headers=bearer_header(owner))

    assert response.status_code == 200
    assert [availability["id"] for availability in response.json()] == [own_open.id, own_cancelled.id]


def test_authenticated_user_can_view_open_availability(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    employee = create_employee(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)

    response = client.get(f"/parking-availabilities/{availability.id}", headers=bearer_header(employee))

    assert response.status_code == 200
    assert response.json()["id"] == availability.id


def test_non_owner_cannot_view_non_open_availability_unless_admin(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    employee = create_employee(db_session)
    admin = create_admin(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        status=ParkingAvailabilityStatus.ASSIGNED,
    )

    employee_response = client.get(f"/parking-availabilities/{availability.id}", headers=bearer_header(employee))
    admin_response = client.get(f"/parking-availabilities/{availability.id}", headers=bearer_header(admin))

    assert employee_response.status_code == 403
    assert employee_response.json() == {"detail": "Not enough permissions"}
    assert admin_response.status_code == 200
    assert admin_response.json()["id"] == availability.id


def test_owner_can_cancel_open_availability(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)

    response = client.patch(f"/parking-availabilities/{availability.id}/cancel", headers=bearer_header(owner))

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_admin_can_cancel_open_availability(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    admin = create_admin(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)

    response = client.patch(f"/parking-availabilities/{availability.id}/cancel", headers=bearer_header(admin))

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_non_owner_cannot_cancel_availability(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    other_owner = create_owner(db_session, email="other.owner@example.com", username="otherowner")
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)

    response = client.patch(f"/parking-availabilities/{availability.id}/cancel", headers=bearer_header(other_owner))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_cancelled_availability_cannot_be_cancelled_again(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        status=ParkingAvailabilityStatus.CANCELLED,
    )

    response = client.patch(f"/parking-availabilities/{availability.id}/cancel", headers=bearer_header(owner))

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking availability cannot be cancelled"}


def test_owner_can_assign_availability_with_one_pending_application(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    applicant = create_employee(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)
    application = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    response = client.post(f"/parking-availabilities/{availability.id}/assign", headers=bearer_header(owner))

    assert response.status_code == 201
    body = response.json()
    assert body["availability_id"] == availability.id
    assert body["application_id"] == application.id
    assert body["parking_spot_id"] == parking_spot.id
    assert body["reserved_for_user_id"] == applicant.id
    assert body["status"] == "active"
    assert "hashed_password" not in body
    assert set(body) == {
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
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability.id).status is (
        ParkingAvailabilityStatus.ASSIGNED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(application.id).status is (
        ParkingApplicationStatus.SELECTED
    )
    audit_log = ParkingAssignmentAuditLogRepository(db_session).get_by_availability_id(availability.id)
    assert audit_log is not None
    assert audit_log.reservation_id == body["id"]
    assert audit_log.selected_application_id == application.id
    assert audit_log.selected_user_id == applicant.id
    assert audit_log.rejected_application_ids == []
    assert len(audit_log.ranking_details) == 1
    assert audit_log.trigger_source is ParkingAssignmentTriggerSource.MANUAL_OWNER


def test_admin_can_assign_availability_owned_by_another_user(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    admin = create_admin(db_session)
    applicant = create_employee(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)
    application = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    response = client.post(f"/parking-availabilities/{availability.id}/assign", headers=bearer_header(admin))

    assert response.status_code == 201
    assert response.json()["application_id"] == application.id
    audit_log = ParkingAssignmentAuditLogRepository(db_session).get_by_availability_id(availability.id)
    assert audit_log is not None
    assert audit_log.trigger_source is ParkingAssignmentTriggerSource.MANUAL_ADMIN


def test_non_owner_non_admin_cannot_assign_availability(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    employee = create_employee(db_session)
    applicant = create_employee(db_session, email="applicant@example.com", username="applicant")
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)
    create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    response = client.post(f"/parking-availabilities/{availability.id}/assign", headers=bearer_header(employee))

    assert response.status_code == 403
    assert response.json() == {"detail": "Not enough permissions"}


def test_assigning_missing_availability_returns_404(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)

    response = client.post("/parking-availabilities/999/assign", headers=bearer_header(owner))

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking availability not found"}


def test_assigning_non_open_availability_returns_409(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    applicant = create_employee(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(
        db_session,
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        status=ParkingAvailabilityStatus.CANCELLED,
    )
    create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)

    response = client.post(f"/parking-availabilities/{availability.id}/assign", headers=bearer_header(owner))

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking availability is not open"}


def test_assigning_open_availability_with_no_pending_applications_returns_409(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)

    response = client.post(f"/parking-availabilities/{availability.id}/assign", headers=bearer_header(owner))

    assert response.status_code == 409
    assert response.json() == {"detail": "No pending parking applications"}


def test_assigning_availability_with_existing_reservation_returns_409(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    applicant = create_employee(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)
    application = create_application(db_session, availability_id=availability.id, applicant_id=applicant.id)
    create_reservation(db_session, availability=availability, application=application)

    response = client.post(f"/parking-availabilities/{availability.id}/assign", headers=bearer_header(owner))

    assert response.status_code == 409
    assert response.json() == {"detail": "Parking reservation already exists"}


def test_assigning_availability_rejects_other_pending_and_ignores_non_pending_applications(
    client: TestClient,
    db_session: Session,
) -> None:
    owner = create_owner(db_session)
    older_applicant = create_employee(db_session)
    newer_applicant = create_employee(db_session, email="newer@example.com", username="newer")
    cancelled_applicant = create_employee(db_session, email="cancelled@example.com", username="cancelled")
    rejected_applicant = create_employee(db_session, email="rejected@example.com", username="rejected")
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)
    older_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=older_applicant.id,
        created_at=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
    )
    newer_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=newer_applicant.id,
        created_at=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    cancelled_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=cancelled_applicant.id,
        status=ParkingApplicationStatus.CANCELLED,
        created_at=datetime(2026, 1, 1, 7, 0, tzinfo=UTC),
    )
    rejected_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=rejected_applicant.id,
        status=ParkingApplicationStatus.REJECTED,
        created_at=datetime(2026, 1, 1, 7, 30, tzinfo=UTC),
    )

    response = client.post(f"/parking-availabilities/{availability.id}/assign", headers=bearer_header(owner))

    assert response.status_code == 201
    assert response.json()["application_id"] == older_application.id
    assert ParkingApplicationRepository(db_session).get_by_id(older_application.id).status is (
        ParkingApplicationStatus.SELECTED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(newer_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(cancelled_application.id).status is (
        ParkingApplicationStatus.CANCELLED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(rejected_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )


def test_assign_availability_missing_token_returns_401(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)

    response = client.post(f"/parking-availabilities/{availability.id}/assign")

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_assign_availability_invalid_token_returns_401(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner_id=owner.id)
    availability = create_availability(db_session, parking_spot_id=parking_spot.id, owner_id=owner.id)

    response = client.post(
        f"/parking-availabilities/{availability.id}/assign",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_missing_availability_returns_404(client: TestClient, db_session: Session) -> None:
    owner = create_owner(db_session)

    response = client.get("/parking-availabilities/999", headers=bearer_header(owner))

    assert response.status_code == 404
    assert response.json() == {"detail": "Parking availability not found"}


def test_missing_token_returns_401(client: TestClient) -> None:
    response = client.get("/parking-availabilities")

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_invalid_token_returns_401(client: TestClient) -> None:
    response = client.get("/parking-availabilities", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}

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
from app.models.parking_application import ParkingApplicationStatus
from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog, ParkingAssignmentTriggerSource
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


def create_user(db_session: Session, *, suffix: str, role: UserRole) -> User:
    user = UserRepository(db_session).create(
        email=f"{suffix}@example.com",
        username=suffix,
        first_name="Test",
        last_name="User",
        hashed_password="hashed-password",
        role=role,
    )
    db_session.commit()
    return user


def create_admin(db_session: Session) -> User:
    return create_user(db_session, suffix="admin", role=UserRole.ADMIN)


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def create_audit_log(
    db_session: Session,
    *,
    suffix: str,
    trigger_source: ParkingAssignmentTriggerSource,
    ranking_policy: str,
) -> ParkingAssignmentAuditLog:
    owner = create_user(db_session, suffix=f"owner{suffix}", role=UserRole.PARKING_OWNER)
    selected_user = create_user(db_session, suffix=f"selected{suffix}", role=UserRole.EMPLOYEE)
    rejected_user = create_user(db_session, suffix=f"rejected{suffix}", role=UserRole.EMPLOYEE)
    spot = ParkingSpotRepository(db_session).create(code=f"AUD-{suffix}", owner_id=owner.id)
    start_at = datetime(2026, 6, 5, 8, 0, tzinfo=UTC) + timedelta(hours=int(suffix))
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=spot.id,
        owner_id=owner.id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=8),
    )
    selected_application = ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=selected_user.id,
        status=ParkingApplicationStatus.SELECTED,
    )
    rejected_application = ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=rejected_user.id,
        status=ParkingApplicationStatus.REJECTED,
    )
    reservation = ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=selected_application.id,
        parking_spot_id=spot.id,
        reserved_for_user_id=selected_user.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
    )
    audit_log = ParkingAssignmentAuditLogRepository(db_session).create(
        availability_id=availability.id,
        reservation_id=reservation.id,
        selected_application_id=selected_application.id,
        selected_user_id=selected_user.id,
        rejected_application_ids=[rejected_application.id],
        ranking_policy=ranking_policy,
        ranking_details=[
            {
                "application_id": selected_application.id,
                "applicant_id": selected_user.id,
                "final_rank_position": 1,
                "selected": True,
            },
            {
                "application_id": rejected_application.id,
                "applicant_id": rejected_user.id,
                "final_rank_position": 2,
                "selected": False,
            },
        ],
        trigger_source=trigger_source,
    )
    db_session.commit()
    db_session.refresh(audit_log)
    return audit_log


def assert_stable_safe_response(payload: dict[str, object]) -> None:
    assert set(payload) == {
        "id",
        "availability_id",
        "reservation_id",
        "selected_application_id",
        "selected_user_id",
        "rejected_application_ids",
        "ranking_policy",
        "ranking_details",
        "trigger_source",
        "created_at",
    }
    serialized_payload = json.dumps(payload)
    assert "hashed_password" not in serialized_payload
    assert "password" not in serialized_payload
    assert "access_token" not in serialized_payload


def test_admin_can_list_audit_logs_newest_first_with_serialized_details(
    client: TestClient,
    db_session: Session,
) -> None:
    admin = create_admin(db_session)
    older = create_audit_log(
        db_session,
        suffix="1",
        trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
        ranking_policy="policy-v1",
    )
    newer = create_audit_log(
        db_session,
        suffix="2",
        trigger_source=ParkingAssignmentTriggerSource.SCHEDULED,
        ranking_policy="policy-v2",
    )

    response = client.get("/admin/assignment-audit-logs", headers=bearer_header(admin))

    assert response.status_code == 200
    body = response.json()
    assert [audit_log["id"] for audit_log in body] == [newer.id, older.id]
    assert body[0]["trigger_source"] == "scheduled"
    assert body[0]["rejected_application_ids"] == newer.rejected_application_ids
    assert body[0]["ranking_details"] == newer.ranking_details
    for audit_log in body:
        assert_stable_safe_response(audit_log)


def test_admin_audit_log_list_supports_pagination(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    older = create_audit_log(
        db_session,
        suffix="1",
        trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
        ranking_policy="policy-v1",
    )
    create_audit_log(
        db_session,
        suffix="2",
        trigger_source=ParkingAssignmentTriggerSource.SCHEDULED,
        ranking_policy="policy-v2",
    )

    response = client.get(
        "/admin/assignment-audit-logs?skip=1&limit=1",
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    assert [audit_log["id"] for audit_log in response.json()] == [older.id]


def test_admin_audit_log_list_supports_exact_match_filters(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    owner_audit = create_audit_log(
        db_session,
        suffix="1",
        trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
        ranking_policy="policy-v1",
    )
    scheduled_audit = create_audit_log(
        db_session,
        suffix="2",
        trigger_source=ParkingAssignmentTriggerSource.SCHEDULED,
        ranking_policy="policy-v2",
    )
    filters = {
        f"availability_id={owner_audit.availability_id}": owner_audit.id,
        f"reservation_id={scheduled_audit.reservation_id}": scheduled_audit.id,
        f"selected_user_id={owner_audit.selected_user_id}": owner_audit.id,
        f"selected_application_id={scheduled_audit.selected_application_id}": scheduled_audit.id,
        "trigger_source=scheduled": scheduled_audit.id,
        "ranking_policy=policy-v1": owner_audit.id,
    }

    for query, expected_id in filters.items():
        response = client.get(f"/admin/assignment-audit-logs?{query}", headers=bearer_header(admin))

        assert response.status_code == 200
        assert [audit_log["id"] for audit_log in response.json()] == [expected_id]


def test_admin_can_get_audit_log_by_id(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    audit_log = create_audit_log(
        db_session,
        suffix="1",
        trigger_source=ParkingAssignmentTriggerSource.MANUAL_ADMIN,
        ranking_policy="policy-v1",
    )

    response = client.get(f"/admin/assignment-audit-logs/{audit_log.id}", headers=bearer_header(admin))

    assert response.status_code == 200
    assert response.json()["id"] == audit_log.id
    assert_stable_safe_response(response.json())


def test_admin_can_get_audit_log_by_reservation(client: TestClient, db_session: Session) -> None:
    admin = create_admin(db_session)
    audit_log = create_audit_log(
        db_session,
        suffix="1",
        trigger_source=ParkingAssignmentTriggerSource.MANUAL_ADMIN,
        ranking_policy="policy-v1",
    )

    response = client.get(
        f"/admin/assignment-audit-logs/by-reservation/{audit_log.reservation_id}",
        headers=bearer_header(admin),
    )

    assert response.status_code == 200
    assert response.json()["id"] == audit_log.id


@pytest.mark.parametrize(
    "path",
    [
        "/admin/assignment-audit-logs/999",
        "/admin/assignment-audit-logs/by-reservation/999",
    ],
)
def test_missing_audit_log_returns_404(client: TestClient, db_session: Session, path: str) -> None:
    admin = create_admin(db_session)

    response = client.get(path, headers=bearer_header(admin))

    assert response.status_code == 404
    assert response.json() == {"detail": "Assignment audit log not found"}


@pytest.mark.parametrize("role", [UserRole.EMPLOYEE, UserRole.PARKING_OWNER])
def test_non_admin_cannot_access_any_audit_log_endpoint(
    client: TestClient,
    db_session: Session,
    role: UserRole,
) -> None:
    user = create_user(db_session, suffix=role.value, role=role)
    audit_log = create_audit_log(
        db_session,
        suffix="1",
        trigger_source=ParkingAssignmentTriggerSource.SYSTEM,
        ranking_policy="policy-v1",
    )

    for path in (
        "/admin/assignment-audit-logs",
        f"/admin/assignment-audit-logs/{audit_log.id}",
        f"/admin/assignment-audit-logs/by-reservation/{audit_log.reservation_id}",
    ):
        response = client.get(path, headers=bearer_header(user))

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
    response = client.get("/admin/assignment-audit-logs", headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}

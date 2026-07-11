from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
import csv
from io import StringIO

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
from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog, ParkingAssignmentTriggerSource
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
from app.services.admin_reports import AdminReportService

REPORT_DAY = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


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


def create_user(db_session: Session, suffix: str, role: UserRole) -> User:
    return UserRepository(db_session).create(
        email=f"report.{suffix}@example.com",
        username=f"report{suffix}",
        first_name="Report",
        last_name="User",
        hashed_password="hashed-password",
        role=role,
    )


def bearer_header(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def set_created_at(record: object, created_at: datetime) -> None:
    setattr(record, "created_at", created_at)
    if hasattr(record, "updated_at"):
        setattr(record, "updated_at", created_at)


def create_report_context(
    db_session: Session,
    *,
    suffix: str,
    owner: User,
    reserved_for_user: User,
    parking_spot: ParkingSpot,
    created_at: datetime,
    availability_status: ParkingAvailabilityStatus,
    application_status: ParkingApplicationStatus,
    reservation_status: ParkingReservationStatus | None,
    trigger_source: ParkingAssignmentTriggerSource | None,
) -> tuple[ParkingAvailability, ParkingApplication, ParkingReservation | None, ParkingAssignmentAuditLog | None]:
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=parking_spot.id,
        owner_id=owner.id,
        start_at=created_at + timedelta(days=10),
        end_at=created_at + timedelta(days=10, hours=8),
        status=availability_status,
        note=f"Availability {suffix}",
    )
    application = ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=reserved_for_user.id,
        status=application_status,
        note=f"Application {suffix}",
    )
    set_created_at(availability, created_at)
    set_created_at(application, created_at)

    reservation = None
    audit_log = None
    if reservation_status is not None:
        reservation = ParkingReservationRepository(db_session).create(
            availability_id=availability.id,
            application_id=application.id,
            parking_spot_id=parking_spot.id,
            reserved_for_user_id=reserved_for_user.id,
            start_at=availability.start_at,
            end_at=availability.end_at,
            status=reservation_status,
        )
        set_created_at(reservation, created_at)

    if reservation is not None and trigger_source is not None:
        audit_log = ParkingAssignmentAuditLogRepository(db_session).create(
            availability_id=availability.id,
            reservation_id=reservation.id,
            selected_application_id=application.id,
            selected_user_id=reserved_for_user.id,
            rejected_application_ids=[],
            ranking_policy="same_team_then_created_v1",
            ranking_details=[{"application_id": application.id, "selected": True}],
            trigger_source=trigger_source,
        )
        set_created_at(audit_log, created_at)

    db_session.flush()
    return availability, application, reservation, audit_log


def create_report_data(db_session: Session) -> dict[str, object]:
    admin = create_user(db_session, "admin", UserRole.ADMIN)
    employee = create_user(db_session, "employee", UserRole.EMPLOYEE)
    owner = create_user(db_session, "owner", UserRole.PARKING_OWNER)
    user_a = create_user(db_session, "winnera", UserRole.EMPLOYEE)
    user_b = create_user(db_session, "winnerb", UserRole.EMPLOYEE)
    spot_a = ParkingSpotRepository(db_session).create(code="REPORT-A", owner_id=owner.id)
    spot_b = ParkingSpotRepository(db_session).create(code="REPORT-B", owner_id=owner.id)

    contexts = [
        create_report_context(
            db_session,
            suffix="open",
            owner=owner,
            reserved_for_user=user_a,
            parking_spot=spot_a,
            created_at=REPORT_DAY,
            availability_status=ParkingAvailabilityStatus.OPEN,
            application_status=ParkingApplicationStatus.PENDING,
            reservation_status=None,
            trigger_source=None,
        ),
        create_report_context(
            db_session,
            suffix="active-a",
            owner=owner,
            reserved_for_user=user_a,
            parking_spot=spot_a,
            created_at=REPORT_DAY + timedelta(days=1),
            availability_status=ParkingAvailabilityStatus.ASSIGNED,
            application_status=ParkingApplicationStatus.SELECTED,
            reservation_status=ParkingReservationStatus.ACTIVE,
            trigger_source=ParkingAssignmentTriggerSource.SCHEDULED,
        ),
        create_report_context(
            db_session,
            suffix="cancelled",
            owner=owner,
            reserved_for_user=user_b,
            parking_spot=spot_b,
            created_at=REPORT_DAY + timedelta(days=2),
            availability_status=ParkingAvailabilityStatus.CANCELLED,
            application_status=ParkingApplicationStatus.REJECTED,
            reservation_status=ParkingReservationStatus.CANCELLED,
            trigger_source=ParkingAssignmentTriggerSource.MANUAL_ADMIN,
        ),
        create_report_context(
            db_session,
            suffix="completed",
            owner=owner,
            reserved_for_user=user_a,
            parking_spot=spot_a,
            created_at=REPORT_DAY + timedelta(days=3),
            availability_status=ParkingAvailabilityStatus.EXPIRED,
            application_status=ParkingApplicationStatus.CANCELLED,
            reservation_status=ParkingReservationStatus.COMPLETED,
            trigger_source=ParkingAssignmentTriggerSource.ADMIN_OVERRIDE,
        ),
        create_report_context(
            db_session,
            suffix="active-b",
            owner=owner,
            reserved_for_user=user_b,
            parking_spot=spot_b,
            created_at=REPORT_DAY + timedelta(days=4),
            availability_status=ParkingAvailabilityStatus.ASSIGNED,
            application_status=ParkingApplicationStatus.SELECTED,
            reservation_status=ParkingReservationStatus.ACTIVE,
            trigger_source=ParkingAssignmentTriggerSource.SCHEDULED,
        ),
    ]
    db_session.commit()
    return {
        "admin": admin,
        "employee": employee,
        "user_a": user_a,
        "user_b": user_b,
        "spot_a": spot_a,
        "spot_b": spot_b,
        "contexts": contexts,
    }


def test_admin_report_service_returns_correct_summaries_and_rankings(db_session: Session) -> None:
    data = create_report_data(db_session)
    service = AdminReportService(db_session)

    summary = service.get_summary()
    top_users = service.get_top_reserved_users()
    spot_usage = service.get_parking_spot_usage()

    assert summary.reservation_summary.model_dump() == {
        "total": 4,
        "active": 2,
        "cancelled": 1,
        "completed": 1,
    }
    assert summary.availability_summary.model_dump() == {
        "total": 5,
        "open": 1,
        "assigned": 2,
        "cancelled": 1,
        "expired": 1,
        "open_without_reservation": 1,
    }
    assert summary.application_summary.model_dump() == {
        "total": 5,
        "pending": 1,
        "selected": 2,
        "rejected": 1,
        "cancelled": 1,
    }
    assert [(item.trigger_source.value, item.count) for item in summary.audit_trigger_summary] == [
        ("scheduled", 2),
        ("admin_override", 1),
        ("manual_admin", 1),
    ]
    assert [(item.user_id, item.reservation_count) for item in top_users] == [
        (data["user_a"].id, 2),
        (data["user_b"].id, 1),
    ]
    assert [(item.parking_spot_id, item.reservation_count) for item in spot_usage] == [
        (data["spot_a"].id, 2),
        (data["spot_b"].id, 1),
    ]


def test_admin_report_service_applies_inclusive_created_at_date_filters(db_session: Session) -> None:
    create_report_data(db_session)
    service = AdminReportService(db_session)

    summary = service.get_summary(
        date_from=date(2026, 6, 2),
        date_to=date(2026, 6, 4),
    )

    assert summary.reservation_summary.total == 3
    assert summary.availability_summary.total == 3
    assert summary.availability_summary.open_without_reservation == 0
    assert summary.application_summary.total == 3
    assert {item.trigger_source.value: item.count for item in summary.audit_trigger_summary} == {
        "scheduled": 1,
        "manual_admin": 1,
        "admin_override": 1,
    }


def test_admin_can_get_summary_report_with_correct_counts_and_date_filters(
    client: TestClient,
    db_session: Session,
) -> None:
    data = create_report_data(db_session)

    response = client.get("/admin/reports/summary", headers=bearer_header(data["admin"]))
    filtered_response = client.get(
        "/admin/reports/summary?date_from=2026-06-02&date_to=2026-06-04",
        headers=bearer_header(data["admin"]),
    )

    assert response.status_code == 200
    assert response.json()["reservation_summary"]["total"] == 4
    assert response.json()["availability_summary"]["open_without_reservation"] == 1
    assert response.json()["application_summary"]["pending"] == 1
    assert response.json()["audit_trigger_summary"] == [
        {"trigger_source": "scheduled", "count": 2},
        {"trigger_source": "admin_override", "count": 1},
        {"trigger_source": "manual_admin", "count": 1},
    ]
    assert filtered_response.status_code == 200
    assert filtered_response.json()["reservation_summary"]["total"] == 3


def test_admin_top_users_and_parking_spot_usage_are_ordered(
    client: TestClient,
    db_session: Session,
) -> None:
    data = create_report_data(db_session)

    users_response = client.get("/admin/reports/top-users", headers=bearer_header(data["admin"]))
    spots_response = client.get("/admin/reports/parking-spot-usage", headers=bearer_header(data["admin"]))

    assert users_response.status_code == 200
    assert users_response.json() == [
        {"user_id": data["user_a"].id, "reservation_count": 2},
        {"user_id": data["user_b"].id, "reservation_count": 1},
    ]
    assert spots_response.status_code == 200
    assert spots_response.json() == [
        {"parking_spot_id": data["spot_a"].id, "reservation_count": 2},
        {"parking_spot_id": data["spot_b"].id, "reservation_count": 1},
    ]


@pytest.mark.parametrize(
    "query",
    [
        "?date_from=not-a-date",
        "?date_to=not-a-date",
        "?date_from=2026-06-05&date_to=2026-06-01",
    ],
)
def test_invalid_report_date_filters_are_rejected(
    client: TestClient,
    db_session: Session,
    query: str,
) -> None:
    data = create_report_data(db_session)

    response = client.get(f"/admin/reports/summary{query}", headers=bearer_header(data["admin"]))

    assert response.status_code == 422


def test_reports_require_admin_authorization(client: TestClient, db_session: Session) -> None:
    data = create_report_data(db_session)

    employee_response = client.get(
        "/admin/reports/summary",
        headers=bearer_header(data["employee"]),
    )
    missing_response = client.get("/admin/reports/summary")
    invalid_response = client.get(
        "/admin/reports/summary",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert employee_response.status_code == 403
    assert employee_response.json() == {"detail": "Not enough permissions"}
    assert missing_response.status_code == 401
    assert invalid_response.status_code == 401


@pytest.mark.parametrize(
    ("path", "expected_headers"),
    [
        (
            "/admin/reports/reservations.csv",
            [
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
            ],
        ),
        (
            "/admin/reports/availabilities.csv",
            [
                "id",
                "parking_spot_id",
                "owner_id",
                "start_at",
                "end_at",
                "status",
                "priority_until",
                "note",
                "created_at",
                "updated_at",
            ],
        ),
        (
            "/admin/reports/applications.csv",
            ["id", "availability_id", "applicant_id", "status", "note", "created_at", "updated_at"],
        ),
        (
            "/admin/reports/audit-logs.csv",
            [
                "id",
                "availability_id",
                "reservation_id",
                "selected_application_id",
                "selected_user_id",
                "trigger_source",
                "ranking_policy",
                "created_at",
            ],
        ),
    ],
)
def test_admin_csv_exports_have_stable_safe_headers(
    client: TestClient,
    db_session: Session,
    path: str,
    expected_headers: list[str],
) -> None:
    data = create_report_data(db_session)

    response = client.get(f"{path}?date_from=2026-06-01&date_to=2026-06-05", headers=bearer_header(data["admin"]))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith("attachment; filename=")
    rows = list(csv.reader(StringIO(response.text)))
    assert rows[0] == expected_headers
    assert len(rows) > 1
    serialized = response.text.lower()
    assert "hashed_password" not in serialized
    assert "password" not in serialized
    assert "access_token" not in serialized


def test_csv_exports_neutralize_spreadsheet_formula_values(
    client: TestClient,
    db_session: Session,
) -> None:
    data = create_report_data(db_session)
    application = data["contexts"][0][1]
    application.note = "=HYPERLINK(\"https://example.invalid\")"
    db_session.commit()

    response = client.get(
        "/admin/reports/applications.csv",
        headers=bearer_header(data["admin"]),
    )

    assert response.status_code == 200
    assert "'=HYPERLINK" in response.text

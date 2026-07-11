from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import JSON, Enum as SqlEnum, create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
from app.models.parking_application import ParkingApplicationStatus
from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog, ParkingAssignmentTriggerSource
from app.models.user import UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.users import UserRepository
from app.schemas.parking_assignment_audit_log import ParkingAssignmentAuditLogCreate, ParkingAssignmentAuditLogRead


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def create_audit_context(
    db_session: Session,
    *,
    suffix: str,
    trigger_source: ParkingAssignmentTriggerSource = ParkingAssignmentTriggerSource.SYSTEM,
) -> ParkingAssignmentAuditLog:
    user_repository = UserRepository(db_session)
    owner = user_repository.create(
        email=f"audit.owner.{suffix}@example.com",
        username=f"auditowner{suffix}",
        first_name="Audit",
        last_name="Owner",
        hashed_password="hashed-password",
        role=UserRole.PARKING_OWNER,
    )
    applicant = user_repository.create(
        email=f"audit.applicant.{suffix}@example.com",
        username=f"auditapplicant{suffix}",
        first_name="Audit",
        last_name="Applicant",
        hashed_password="hashed-password",
        role=UserRole.EMPLOYEE,
    )
    spot = ParkingSpotRepository(db_session).create(code=f"AU-{suffix}", owner_id=owner.id)
    start_at = datetime.now(UTC) + timedelta(days=1)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=spot.id,
        owner_id=owner.id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=4),
    )
    application = ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=applicant.id,
        status=ParkingApplicationStatus.SELECTED,
    )
    reservation = ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=application.id,
        parking_spot_id=spot.id,
        reserved_for_user_id=applicant.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
    )
    return ParkingAssignmentAuditLogRepository(db_session).create(
        availability_id=availability.id,
        reservation_id=reservation.id,
        selected_application_id=application.id,
        selected_user_id=applicant.id,
        rejected_application_ids=[],
        ranking_policy="same_team_soft_limit_recent_wins_v1",
        ranking_details=[
            {
                "application_id": application.id,
                "applicant_id": applicant.id,
                "recent_win_count": 0,
                "final_rank_position": 1,
                "selected": True,
            },
        ],
        trigger_source=trigger_source,
    )


def test_assignment_audit_log_model_metadata_contains_expected_columns_constraints_and_indexes() -> None:
    assert "parking_assignment_audit_logs" in Base.metadata.tables
    table = ParkingAssignmentAuditLog.__table__

    assert table.c.id.primary_key
    assert table.c.availability_id.index is True
    assert table.c.reservation_id.index is True
    assert table.c.selected_application_id.index is True
    assert table.c.selected_user_id.index is True
    assert isinstance(table.c.rejected_application_ids.type, JSON)
    assert isinstance(table.c.ranking_details.type, JSON)
    assert isinstance(table.c.trigger_source.type, SqlEnum)
    assert set(table.c.trigger_source.type.enums) == {
        "system",
        "manual_owner",
        "manual_admin",
        "scheduled",
        "admin_override",
    }
    assert table.c.created_at.index is True
    assert table.c.created_at.type.timezone is True
    assert "uq_parking_assignment_audit_logs_reservation_id" not in {
        constraint.name for constraint in table.constraints
    }
    assert list(table.c.availability_id.foreign_keys)[0].target_fullname == "parking_availabilities.id"
    assert list(table.c.reservation_id.foreign_keys)[0].target_fullname == "parking_reservations.id"
    assert list(table.c.selected_application_id.foreign_keys)[0].target_fullname == "parking_applications.id"
    assert list(table.c.selected_user_id.foreign_keys)[0].target_fullname == "users.id"


def test_assignment_audit_log_schemas_serialize_json_details() -> None:
    now = datetime.now(UTC)
    create_schema = ParkingAssignmentAuditLogCreate(
        availability_id=1,
        reservation_id=2,
        selected_application_id=3,
        selected_user_id=4,
        rejected_application_ids=[5, 6],
        ranking_policy="same_team_soft_limit_recent_wins_v1",
        ranking_details=[{"application_id": 3, "created_at": now.isoformat(), "selected": True}],
        trigger_source=ParkingAssignmentTriggerSource.SCHEDULED,
    )
    model = ParkingAssignmentAuditLog(id=7, created_at=now, **create_schema.model_dump())

    dumped = ParkingAssignmentAuditLogRead.model_validate(model).model_dump(mode="json")

    assert dumped["trigger_source"] == "scheduled"
    assert dumped["rejected_application_ids"] == [5, 6]
    assert dumped["ranking_details"][0]["created_at"] == now.isoformat()
    assert "hashed_password" not in dumped

    with pytest.raises(ValidationError):
        ParkingAssignmentAuditLogCreate(
            availability_id=0,
            reservation_id=0,
            selected_application_id=0,
            selected_user_id=0,
            rejected_application_ids=[],
            ranking_policy="",
            ranking_details=[],
            trigger_source=ParkingAssignmentTriggerSource.SYSTEM,
        )


def test_assignment_audit_log_repository_create_get_and_list_methods(db_session: Session) -> None:
    first = create_audit_context(db_session, suffix="first", trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER)
    second = create_audit_context(db_session, suffix="second", trigger_source=ParkingAssignmentTriggerSource.SCHEDULED)
    repository = ParkingAssignmentAuditLogRepository(db_session)

    assert repository.get_by_id(first.id).id == first.id
    assert repository.get_by_reservation_id(first.reservation_id).id == first.id
    assert repository.get_by_availability_id(first.availability_id).id == first.id
    assert repository.get_by_id(999) is None
    assert repository.get_by_reservation_id(999) is None
    assert repository.get_by_availability_id(999) is None
    assert [audit.id for audit in repository.list()] == [second.id, first.id]
    assert [audit.id for audit in repository.list(skip=1, limit=1)] == [first.id]
    assert [audit.id for audit in repository.list_by_selected_user_id(first.selected_user_id)] == [first.id]


def test_assignment_audit_log_repository_preserves_multiple_events_for_one_reservation(db_session: Session) -> None:
    existing = create_audit_context(db_session, suffix="duplicate")
    replacement = ParkingAssignmentAuditLogRepository(db_session).create(
        availability_id=existing.availability_id,
        reservation_id=existing.reservation_id,
        selected_application_id=existing.selected_application_id,
        selected_user_id=existing.selected_user_id,
        rejected_application_ids=[],
        ranking_policy="admin_override_replacement_v1",
        ranking_details=[{"action": "replacement"}],
        trigger_source=ParkingAssignmentTriggerSource.ADMIN_OVERRIDE,
    )
    repository = ParkingAssignmentAuditLogRepository(db_session)

    assert repository.get_by_reservation_id(existing.reservation_id).id == replacement.id
    assert repository.get_by_availability_id(existing.availability_id).id == replacement.id
    assert [audit.id for audit in repository.list(reservation_id=existing.reservation_id)] == [
        replacement.id,
        existing.id,
    ]

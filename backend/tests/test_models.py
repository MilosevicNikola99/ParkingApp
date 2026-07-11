from datetime import UTC, datetime, timedelta

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.models.parking_spot import ParkingSpot
from app.models.team import Team
from app.models.user import User, UserRole


def test_model_metadata_contains_current_domain_tables() -> None:
    assert "parking_assignment_audit_logs" in Base.metadata.tables
    assert "parking_applications" in Base.metadata.tables
    assert "parking_availabilities" in Base.metadata.tables
    assert "parking_reservations" in Base.metadata.tables
    assert "parking_spots" in Base.metadata.tables
    assert "teams" in Base.metadata.tables
    assert "users" in Base.metadata.tables


def test_team_model_columns_and_indexes_are_configured() -> None:
    table = Team.__table__

    assert table.c.id.primary_key
    assert table.c.name.nullable is False
    assert table.c.name.unique is True
    assert table.c.name.index is True
    assert table.c.description.nullable is True
    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True


def test_user_model_columns_constraints_and_relationships_are_configured() -> None:
    table = User.__table__

    assert table.c.id.primary_key
    assert table.c.email.unique is True
    assert table.c.email.index is True
    assert table.c.username.unique is True
    assert table.c.username.index is True
    assert table.c.hashed_password.nullable is False
    assert table.c.team_id.index is True
    assert table.c.is_active.nullable is False
    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True

    role_type = table.c.role.type
    assert isinstance(role_type, SqlEnum)
    assert set(role_type.enums) == {"admin", "employee", "parking_owner"}

    foreign_keys = list(table.c.team_id.foreign_keys)
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "teams.id"
    assert User.team.property.mapper.class_ is Team
    assert Team.users.property.mapper.class_ is User


def test_parking_spot_model_columns_constraints_and_relationships_are_configured() -> None:
    table = ParkingSpot.__table__

    assert table.c.id.primary_key
    assert table.c.code.nullable is False
    assert table.c.code.unique is True
    assert table.c.code.index is True
    assert table.c.location.nullable is True
    assert table.c.description.nullable is True
    assert table.c.owner_id.nullable is True
    assert table.c.owner_id.index is True
    assert table.c.is_active.nullable is False
    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True

    foreign_keys = list(table.c.owner_id.foreign_keys)
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "users.id"
    assert ParkingSpot.owner.property.mapper.class_ is User
    assert User.owned_parking_spots.property.mapper.class_ is ParkingSpot
    assert ParkingSpot.availabilities.property.mapper.class_ is ParkingAvailability


def test_parking_availability_model_columns_constraints_indexes_and_relationships_are_configured() -> None:
    table = ParkingAvailability.__table__

    assert table.c.id.primary_key
    assert table.c.parking_spot_id.nullable is False
    assert table.c.parking_spot_id.index is True
    assert table.c.owner_id.nullable is False
    assert table.c.owner_id.index is True
    assert table.c.start_at.nullable is False
    assert table.c.start_at.index is True
    assert table.c.start_at.type.timezone is True
    assert table.c.end_at.nullable is False
    assert table.c.end_at.index is True
    assert table.c.end_at.type.timezone is True
    assert table.c.status.nullable is False
    assert table.c.status.index is True
    assert table.c.note.nullable is True
    assert table.c.priority_until.nullable is True
    assert table.c.priority_until.type.timezone is True
    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True

    status_type = table.c.status.type
    assert isinstance(status_type, SqlEnum)
    assert set(status_type.enums) == {"open", "assigned", "cancelled", "expired"}

    parking_spot_foreign_keys = list(table.c.parking_spot_id.foreign_keys)
    owner_foreign_keys = list(table.c.owner_id.foreign_keys)
    assert len(parking_spot_foreign_keys) == 1
    assert parking_spot_foreign_keys[0].target_fullname == "parking_spots.id"
    assert len(owner_foreign_keys) == 1
    assert owner_foreign_keys[0].target_fullname == "users.id"
    assert ParkingAvailability.parking_spot.property.mapper.class_ is ParkingSpot
    assert ParkingAvailability.owner.property.mapper.class_ is User
    assert ParkingAvailability.applications.property.mapper.class_ is ParkingApplication
    assert ParkingAvailability.reservations.property.mapper.class_ is ParkingReservation
    assert User.published_availabilities.property.mapper.class_ is ParkingAvailability

    index_names = {index.name for index in table.indexes}
    assert "ix_parking_availabilities_status_start_at" in index_names
    assert "ix_parking_availabilities_spot_start_end" in index_names


def test_parking_application_model_columns_constraints_indexes_and_relationships_are_configured() -> None:
    table = ParkingApplication.__table__

    assert table.c.id.primary_key
    assert table.c.availability_id.nullable is False
    assert table.c.availability_id.index is True
    assert table.c.applicant_id.nullable is False
    assert table.c.applicant_id.index is True
    assert table.c.status.nullable is False
    assert table.c.status.index is True
    assert table.c.note.nullable is True
    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True

    status_type = table.c.status.type
    assert isinstance(status_type, SqlEnum)
    assert set(status_type.enums) == {"pending", "selected", "cancelled", "rejected"}

    availability_foreign_keys = list(table.c.availability_id.foreign_keys)
    applicant_foreign_keys = list(table.c.applicant_id.foreign_keys)
    assert len(availability_foreign_keys) == 1
    assert availability_foreign_keys[0].target_fullname == "parking_availabilities.id"
    assert len(applicant_foreign_keys) == 1
    assert applicant_foreign_keys[0].target_fullname == "users.id"

    unique_constraint_names = {constraint.name for constraint in table.constraints}
    assert "uq_parking_applications_availability_id_applicant_id" in unique_constraint_names

    index_names = {index.name for index in table.indexes}
    assert "ix_parking_applications_availability_status" in index_names

    assert ParkingApplication.availability.property.mapper.class_ is ParkingAvailability
    assert ParkingApplication.applicant.property.mapper.class_ is User
    assert ParkingApplication.reservation.property.mapper.class_ is ParkingReservation
    assert User.parking_applications.property.mapper.class_ is ParkingApplication


def test_parking_reservation_model_columns_constraints_indexes_and_relationships_are_configured() -> None:
    table = ParkingReservation.__table__

    assert table.c.id.primary_key
    assert table.c.availability_id.nullable is False
    assert table.c.availability_id.index is True
    assert table.c.application_id.nullable is True
    assert table.c.application_id.index is True
    assert table.c.parking_spot_id.nullable is False
    assert table.c.parking_spot_id.index is True
    assert table.c.reserved_for_user_id.nullable is False
    assert table.c.reserved_for_user_id.index is True
    assert table.c.start_at.nullable is False
    assert table.c.start_at.index is True
    assert table.c.start_at.type.timezone is True
    assert table.c.end_at.nullable is False
    assert table.c.end_at.index is True
    assert table.c.end_at.type.timezone is True
    assert table.c.status.nullable is False
    assert table.c.status.index is True
    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True

    status_type = table.c.status.type
    assert isinstance(status_type, SqlEnum)
    assert set(status_type.enums) == {"active", "cancelled", "completed"}

    availability_foreign_keys = list(table.c.availability_id.foreign_keys)
    application_foreign_keys = list(table.c.application_id.foreign_keys)
    parking_spot_foreign_keys = list(table.c.parking_spot_id.foreign_keys)
    reserved_for_user_foreign_keys = list(table.c.reserved_for_user_id.foreign_keys)
    assert len(availability_foreign_keys) == 1
    assert availability_foreign_keys[0].target_fullname == "parking_availabilities.id"
    assert len(application_foreign_keys) == 1
    assert application_foreign_keys[0].target_fullname == "parking_applications.id"
    assert len(parking_spot_foreign_keys) == 1
    assert parking_spot_foreign_keys[0].target_fullname == "parking_spots.id"
    assert len(reserved_for_user_foreign_keys) == 1
    assert reserved_for_user_foreign_keys[0].target_fullname == "users.id"

    unique_constraint_names = {constraint.name for constraint in table.constraints}
    assert "uq_parking_reservations_availability_id" not in unique_constraint_names
    assert "uq_parking_reservations_application_id" in unique_constraint_names

    index_names = {index.name for index in table.indexes}
    active_availability_index = next(
        index for index in table.indexes if index.name == "uq_parking_reservations_active_availability_id"
    )
    assert active_availability_index.unique is True
    assert active_availability_index.dialect_options["postgresql"]["where"] is not None
    assert active_availability_index.dialect_options["sqlite"]["where"] is not None
    assert "ix_parking_reservations_spot_start_end" in index_names
    assert "ix_parking_reservations_user_status" in index_names

    assert ParkingReservation.availability.property.mapper.class_ is ParkingAvailability
    assert ParkingReservation.application.property.mapper.class_ is ParkingApplication
    assert ParkingReservation.parking_spot.property.mapper.class_ is ParkingSpot
    assert ParkingReservation.reserved_for_user.property.mapper.class_ is User
    assert ParkingSpot.reservations.property.mapper.class_ is ParkingReservation
    assert User.parking_reservations.property.mapper.class_ is ParkingReservation


def test_models_can_create_tables_and_persist_basic_records_with_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
        "parking_assignment_audit_logs",
        "parking_applications",
        "parking_availabilities",
        "parking_reservations",
        "parking_spots",
        "teams",
        "users",
    }

    with Session(engine) as session:
        start_at = datetime.now(UTC)
        end_at = start_at + timedelta(hours=8)
        priority_until = start_at + timedelta(hours=2)
        team = Team(name="Engineering", description="Product engineering")
        user = User(
            email="ada.lovelace@example.com",
            username="alovelace",
            first_name="Ada",
            last_name="Lovelace",
            hashed_password="hashed-password",
            role=UserRole.EMPLOYEE,
            team=team,
        )
        parking_spot = ParkingSpot(
            code="A-12",
            location="Garage P1",
            description="Near elevator",
            owner=user,
        )
        availability = ParkingAvailability(
            parking_spot=parking_spot,
            owner=user,
            start_at=start_at,
            end_at=end_at,
            note="Working from home",
            priority_until=priority_until,
        )
        application = ParkingApplication(
            availability=availability,
            applicant=user,
            note="I need the spot for a client visit",
        )
        reservation = ParkingReservation(
            availability=availability,
            application=application,
            parking_spot=parking_spot,
            reserved_for_user=user,
            start_at=start_at,
            end_at=end_at,
        )
        session.add(reservation)
        session.commit()
        session.refresh(user)
        session.refresh(parking_spot)
        session.refresh(availability)
        session.refresh(application)
        session.refresh(reservation)

        assert user.id is not None
        assert user.team is team
        assert user.role is UserRole.EMPLOYEE
        assert user.is_active is True
        assert parking_spot.id is not None
        assert parking_spot.owner is user
        assert parking_spot in user.owned_parking_spots
        assert parking_spot.is_active is True
        assert availability.id is not None
        assert availability.parking_spot is parking_spot
        assert availability.owner is user
        assert availability.status is ParkingAvailabilityStatus.OPEN
        assert availability in parking_spot.availabilities
        assert availability in user.published_availabilities
        assert application.id is not None
        assert application.availability is availability
        assert application.applicant is user
        assert application.status is ParkingApplicationStatus.PENDING
        assert application in availability.applications
        assert application in user.parking_applications
        assert reservation.id is not None
        assert reservation.availability is availability
        assert reservation.application is application
        assert reservation.parking_spot is parking_spot
        assert reservation.reserved_for_user is user
        assert reservation.status is ParkingReservationStatus.ACTIVE
        assert reservation in availability.reservations
        assert application.reservation is reservation
        assert reservation in parking_spot.reservations
        assert reservation in user.parking_reservations

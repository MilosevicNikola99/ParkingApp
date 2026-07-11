from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.models.parking_spot import ParkingSpot
from app.models.team import Team
from app.models.user import User, UserRole
from app.schemas.parking_availability import (
    ParkingAvailabilityCreate,
    ParkingAvailabilityRead,
    ParkingAvailabilityUpdate,
)
from app.schemas.parking_application import (
    ParkingApplicationCreate,
    ParkingApplicationRead,
    ParkingApplicationUpdate,
)
from app.schemas.parking_reservation import (
    ParkingReassignmentRequest,
    ParkingReservationCreate,
    ParkingReservationHistoryRead,
    ParkingReservationHistoryState,
    ParkingReservationRead,
    ParkingReservationUpdate,
)
from app.schemas.parking_spot import ParkingSpotCreate, ParkingSpotRead, ParkingSpotUpdate
from app.schemas.team import TeamCreate, TeamRead, TeamUpdate
from app.schemas.user import UserCreate, UserRead, UserUpdate


def test_team_schemas_validate_and_serialize_from_model() -> None:
    create_schema = TeamCreate(name="Engineering", description="Product engineering")
    update_schema = TeamUpdate(name="Platform")
    now = datetime.now(UTC)
    team = Team(id=1, name=create_schema.name, description=create_schema.description, created_at=now, updated_at=now)

    read_schema = TeamRead.model_validate(team)

    assert create_schema.name == "Engineering"
    assert update_schema.model_dump(exclude_unset=True) == {"name": "Platform"}
    assert read_schema.model_dump()["id"] == 1
    assert read_schema.model_dump()["name"] == "Engineering"


def test_team_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        TeamCreate(name="", description=None)


def test_team_update_rejects_null_name() -> None:
    with pytest.raises(ValidationError):
        TeamUpdate(name=None)


def test_parking_spot_schemas_validate_and_serialize_from_model() -> None:
    create_schema = ParkingSpotCreate(
        code="A-12",
        location="Garage P1",
        description="Near elevator",
        owner_id=7,
        is_active=True,
    )
    update_schema = ParkingSpotUpdate(location="Garage P2", owner_id=None)
    now = datetime.now(UTC)
    parking_spot = ParkingSpot(
        id=3,
        code=create_schema.code,
        location=create_schema.location,
        description=create_schema.description,
        owner_id=create_schema.owner_id,
        is_active=create_schema.is_active,
        created_at=now,
        updated_at=now,
    )

    read_schema = ParkingSpotRead.model_validate(parking_spot)
    dumped = read_schema.model_dump()

    assert create_schema.code == "A-12"
    assert update_schema.model_dump(exclude_unset=True) == {
        "location": "Garage P2",
        "owner_id": None,
    }
    assert dumped["id"] == 3
    assert dumped["code"] == "A-12"
    assert dumped["owner_id"] == 7


def test_parking_spot_create_rejects_blank_code() -> None:
    with pytest.raises(ValidationError):
        ParkingSpotCreate(code="")


@pytest.mark.parametrize("field", ["code", "is_active"])
def test_parking_spot_update_rejects_null_required_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        ParkingSpotUpdate(**{field: None})


def test_parking_spot_update_allows_clearing_optional_fields() -> None:
    schema = ParkingSpotUpdate(location=None, description=None, owner_id=None)

    assert schema.model_dump(exclude_unset=True) == {
        "location": None,
        "description": None,
        "owner_id": None,
    }


def test_parking_spot_read_does_not_expose_owner_sensitive_fields() -> None:
    now = datetime.now(UTC)
    parking_spot = ParkingSpot(
        id=1,
        code="B-22",
        owner_id=4,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    dumped = ParkingSpotRead.model_validate(parking_spot).model_dump(mode="json")

    assert dumped["owner_id"] == 4
    assert "owner" not in dumped
    assert "hashed_password" not in dumped
    assert "password" not in dumped


def test_parking_availability_schemas_validate_and_serialize_from_model() -> None:
    start_at = datetime.now(UTC)
    end_at = start_at + timedelta(hours=8)
    priority_until = start_at + timedelta(hours=2)
    create_schema = ParkingAvailabilityCreate(
        parking_spot_id=3,
        start_at=start_at,
        end_at=end_at,
        note="Remote day",
    )
    update_schema = ParkingAvailabilityUpdate(
        status=ParkingAvailabilityStatus.CANCELLED,
        note=None,
    )
    availability = ParkingAvailability(
        id=5,
        parking_spot_id=create_schema.parking_spot_id,
        owner_id=7,
        start_at=create_schema.start_at,
        end_at=create_schema.end_at,
        status=ParkingAvailabilityStatus.OPEN,
        note=create_schema.note,
        priority_until=priority_until,
        created_at=start_at,
        updated_at=start_at,
    )

    read_schema = ParkingAvailabilityRead.model_validate(availability)
    dumped = read_schema.model_dump(mode="json")

    assert create_schema.model_dump(exclude={"start_at", "end_at"}) == {
        "parking_spot_id": 3,
        "note": "Remote day",
    }
    assert update_schema.model_dump(exclude_unset=True, mode="json") == {
        "status": "cancelled",
        "note": None,
    }
    assert dumped["id"] == 5
    assert dumped["parking_spot_id"] == 3
    assert dumped["owner_id"] == 7
    assert dumped["status"] == "open"
    assert "parking_spot" not in dumped
    assert "owner" not in dumped
    assert "hashed_password" not in dumped


@pytest.mark.parametrize("end_delta", [timedelta(0), -timedelta(minutes=1)])
def test_parking_availability_create_rejects_end_at_not_after_start_at(end_delta: timedelta) -> None:
    start_at = datetime.now(UTC)

    with pytest.raises(ValidationError):
        ParkingAvailabilityCreate(
            parking_spot_id=1,
            start_at=start_at,
            end_at=start_at + end_delta,
        )


def test_parking_availability_create_rejects_naive_datetimes() -> None:
    start_at = datetime(2026, 6, 3, 8, 0)

    with pytest.raises(ValidationError):
        ParkingAvailabilityCreate(
            parking_spot_id=1,
            start_at=start_at,
            end_at=start_at + timedelta(hours=8),
        )


@pytest.mark.parametrize("field", ["start_at", "end_at", "status"])
def test_parking_availability_update_rejects_null_required_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        ParkingAvailabilityUpdate(**{field: None})


def test_parking_availability_update_rejects_invalid_interval_when_both_dates_provided() -> None:
    start_at = datetime.now(UTC)

    with pytest.raises(ValidationError):
        ParkingAvailabilityUpdate(start_at=start_at, end_at=start_at)


def test_parking_availability_update_allows_note_to_be_cleared() -> None:
    schema = ParkingAvailabilityUpdate(note=None)

    assert schema.model_dump(exclude_unset=True) == {"note": None}


def test_parking_application_schemas_validate_and_serialize_from_model() -> None:
    now = datetime.now(UTC)
    create_schema = ParkingApplicationCreate(
        availability_id=5,
        note="I have an offsite meeting",
    )
    update_schema = ParkingApplicationUpdate(
        status=ParkingApplicationStatus.CANCELLED,
        note=None,
    )
    application = ParkingApplication(
        id=9,
        availability_id=create_schema.availability_id,
        applicant_id=7,
        status=ParkingApplicationStatus.PENDING,
        note=create_schema.note,
        created_at=now,
        updated_at=now,
    )

    read_schema = ParkingApplicationRead.model_validate(application)
    dumped = read_schema.model_dump(mode="json")

    assert create_schema.model_dump() == {
        "availability_id": 5,
        "note": "I have an offsite meeting",
    }
    assert "applicant_id" not in create_schema.model_fields_set
    assert update_schema.model_dump(exclude_unset=True, mode="json") == {
        "status": "cancelled",
        "note": None,
    }
    assert dumped["id"] == 9
    assert dumped["availability_id"] == 5
    assert dumped["applicant_id"] == 7
    assert dumped["status"] == "pending"
    assert "availability" not in dumped
    assert "applicant" not in dumped
    assert "hashed_password" not in dumped


def test_parking_application_create_rejects_invalid_availability_id() -> None:
    with pytest.raises(ValidationError):
        ParkingApplicationCreate(availability_id=0)


def test_parking_application_update_rejects_null_status() -> None:
    with pytest.raises(ValidationError):
        ParkingApplicationUpdate(status=None)


def test_parking_application_update_allows_note_to_be_cleared() -> None:
    schema = ParkingApplicationUpdate(note=None)

    assert schema.model_dump(exclude_unset=True) == {"note": None}


def test_parking_reservation_schemas_validate_and_serialize_from_model() -> None:
    start_at = datetime.now(UTC)
    end_at = start_at + timedelta(hours=8)
    create_schema = ParkingReservationCreate(
        availability_id=5,
        application_id=None,
        parking_spot_id=3,
        reserved_for_user_id=7,
        start_at=start_at,
        end_at=end_at,
    )
    update_schema = ParkingReservationUpdate(status=ParkingReservationStatus.CANCELLED)
    reservation = ParkingReservation(
        id=11,
        availability_id=create_schema.availability_id,
        application_id=create_schema.application_id,
        parking_spot_id=create_schema.parking_spot_id,
        reserved_for_user_id=create_schema.reserved_for_user_id,
        start_at=create_schema.start_at,
        end_at=create_schema.end_at,
        status=ParkingReservationStatus.ACTIVE,
        created_at=start_at,
        updated_at=start_at,
    )

    read_schema = ParkingReservationRead.model_validate(reservation)
    dumped = read_schema.model_dump(mode="json")

    assert create_schema.model_dump(exclude={"start_at", "end_at"}) == {
        "availability_id": 5,
        "application_id": None,
        "parking_spot_id": 3,
        "reserved_for_user_id": 7,
        "status": ParkingReservationStatus.ACTIVE,
    }
    assert update_schema.model_dump(exclude_unset=True, mode="json") == {"status": "cancelled"}
    assert dumped["id"] == 11
    assert dumped["availability_id"] == 5
    assert dumped["application_id"] is None
    assert dumped["parking_spot_id"] == 3
    assert dumped["reserved_for_user_id"] == 7
    assert dumped["status"] == "active"
    assert "reserved_for_user" not in dumped
    assert "parking_spot" not in dumped
    assert "hashed_password" not in dumped


@pytest.mark.parametrize(
    ("status", "expected_history_state"),
    [
        (ParkingReservationStatus.ACTIVE, ParkingReservationHistoryState.CURRENT_ACTIVE),
        (ParkingReservationStatus.CANCELLED, ParkingReservationHistoryState.HISTORICAL),
        (ParkingReservationStatus.COMPLETED, ParkingReservationHistoryState.HISTORICAL),
    ],
)
def test_parking_reservation_history_schema_marks_current_active_and_historical_records(
    status: ParkingReservationStatus,
    expected_history_state: ParkingReservationHistoryState,
) -> None:
    start_at = datetime.now(UTC)
    reservation = ParkingReservation(
        id=11,
        availability_id=5,
        application_id=7,
        parking_spot_id=3,
        reserved_for_user_id=9,
        start_at=start_at,
        end_at=start_at + timedelta(hours=8),
        status=status,
        created_at=start_at,
        updated_at=start_at,
    )

    history_read = ParkingReservationHistoryRead.from_reservation(reservation)

    assert history_read.history_state is expected_history_state
    assert history_read.model_dump(mode="json")["history_state"] == expected_history_state.value


@pytest.mark.parametrize("end_delta", [timedelta(0), -timedelta(minutes=1)])
def test_parking_reservation_create_rejects_end_at_not_after_start_at(end_delta: timedelta) -> None:
    start_at = datetime.now(UTC)

    with pytest.raises(ValidationError):
        ParkingReservationCreate(
            availability_id=1,
            application_id=None,
            parking_spot_id=1,
            reserved_for_user_id=1,
            start_at=start_at,
            end_at=start_at + end_delta,
        )


def test_parking_reservation_create_rejects_naive_datetimes() -> None:
    start_at = datetime(2026, 6, 3, 8, 0)

    with pytest.raises(ValidationError):
        ParkingReservationCreate(
            availability_id=1,
            application_id=None,
            parking_spot_id=1,
            reserved_for_user_id=1,
            start_at=start_at,
            end_at=start_at + timedelta(hours=8),
        )


def test_parking_reservation_create_rejects_invalid_identifiers() -> None:
    start_at = datetime.now(UTC)

    with pytest.raises(ValidationError):
        ParkingReservationCreate(
            availability_id=0,
            application_id=0,
            parking_spot_id=0,
            reserved_for_user_id=0,
            start_at=start_at,
            end_at=start_at + timedelta(hours=8),
        )


def test_parking_reservation_update_rejects_null_status() -> None:
    with pytest.raises(ValidationError):
        ParkingReservationUpdate(status=None)


def test_parking_reassignment_request_normalizes_optional_reason() -> None:
    assert ParkingReassignmentRequest(reason="  Reassign  ").reason == "Reassign"
    assert ParkingReassignmentRequest(reason="   ").reason is None
    assert ParkingReassignmentRequest().reason is None


def test_user_create_validates_email_role_and_password() -> None:
    schema = UserCreate(
        email="grace.hopper@example.com",
        username="ghopper",
        first_name="Grace",
        last_name="Hopper",
        password="long-enough-password",
        role=UserRole.ADMIN,
    )

    dumped = schema.model_dump(mode="json")

    assert dumped["email"] == "grace.hopper@example.com"
    assert dumped["role"] == "admin"
    assert dumped["password"] == "long-enough-password"


def test_user_create_rejects_invalid_email_and_short_password() -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            email="not-an-email",
            username="baduser",
            first_name="Bad",
            last_name="User",
            password="short",
        )


def test_user_create_rejects_password_over_bcrypt_limit() -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            email="long.password@example.com",
            username="longpass",
            first_name="Long",
            last_name="Password",
            password="a" * 73,
        )


def test_user_update_allows_partial_changes() -> None:
    schema = UserUpdate(first_name="Updated", is_active=False)

    assert schema.model_dump(exclude_unset=True) == {
        "first_name": "Updated",
        "is_active": False,
    }


def test_user_update_allows_clearing_team_id_only() -> None:
    schema = UserUpdate(team_id=None)

    assert schema.model_dump(exclude_unset=True) == {"team_id": None}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", None),
        ("username", None),
        ("first_name", None),
        ("last_name", None),
        ("password", None),
        ("role", None),
        ("is_active", None),
    ],
)
def test_user_update_rejects_null_non_nullable_fields(field: str, value: None) -> None:
    with pytest.raises(ValidationError):
        UserUpdate(**{field: value})


def test_user_read_serializes_from_model_without_hashed_password() -> None:
    now = datetime.now(UTC)
    user = User(
        id=7,
        email="katherine.johnson@example.com",
        username="kjohnson",
        first_name="Katherine",
        last_name="Johnson",
        hashed_password="must-not-leak",
        role=UserRole.EMPLOYEE,
        team_id=3,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    read_schema = UserRead.model_validate(user)
    dumped = read_schema.model_dump(mode="json")

    assert dumped["id"] == 7
    assert dumped["email"] == "katherine.johnson@example.com"
    assert dumped["role"] == "employee"
    assert "hashed_password" not in dumped
    assert "password" not in dumped

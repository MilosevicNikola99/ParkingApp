from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
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
from app.services.parking_reservation_cancellation import (
    ParkingReservationCancellationActorType,
    ParkingReservationCancellationAdminReasonRequiredError,
    ParkingReservationCancellationAuditPersistenceError,
    ParkingReservationCancellationNotActiveError,
    ParkingReservationCancellationNotFoundError,
    ParkingReservationCancellationPermissionError,
    ParkingReservationCancellationService,
)

TEST_NOW = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def create_service(
    db_session: Session,
    *,
    audit_repository: ParkingAssignmentAuditLogRepository | None = None,
) -> ParkingReservationCancellationService:
    return ParkingReservationCancellationService(
        reservation_repository=ParkingReservationRepository(db_session),
        availability_repository=ParkingAvailabilityRepository(db_session),
        application_repository=ParkingApplicationRepository(db_session),
        audit_log_repository=audit_repository,
        user_repository=UserRepository(db_session),
        now_provider=lambda: TEST_NOW,
    )


def create_user(
    db_session: Session,
    suffix: str,
    *,
    role: UserRole = UserRole.EMPLOYEE,
    is_active: bool = True,
) -> User:
    return UserRepository(db_session).create(
        email=f"cancellation.{suffix}@example.com",
        username=f"cancellation{suffix}",
        first_name="Cancellation",
        last_name="Service",
        hashed_password="hashed-password",
        role=role,
        is_active=is_active,
    )


def create_context(
    db_session: Session,
    suffix: str,
    *,
    reservation_status: ParkingReservationStatus = ParkingReservationStatus.ACTIVE,
    availability_end_at: datetime | None = None,
) -> tuple[User, User, ParkingAvailability, ParkingApplication, ParkingReservation, ParkingApplication]:
    owner = create_user(db_session, f"owner{suffix}", role=UserRole.PARKING_OWNER)
    reserved_user = create_user(db_session, f"reserved{suffix}")
    pending_user = create_user(db_session, f"pending{suffix}")
    spot = ParkingSpotRepository(db_session).create(code=f"CAN-{suffix}", owner_id=owner.id)
    end_at = availability_end_at or TEST_NOW + timedelta(hours=8)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=spot.id,
        owner_id=owner.id,
        start_at=end_at - timedelta(hours=4),
        end_at=end_at,
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


def test_reserved_user_can_cancel_own_active_reservation_without_selecting_replacement(
    db_session: Session,
) -> None:
    _, reserved_user, availability, selected_application, reservation, pending_application = create_context(
        db_session,
        "user",
    )

    result = create_service(db_session).cancel_my_reservation(
        reservation.id,
        reserved_user.id,
        "  Personal schedule change  ",
    )

    assert result.actor_type is ParkingReservationCancellationActorType.RESERVED_USER
    assert result.reservation.status is ParkingReservationStatus.CANCELLED
    assert result.availability.status is ParkingAvailabilityStatus.OPEN
    assert result.application.status is ParkingApplicationStatus.CANCELLED
    assert result.audit_log is None
    assert ParkingApplicationRepository(db_session).get_by_id(pending_application.id).status is (
        ParkingApplicationStatus.PENDING
    )
    assert ParkingReservationRepository(db_session).get_by_id(reservation.id).application_id == selected_application.id
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability.id).status is ParkingAvailabilityStatus.OPEN


def test_owner_can_cancel_and_create_owner_audit(db_session: Session) -> None:
    owner, reserved_user, availability, selected_application, reservation, _ = create_context(db_session, "owner")

    result = create_service(db_session).cancel_as_owner(
        reservation.id,
        owner.id,
        "  Owner schedule changed  ",
    )

    assert result.actor_type is ParkingReservationCancellationActorType.AVAILABILITY_OWNER
    assert result.reservation.status is ParkingReservationStatus.CANCELLED
    assert result.availability.status is ParkingAvailabilityStatus.OPEN
    assert result.application.status is ParkingApplicationStatus.REJECTED
    assert result.audit_log is not None
    assert result.audit_log.trigger_source is ParkingAssignmentTriggerSource.MANUAL_OWNER
    assert result.audit_log.rejected_application_ids == [selected_application.id]
    assert result.audit_log.ranking_details == [
        {
            "action": "cancellation",
            "cancellation_actor_type": "availability_owner",
            "actor_user_id": owner.id,
            "reason": "Owner schedule changed",
            "reservation_id": reservation.id,
            "availability_id": availability.id,
            "previous_application_id": selected_application.id,
            "previous_user_id": reserved_user.id,
            "reservation_status": "cancelled",
            "availability_status": "open",
            "application_status": "rejected",
            "owner_user_id": owner.id,
        },
    ]


def test_admin_can_cancel_any_active_reservation_with_reason_and_audit(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, reserved_user, availability, selected_application, reservation, _ = create_context(db_session, "admin")

    result = create_service(db_session).cancel_as_admin(
        reservation.id,
        admin.id,
        "  Policy exception  ",
    )

    assert result.actor_type is ParkingReservationCancellationActorType.ADMIN
    assert result.application.status is ParkingApplicationStatus.REJECTED
    assert result.audit_log is not None
    assert result.audit_log.trigger_source is ParkingAssignmentTriggerSource.ADMIN_OVERRIDE
    assert result.audit_log.ranking_details[0]["action"] == "cancellation"
    assert result.audit_log.ranking_details[0]["reason"] == "Policy exception"
    assert result.audit_log.ranking_details[0]["admin_user_id"] == admin.id
    assert result.audit_log.ranking_details[0]["reservation_id"] == reservation.id
    assert result.audit_log.ranking_details[0]["availability_id"] == availability.id
    assert result.audit_log.ranking_details[0]["previous_application_id"] == selected_application.id
    assert result.audit_log.ranking_details[0]["previous_user_id"] == reserved_user.id


def test_cancellation_expires_availability_when_end_time_is_not_future(db_session: Session) -> None:
    _, reserved_user, _, _, reservation, _ = create_context(
        db_session,
        "expired",
        availability_end_at=TEST_NOW,
    )

    result = create_service(db_session).cancel_my_reservation(reservation.id, reserved_user.id)

    assert result.availability.status is ParkingAvailabilityStatus.EXPIRED


def test_unrelated_user_cannot_cancel_reservation(db_session: Session) -> None:
    unrelated = create_user(db_session, "unrelated")
    _, _, _, _, reservation, _ = create_context(db_session, "forbidden")

    with pytest.raises(ParkingReservationCancellationPermissionError):
        create_service(db_session).cancel_for_user_or_owner(reservation.id, unrelated.id)


def test_missing_and_non_active_reservations_are_rejected(db_session: Session) -> None:
    service = create_service(db_session)

    with pytest.raises(ParkingReservationCancellationNotFoundError):
        service.cancel_for_user_or_owner(999, 1)

    _, reserved_user, _, _, reservation, _ = create_context(
        db_session,
        "inactive",
        reservation_status=ParkingReservationStatus.CANCELLED,
    )
    with pytest.raises(ParkingReservationCancellationNotActiveError):
        service.cancel_my_reservation(reservation.id, reserved_user.id)


@pytest.mark.parametrize("reason", ["", "   ", "\t\n"])
def test_admin_reason_is_required(db_session: Session, reason: str) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    with pytest.raises(ParkingReservationCancellationAdminReasonRequiredError):
        create_service(db_session).cancel_as_admin(1, admin.id, reason)


def test_non_admin_cannot_use_admin_cancellation(db_session: Session) -> None:
    employee = create_user(db_session, "employee")
    _, _, _, _, reservation, _ = create_context(db_session, "nonadmin")

    with pytest.raises(ParkingReservationCancellationPermissionError):
        create_service(db_session).cancel_as_admin(reservation.id, employee.id, "Reason")


def test_audit_failure_rolls_back_owner_cancellation(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, _, availability, selected_application, reservation, pending_application = create_context(
        db_session,
        "rollback",
    )
    audit_repository = ParkingAssignmentAuditLogRepository(db_session)
    service = create_service(db_session, audit_repository=audit_repository)
    owner_id = owner.id
    availability_id = availability.id
    selected_application_id = selected_application.id
    reservation_id = reservation.id
    pending_application_id = pending_application.id
    db_session.commit()

    def fail_audit_create(**_: object) -> None:
        raise RuntimeError("simulated cancellation audit failure")

    monkeypatch.setattr(audit_repository, "create", fail_audit_create)

    with pytest.raises(ParkingReservationCancellationAuditPersistenceError):
        service.cancel_as_owner(reservation_id, owner_id, "Reason")

    assert ParkingReservationRepository(db_session).get_by_id(reservation_id).status is ParkingReservationStatus.ACTIVE
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability_id).status is (
        ParkingAvailabilityStatus.ASSIGNED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(selected_application_id).status is (
        ParkingApplicationStatus.SELECTED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(pending_application_id).status is (
        ParkingApplicationStatus.PENDING
    )
    assert audit_repository.list(reservation_id=reservation_id) == []


def test_cancellation_uses_availability_reservation_and_application_lock_paths(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, reserved_user, _, _, reservation, _ = create_context(db_session, "locks")
    availability_repository = ParkingAvailabilityRepository(db_session)
    reservation_repository = ParkingReservationRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    service = ParkingReservationCancellationService(
        reservation_repository=reservation_repository,
        availability_repository=availability_repository,
        application_repository=application_repository,
        now_provider=lambda: TEST_NOW,
    )
    locks_called = {"availability": False, "reservation": False, "application": False}
    original_availability_lock = availability_repository.get_by_id_for_update
    original_reservation_lock = reservation_repository.get_by_id_for_update
    original_application_lock = application_repository.get_by_id_for_update

    def availability_lock_spy(availability_id: int) -> ParkingAvailability | None:
        locks_called["availability"] = True
        return original_availability_lock(availability_id)

    def reservation_lock_spy(reservation_id: int) -> ParkingReservation | None:
        locks_called["reservation"] = True
        return original_reservation_lock(reservation_id)

    def application_lock_spy(application_id: int) -> ParkingApplication | None:
        locks_called["application"] = True
        return original_application_lock(application_id)

    monkeypatch.setattr(availability_repository, "get_by_id_for_update", availability_lock_spy)
    monkeypatch.setattr(reservation_repository, "get_by_id_for_update", reservation_lock_spy)
    monkeypatch.setattr(application_repository, "get_by_id_for_update", application_lock_spy)

    service.cancel_my_reservation(reservation.id, reserved_user.id)

    assert locks_called == {"availability": True, "reservation": True, "application": True}

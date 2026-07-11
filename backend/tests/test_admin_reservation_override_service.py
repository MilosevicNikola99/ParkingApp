from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_assignment_audit_log import ParkingAssignmentTriggerSource
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_reservation import ParkingReservationStatus
from app.models.parking_spot import ParkingSpot
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.users import UserRepository
from app.services.admin_reservation_override import (
    AdminReservationOverrideAdminInactiveError,
    AdminReservationOverrideAdminNotFoundError,
    AdminReservationOverrideApplicantInactiveError,
    AdminReservationOverrideApplicationAvailabilityMismatchError,
    AdminReservationOverrideApplicationNotFoundError,
    AdminReservationOverrideApplicationNotPendingError,
    AdminReservationOverrideAuditPersistenceError,
    AdminReservationOverrideAvailabilityNotFoundError,
    AdminReservationOverrideAvailabilityNotOpenError,
    AdminReservationOverrideIntegrityError,
    AdminReservationOverridePermissionError,
    AdminReservationOverrideReasonRequiredError,
    AdminReservationOverrideReservationExistsError,
    AdminReservationOverrideService,
)
from app.services.parking_application_ranking import ParkingApplicationRankingService

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
    reservation_repository: ParkingReservationRepository | None = None,
) -> AdminReservationOverrideService:
    return AdminReservationOverrideService(
        availability_repository=ParkingAvailabilityRepository(db_session),
        application_repository=ParkingApplicationRepository(db_session),
        reservation_repository=reservation_repository or ParkingReservationRepository(db_session),
        audit_log_repository=audit_repository,
        user_repository=UserRepository(db_session),
    )


def create_user(
    db_session: Session,
    suffix: str,
    *,
    role: UserRole = UserRole.EMPLOYEE,
    is_active: bool = True,
) -> User:
    return UserRepository(db_session).create(
        email=f"override.{suffix}@example.com",
        username=f"override{suffix}",
        first_name="Override",
        last_name="User",
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
    spot = ParkingSpotRepository(db_session).create(code=f"OV-{suffix}", owner_id=owner.id)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=spot.id,
        owner_id=owner.id,
        start_at=TEST_NOW + timedelta(hours=1),
        end_at=TEST_NOW + timedelta(hours=9),
        status=status,
    )
    return spot, availability


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


def test_valid_admin_override_selects_requested_application_and_records_audit(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    spot, availability = create_context(db_session, "success")
    older_applicant = create_user(db_session, "older")
    requested_applicant = create_user(db_session, "requested")
    other_applicant = create_user(db_session, "other")
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
    other_application = create_application(
        db_session,
        availability,
        other_applicant,
        created_at=TEST_NOW + timedelta(minutes=20),
    )
    pending = ParkingApplicationRepository(db_session).list_pending_by_availability_id(availability.id)
    automatic_winner = ParkingApplicationRankingService(now_provider=lambda: TEST_NOW).select_winning_application(
        availability,
        pending,
    )
    assert automatic_winner.id == older_application.id

    result = create_service(db_session).override_assign_availability(
        availability.id,
        requested_application.id,
        admin.id,
        "  Accessibility requirement  ",
    )

    assert result.selected_application.id == requested_application.id
    assert result.selected_application.status is ParkingApplicationStatus.SELECTED
    assert {application.id for application in result.rejected_applications} == {
        older_application.id,
        other_application.id,
    }
    assert result.availability.status is ParkingAvailabilityStatus.ASSIGNED
    assert result.reservation.availability_id == availability.id
    assert result.reservation.application_id == requested_application.id
    assert result.reservation.parking_spot_id == spot.id
    assert result.reservation.reserved_for_user_id == requested_applicant.id
    assert result.reservation.start_at == availability.start_at
    assert result.reservation.end_at == availability.end_at
    assert result.reservation.status is ParkingReservationStatus.ACTIVE
    assert result.audit_log.availability_id == availability.id
    assert result.audit_log.reservation_id == result.reservation.id
    assert result.audit_log.selected_application_id == requested_application.id
    assert result.audit_log.selected_user_id == requested_applicant.id
    assert set(result.audit_log.rejected_application_ids) == {older_application.id, other_application.id}
    assert result.audit_log.ranking_policy == AdminReservationOverrideService.RANKING_POLICY
    assert result.audit_log.trigger_source is ParkingAssignmentTriggerSource.ADMIN_OVERRIDE
    assert result.audit_log.ranking_details == [
        {
            "assignment_method": "admin_override",
            "selection_basis": "manual_admin_selection",
            "admin_user_id": admin.id,
            "override_reason": "Accessibility requirement",
            "selected_application_id": requested_application.id,
            "selected_user_id": requested_applicant.id,
            "considered_pending_application_ids": [
                older_application.id,
                requested_application.id,
                other_application.id,
            ],
        },
    ]


@pytest.mark.parametrize("reason", ["", "   ", "\t\n"])
def test_blank_override_reason_is_rejected(db_session: Session, reason: str) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    with pytest.raises(AdminReservationOverrideReasonRequiredError):
        create_service(db_session).override_assign_availability(1, 1, admin.id, reason)


@pytest.mark.parametrize(
    ("admin_kind", "expected_error"),
    [
        ("missing", AdminReservationOverrideAdminNotFoundError),
        ("inactive", AdminReservationOverrideAdminInactiveError),
        ("employee", AdminReservationOverridePermissionError),
    ],
)
def test_invalid_admin_actor_is_rejected(
    db_session: Session,
    admin_kind: str,
    expected_error: type[Exception],
) -> None:
    if admin_kind == "missing":
        admin_id = 999
    else:
        admin = create_user(
            db_session,
            admin_kind,
            role=UserRole.ADMIN if admin_kind == "inactive" else UserRole.EMPLOYEE,
            is_active=admin_kind != "inactive",
        )
        admin_id = admin.id

    with pytest.raises(expected_error):
        create_service(db_session).override_assign_availability(1, 1, admin_id, "Reason")


def test_missing_availability_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    with pytest.raises(AdminReservationOverrideAvailabilityNotFoundError):
        create_service(db_session).override_assign_availability(999, 1, admin.id, "Reason")


def test_non_open_availability_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "closed", status=ParkingAvailabilityStatus.CANCELLED)

    with pytest.raises(AdminReservationOverrideAvailabilityNotOpenError):
        create_service(db_session).override_assign_availability(availability.id, 1, admin.id, "Reason")


def test_missing_application_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "missingapp")

    with pytest.raises(AdminReservationOverrideApplicationNotFoundError):
        create_service(db_session).override_assign_availability(availability.id, 999, admin.id, "Reason")


def test_application_from_another_availability_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "target")
    _, other_availability = create_context(db_session, "other")
    applicant = create_user(db_session, "applicant")
    other_application = create_application(db_session, other_availability, applicant)

    with pytest.raises(AdminReservationOverrideApplicationAvailabilityMismatchError):
        create_service(db_session).override_assign_availability(
            availability.id,
            other_application.id,
            admin.id,
            "Reason",
        )


def test_non_pending_application_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "nonpending")
    applicant = create_user(db_session, "applicant")
    application = create_application(
        db_session,
        availability,
        applicant,
        status=ParkingApplicationStatus.CANCELLED,
    )

    with pytest.raises(AdminReservationOverrideApplicationNotPendingError):
        create_service(db_session).override_assign_availability(availability.id, application.id, admin.id, "Reason")


def test_inactive_applicant_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "inactive")
    applicant = create_user(db_session, "applicant", is_active=False)
    application = create_application(db_session, availability, applicant)

    with pytest.raises(AdminReservationOverrideApplicantInactiveError):
        create_service(db_session).override_assign_availability(availability.id, application.id, admin.id, "Reason")


def test_existing_reservation_prevents_override(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    spot, availability = create_context(db_session, "existing")
    applicant = create_user(db_session, "applicant")
    application = create_application(db_session, availability, applicant)
    ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=application.id,
        parking_spot_id=spot.id,
        reserved_for_user_id=applicant.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
    )

    with pytest.raises(AdminReservationOverrideReservationExistsError):
        create_service(db_session).override_assign_availability(availability.id, application.id, admin.id, "Reason")

    assert ParkingApplicationRepository(db_session).get_by_id(application.id).status is ParkingApplicationStatus.PENDING
    assert ParkingAssignmentAuditLogRepository(db_session).get_by_availability_id(availability.id) is None


def test_audit_creation_failure_rolls_back_entire_override(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "auditfailure")
    selected_applicant = create_user(db_session, "selected")
    rejected_applicant = create_user(db_session, "rejected")
    selected_application = create_application(db_session, availability, selected_applicant)
    rejected_application = create_application(db_session, availability, rejected_applicant)
    audit_repository = ParkingAssignmentAuditLogRepository(db_session)
    service = create_service(db_session, audit_repository=audit_repository)
    availability_id = availability.id
    selected_application_id = selected_application.id
    rejected_application_id = rejected_application.id
    admin_id = admin.id
    db_session.commit()

    def fail_audit_create(**_: object) -> None:
        raise RuntimeError("simulated audit failure")

    monkeypatch.setattr(audit_repository, "create", fail_audit_create)

    with pytest.raises(AdminReservationOverrideAuditPersistenceError):
        service.override_assign_availability(availability_id, selected_application_id, admin_id, "Reason")

    assert ParkingReservationRepository(db_session).get_by_availability_id(availability_id) is None
    assert audit_repository.get_by_availability_id(availability_id) is None
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability_id).status is ParkingAvailabilityStatus.OPEN
    assert ParkingApplicationRepository(db_session).get_by_id(selected_application_id).status is (
        ParkingApplicationStatus.PENDING
    )
    assert ParkingApplicationRepository(db_session).get_by_id(rejected_application_id).status is (
        ParkingApplicationStatus.PENDING
    )


def test_integrity_error_during_reservation_creation_rolls_back_cleanly(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "integrity")
    applicant = create_user(db_session, "applicant")
    application = create_application(db_session, availability, applicant)
    reservation_repository = ParkingReservationRepository(db_session)
    service = create_service(db_session, reservation_repository=reservation_repository)
    availability_id = availability.id
    application_id = application.id
    admin_id = admin.id
    db_session.commit()

    def raise_integrity_error(**_: object) -> None:
        raise IntegrityError("insert parking_reservations", {}, Exception("duplicate availability"))

    monkeypatch.setattr(reservation_repository, "create", raise_integrity_error)

    with pytest.raises(AdminReservationOverrideIntegrityError):
        service.override_assign_availability(availability_id, application_id, admin_id, "Reason")

    assert reservation_repository.get_by_availability_id(availability_id) is None
    assert ParkingAssignmentAuditLogRepository(db_session).get_by_availability_id(availability_id) is None
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability_id).status is ParkingAvailabilityStatus.OPEN
    assert ParkingApplicationRepository(db_session).get_by_id(application_id).status is ParkingApplicationStatus.PENDING


def test_override_uses_lock_enabled_repository_paths(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability = create_context(db_session, "locks")
    applicant = create_user(db_session, "applicant")
    application = create_application(db_session, availability, applicant)
    availability_repository = ParkingAvailabilityRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    service = AdminReservationOverrideService(
        availability_repository=availability_repository,
        application_repository=application_repository,
        reservation_repository=ParkingReservationRepository(db_session),
        user_repository=UserRepository(db_session),
    )
    original_get_for_update = availability_repository.get_by_id_for_update
    original_list_for_update = application_repository.list_pending_by_availability_id_for_update
    availability_lock_called = False
    application_lock_called = False

    def get_for_update_spy(availability_id: int) -> ParkingAvailability | None:
        nonlocal availability_lock_called
        availability_lock_called = True
        return original_get_for_update(availability_id)

    def list_for_update_spy(availability_id: int) -> list[ParkingApplication]:
        nonlocal application_lock_called
        application_lock_called = True
        return original_list_for_update(availability_id)

    monkeypatch.setattr(availability_repository, "get_by_id_for_update", get_for_update_spy)
    monkeypatch.setattr(application_repository, "list_pending_by_availability_id_for_update", list_for_update_spy)

    service.override_assign_availability(availability.id, application.id, admin.id, "Reason")

    assert availability_lock_called is True
    assert application_lock_called is True

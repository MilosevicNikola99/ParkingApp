from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
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
from app.services.admin_reservation_override import (
    AdminReservationOverrideApplicantAlreadyReservedError,
    AdminReservationOverrideApplicantInactiveError,
    AdminReservationOverrideApplicantNotFoundError,
    AdminReservationOverrideApplicationAlreadyReservedError,
    AdminReservationOverrideApplicationAvailabilityMismatchError,
    AdminReservationOverrideApplicationNotFoundError,
    AdminReservationOverrideApplicationNotPendingError,
    AdminReservationOverrideAuditPersistenceError,
    AdminReservationOverrideAvailabilityNotAssignedError,
    AdminReservationOverrideAvailabilityNotFoundError,
    AdminReservationOverrideExistingReservationNotActiveError,
    AdminReservationOverrideExistingReservationNotFoundError,
    AdminReservationOverrideIntegrityError,
    AdminReservationOverrideReasonRequiredError,
    AdminReservationOverrideService,
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
        email=f"replacement.{suffix}@example.com",
        username=f"replacement{suffix}",
        first_name="Replacement",
        last_name="User",
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
) -> ParkingApplication:
    return ParkingApplicationRepository(db_session).create(
        availability_id=availability.id,
        applicant_id=applicant.id,
        status=status,
    )


def create_assigned_context(
    db_session: Session,
    suffix: str,
    *,
    availability_status: ParkingAvailabilityStatus = ParkingAvailabilityStatus.ASSIGNED,
    reservation_status: ParkingReservationStatus = ParkingReservationStatus.ACTIVE,
    include_reservation: bool = True,
    include_initial_audit: bool = True,
) -> tuple[ParkingSpot, ParkingAvailability, User, ParkingApplication, ParkingReservation | None, ParkingAssignmentAuditLog | None]:
    owner = create_user(db_session, f"owner{suffix}", role=UserRole.PARKING_OWNER)
    selected_user = create_user(db_session, f"selected{suffix}")
    spot = ParkingSpotRepository(db_session).create(code=f"RP-{suffix}", owner_id=owner.id)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=spot.id,
        owner_id=owner.id,
        start_at=TEST_NOW + timedelta(hours=1),
        end_at=TEST_NOW + timedelta(hours=9),
        status=availability_status,
    )
    selected_application = create_application(
        db_session,
        availability,
        selected_user,
        status=ParkingApplicationStatus.SELECTED,
    )
    reservation = None
    initial_audit = None
    if include_reservation:
        reservation = ParkingReservationRepository(db_session).create(
            availability_id=availability.id,
            application_id=selected_application.id,
            parking_spot_id=spot.id,
            reserved_for_user_id=selected_user.id,
            start_at=availability.start_at,
            end_at=availability.end_at,
            status=reservation_status,
        )
        if include_initial_audit:
            initial_audit = ParkingAssignmentAuditLogRepository(db_session).create(
                availability_id=availability.id,
                reservation_id=reservation.id,
                selected_application_id=selected_application.id,
                selected_user_id=selected_user.id,
                rejected_application_ids=[],
                ranking_policy="same_team_soft_limit_recent_wins_v1",
                ranking_details=[{"action": "initial_assignment"}],
                trigger_source=ParkingAssignmentTriggerSource.SCHEDULED,
            )

    return spot, availability, selected_user, selected_application, reservation, initial_audit


def test_admin_can_replace_active_reservation_in_place_and_preserve_audit_history(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, previous_user, previous_application, reservation, initial_audit = create_assigned_context(
        db_session,
        "success",
    )
    replacement_user = create_user(db_session, "replacement")
    other_user = create_user(db_session, "other")
    replacement_application = create_application(
        db_session,
        availability,
        replacement_user,
        status=ParkingApplicationStatus.PENDING,
    )
    other_application = create_application(
        db_session,
        availability,
        other_user,
        status=ParkingApplicationStatus.PENDING,
    )

    result = create_service(db_session).replace_existing_reservation(
        availability.id,
        replacement_application.id,
        admin.id,
        "  Shift coverage change  ",
    )

    assert reservation is not None
    assert initial_audit is not None
    assert result.reservation.id == reservation.id
    assert result.reservation.application_id == replacement_application.id
    assert result.reservation.reserved_for_user_id == replacement_user.id
    assert result.reservation.status is ParkingReservationStatus.ACTIVE
    assert result.previous_application.id == previous_application.id
    assert result.previous_application.status is ParkingApplicationStatus.REJECTED
    assert result.selected_application.id == replacement_application.id
    assert result.selected_application.status is ParkingApplicationStatus.SELECTED
    assert {application.id for application in result.rejected_applications} == {
        previous_application.id,
        other_application.id,
    }
    assert result.availability.status is ParkingAvailabilityStatus.ASSIGNED
    assert result.audit_log.reservation_id == reservation.id
    assert result.audit_log.trigger_source is ParkingAssignmentTriggerSource.ADMIN_OVERRIDE
    assert result.audit_log.ranking_policy == AdminReservationOverrideService.REPLACEMENT_POLICY
    assert set(result.audit_log.rejected_application_ids) == {previous_application.id, other_application.id}
    assert result.audit_log.ranking_details == [
        {
            "action": "replacement",
            "assignment_method": "admin_override",
            "selection_basis": "manual_admin_replacement",
            "admin_user_id": admin.id,
            "override_reason": "Shift coverage change",
            "previous_reservation_id": reservation.id,
            "previous_application_id": previous_application.id,
            "previous_user_id": previous_user.id,
            "new_reservation_id": reservation.id,
            "selected_application_id": replacement_application.id,
            "selected_user_id": replacement_user.id,
            "considered_pending_application_ids": [replacement_application.id, other_application.id],
        },
    ]
    audit_history = ParkingAssignmentAuditLogRepository(db_session).list(reservation_id=reservation.id)
    assert [audit.id for audit in audit_history] == [result.audit_log.id, initial_audit.id]


def test_admin_can_replace_reservation_by_applicant_id_without_existing_application(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, previous_user, previous_application, reservation, _ = create_assigned_context(
        db_session,
        "applicant",
    )
    replacement_user = create_user(db_session, "replacement")

    result = create_service(db_session).replace_existing_reservation(
        availability.id,
        None,
        admin.id,
        "  Applicant override  ",
        applicant_id=replacement_user.id,
    )

    assert reservation is not None
    assert result.reservation.id == reservation.id
    assert result.reservation.reserved_for_user_id == replacement_user.id
    assert result.previous_application.id == previous_application.id
    assert result.previous_application.status is ParkingApplicationStatus.REJECTED
    assert result.selected_application.applicant_id == replacement_user.id
    assert result.selected_application.status is ParkingApplicationStatus.SELECTED
    assert result.selected_application.note == "Admin replacement override candidate"
    assert result.audit_log.ranking_details[0]["action"] == "replacement"
    assert result.audit_log.ranking_details[0]["override_reason"] == "Applicant override"
    assert result.audit_log.ranking_details[0]["previous_user_id"] == previous_user.id
    assert result.audit_log.ranking_details[0]["selected_user_id"] == replacement_user.id
    assert result.audit_log.ranking_details[0]["requested_applicant_id"] == replacement_user.id
    assert result.audit_log.ranking_details[0]["replacement_candidate_action"] == "created_application"
    assert (
        result.audit_log.ranking_details[0]["replacement_selection_basis"]
        == "manual_admin_replacement_by_applicant"
    )


def test_admin_can_replace_reservation_by_reactivating_rejected_application(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _, _ = create_assigned_context(db_session, "reactivate")
    replacement_user = create_user(db_session, "replacement")
    rejected_application = create_application(
        db_session,
        availability,
        replacement_user,
        status=ParkingApplicationStatus.REJECTED,
    )

    result = create_service(db_session).replace_existing_reservation(
        availability.id,
        None,
        admin.id,
        "Applicant override",
        applicant_id=replacement_user.id,
    )

    assert result.selected_application.id == rejected_application.id
    assert result.selected_application.status is ParkingApplicationStatus.SELECTED
    assert result.reservation.application_id == rejected_application.id
    assert result.audit_log.ranking_details[0]["replacement_candidate_action"] == "reactivated_existing_application"
    assert result.audit_log.ranking_details[0]["created_or_reactivated_application_id"] == rejected_application.id


def test_applicant_id_replacement_rejects_current_reserved_user(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, previous_user, _, _, _ = create_assigned_context(db_session, "current")

    with pytest.raises(AdminReservationOverrideApplicantAlreadyReservedError):
        create_service(db_session).replace_existing_reservation(
            availability.id,
            None,
            admin.id,
            "Applicant override",
            applicant_id=previous_user.id,
        )


def test_applicant_id_replacement_rejects_missing_applicant(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _, _ = create_assigned_context(db_session, "missingapplicant")

    with pytest.raises(AdminReservationOverrideApplicantNotFoundError):
        create_service(db_session).replace_existing_reservation(
            availability.id,
            None,
            admin.id,
            "Applicant override",
            applicant_id=999,
        )


def test_applicant_id_replacement_rejects_inactive_applicant(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _, _ = create_assigned_context(db_session, "inactivebyid")
    inactive_user = create_user(db_session, "inactivebyid", is_active=False)

    with pytest.raises(AdminReservationOverrideApplicantInactiveError):
        create_service(db_session).replace_existing_reservation(
            availability.id,
            None,
            admin.id,
            "Applicant override",
            applicant_id=inactive_user.id,
        )


@pytest.mark.parametrize("reason", ["", "  ", "\t\n"])
def test_blank_replacement_reason_is_rejected(db_session: Session, reason: str) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    with pytest.raises(AdminReservationOverrideReasonRequiredError):
        create_service(db_session).replace_existing_reservation(1, 1, admin.id, reason)


def test_missing_availability_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)

    with pytest.raises(AdminReservationOverrideAvailabilityNotFoundError):
        create_service(db_session).replace_existing_reservation(999, 1, admin.id, "Reason")


def test_availability_not_assigned_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _, _ = create_assigned_context(
        db_session,
        "open",
        availability_status=ParkingAvailabilityStatus.OPEN,
        include_reservation=False,
    )

    with pytest.raises(AdminReservationOverrideAvailabilityNotAssignedError):
        create_service(db_session).replace_existing_reservation(availability.id, 1, admin.id, "Reason")


def test_missing_existing_reservation_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _, _ = create_assigned_context(db_session, "missingreservation", include_reservation=False)

    with pytest.raises(AdminReservationOverrideExistingReservationNotFoundError):
        create_service(db_session).replace_existing_reservation(availability.id, 1, admin.id, "Reason")


def test_non_active_existing_reservation_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _, _ = create_assigned_context(
        db_session,
        "inactive",
        reservation_status=ParkingReservationStatus.CANCELLED,
    )

    with pytest.raises(AdminReservationOverrideExistingReservationNotActiveError):
        create_service(db_session).replace_existing_reservation(availability.id, 1, admin.id, "Reason")


def test_missing_replacement_application_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _, _ = create_assigned_context(db_session, "missingapplication")

    with pytest.raises(AdminReservationOverrideApplicationNotFoundError):
        create_service(db_session).replace_existing_reservation(availability.id, 999, admin.id, "Reason")


def test_replacement_application_from_another_availability_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _, _ = create_assigned_context(db_session, "target")
    _, other_availability, _, _, _, _ = create_assigned_context(db_session, "other")
    applicant = create_user(db_session, "applicant")
    other_application = create_application(
        db_session,
        other_availability,
        applicant,
        status=ParkingApplicationStatus.PENDING,
    )

    with pytest.raises(AdminReservationOverrideApplicationAvailabilityMismatchError):
        create_service(db_session).replace_existing_reservation(
            availability.id,
            other_application.id,
            admin.id,
            "Reason",
        )


def test_non_pending_replacement_application_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _, _ = create_assigned_context(db_session, "nonpending")
    applicant = create_user(db_session, "applicant")
    application = create_application(
        db_session,
        availability,
        applicant,
        status=ParkingApplicationStatus.CANCELLED,
    )

    with pytest.raises(AdminReservationOverrideApplicationNotPendingError):
        create_service(db_session).replace_existing_reservation(availability.id, application.id, admin.id, "Reason")


def test_inactive_replacement_applicant_is_rejected(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _, _ = create_assigned_context(db_session, "inactiveapplicant")
    applicant = create_user(db_session, "applicant", is_active=False)
    application = create_application(
        db_session,
        availability,
        applicant,
        status=ParkingApplicationStatus.PENDING,
    )

    with pytest.raises(AdminReservationOverrideApplicantInactiveError):
        create_service(db_session).replace_existing_reservation(availability.id, application.id, admin.id, "Reason")


def test_currently_selected_application_cannot_replace_itself(db_session: Session) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, selected_application, _, _ = create_assigned_context(db_session, "same")

    with pytest.raises(AdminReservationOverrideApplicationAlreadyReservedError):
        create_service(db_session).replace_existing_reservation(
            availability.id,
            selected_application.id,
            admin.id,
            "Reason",
        )


def test_audit_creation_failure_rolls_back_complete_replacement(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, previous_user, previous_application, reservation, initial_audit = create_assigned_context(
        db_session,
        "auditfailure",
    )
    replacement_user = create_user(db_session, "replacement")
    replacement_application = create_application(
        db_session,
        availability,
        replacement_user,
        status=ParkingApplicationStatus.PENDING,
    )
    audit_repository = ParkingAssignmentAuditLogRepository(db_session)
    service = create_service(db_session, audit_repository=audit_repository)
    availability_id = availability.id
    reservation_id = reservation.id
    previous_application_id = previous_application.id
    replacement_application_id = replacement_application.id
    previous_user_id = previous_user.id
    admin_id = admin.id
    initial_audit_id = initial_audit.id
    db_session.commit()

    def fail_audit_create(**_: object) -> None:
        raise RuntimeError("simulated replacement audit failure")

    monkeypatch.setattr(audit_repository, "create", fail_audit_create)

    with pytest.raises(AdminReservationOverrideAuditPersistenceError):
        service.replace_existing_reservation(
            availability_id,
            replacement_application_id,
            admin_id,
            "Reason",
        )

    restored_reservation = ParkingReservationRepository(db_session).get_by_id(reservation_id)
    assert restored_reservation.application_id == previous_application_id
    assert restored_reservation.reserved_for_user_id == previous_user_id
    assert restored_reservation.status is ParkingReservationStatus.ACTIVE
    assert ParkingApplicationRepository(db_session).get_by_id(previous_application_id).status is (
        ParkingApplicationStatus.SELECTED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(replacement_application_id).status is (
        ParkingApplicationStatus.PENDING
    )
    assert [audit.id for audit in audit_repository.list(reservation_id=reservation_id)] == [initial_audit_id]


def test_integrity_error_during_reservation_update_rolls_back_cleanly(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, previous_user, previous_application, reservation, initial_audit = create_assigned_context(
        db_session,
        "integrity",
    )
    replacement_user = create_user(db_session, "replacement")
    replacement_application = create_application(
        db_session,
        availability,
        replacement_user,
        status=ParkingApplicationStatus.PENDING,
    )
    reservation_repository = ParkingReservationRepository(db_session)
    service = create_service(db_session, reservation_repository=reservation_repository)
    availability_id = availability.id
    reservation_id = reservation.id
    previous_application_id = previous_application.id
    replacement_application_id = replacement_application.id
    previous_user_id = previous_user.id
    admin_id = admin.id
    initial_audit_id = initial_audit.id
    db_session.commit()

    def raise_integrity_error(*_: object, **__: object) -> None:
        raise IntegrityError("update parking_reservations", {}, Exception("replacement conflict"))

    monkeypatch.setattr(reservation_repository, "update", raise_integrity_error)

    with pytest.raises(AdminReservationOverrideIntegrityError):
        service.replace_existing_reservation(
            availability_id,
            replacement_application_id,
            admin_id,
            "Reason",
        )

    restored_reservation = reservation_repository.get_by_id(reservation_id)
    assert restored_reservation.application_id == previous_application_id
    assert restored_reservation.reserved_for_user_id == previous_user_id
    assert ParkingApplicationRepository(db_session).get_by_id(previous_application_id).status is (
        ParkingApplicationStatus.SELECTED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(replacement_application_id).status is (
        ParkingApplicationStatus.PENDING
    )
    assert [audit.id for audit in ParkingAssignmentAuditLogRepository(db_session).list(reservation_id=reservation_id)] == [
        initial_audit_id
    ]


def test_replacement_uses_lock_enabled_availability_reservation_and_application_paths(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    _, availability, _, _, _, _ = create_assigned_context(db_session, "locks")
    replacement_user = create_user(db_session, "replacement")
    replacement_application = create_application(
        db_session,
        availability,
        replacement_user,
        status=ParkingApplicationStatus.PENDING,
    )
    availability_repository = ParkingAvailabilityRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    reservation_repository = ParkingReservationRepository(db_session)
    service = AdminReservationOverrideService(
        availability_repository=availability_repository,
        application_repository=application_repository,
        reservation_repository=reservation_repository,
        user_repository=UserRepository(db_session),
    )
    availability_lock_called = False
    reservation_lock_called = False
    application_lock_called = False
    original_availability_lock = availability_repository.get_by_id_for_update
    original_reservation_lock = reservation_repository.get_active_by_availability_id_for_update
    original_application_lock = application_repository.list_pending_by_availability_id_for_update

    def availability_lock_spy(availability_id: int) -> ParkingAvailability | None:
        nonlocal availability_lock_called
        availability_lock_called = True
        return original_availability_lock(availability_id)

    def reservation_lock_spy(availability_id: int) -> ParkingReservation | None:
        nonlocal reservation_lock_called
        reservation_lock_called = True
        return original_reservation_lock(availability_id)

    def application_lock_spy(availability_id: int) -> list[ParkingApplication]:
        nonlocal application_lock_called
        application_lock_called = True
        return original_application_lock(availability_id)

    monkeypatch.setattr(availability_repository, "get_by_id_for_update", availability_lock_spy)
    monkeypatch.setattr(reservation_repository, "get_active_by_availability_id_for_update", reservation_lock_spy)
    monkeypatch.setattr(application_repository, "list_pending_by_availability_id_for_update", application_lock_spy)

    service.replace_existing_reservation(availability.id, replacement_application.id, admin.id, "Reason")

    assert availability_lock_called is True
    assert reservation_lock_called is True
    assert application_lock_called is True


def test_reservation_replacement_repository_update_and_lock_compile_for_postgresql(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, availability, _, _, reservation, _ = create_assigned_context(db_session, "repository")
    replacement_user = create_user(db_session, "replacement")
    replacement_application = create_application(
        db_session,
        availability,
        replacement_user,
        status=ParkingApplicationStatus.PENDING,
    )
    repository = ParkingReservationRepository(db_session)
    captured_statements: list[object] = []
    original_execute = db_session.execute

    def execute_spy(statement: object, *args: object, **kwargs: object) -> object:
        captured_statements.append(statement)
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", execute_spy)

    locked_reservation = repository.get_active_by_availability_id_for_update(availability.id)
    lock_statement = captured_statements[0]
    lock_sql = str(
        lock_statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        ),
    )
    updated = repository.update(
        locked_reservation,
        {
            "application_id": replacement_application.id,
            "reserved_for_user_id": replacement_user.id,
            "status": ParkingReservationStatus.ACTIVE,
            "availability_id": 999,
        },
    )

    assert "FOR UPDATE OF parking_reservations" in lock_sql
    assert updated.id == reservation.id
    assert updated.availability_id == availability.id
    assert updated.application_id == replacement_application.id
    assert updated.reserved_for_user_id == replacement_user.id
    assert updated.status is ParkingReservationStatus.ACTIVE

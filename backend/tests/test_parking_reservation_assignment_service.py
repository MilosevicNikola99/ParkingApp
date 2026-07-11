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
from app.repositories.teams import TeamRepository
from app.repositories.users import UserRepository
from app.services.parking_application_ranking import ParkingApplicationRankingService
from app.services.parking_reservation_assignment import (
    ParkingReservationAssignmentAvailabilityNotFoundError,
    ParkingReservationAssignmentAvailabilityNotOpenError,
    ParkingReservationAssignmentAuditPersistenceError,
    ParkingReservationAssignmentIntegrityError,
    ParkingReservationAssignmentMethod,
    ParkingReservationAssignmentNoPendingApplicationsError,
    ParkingReservationAssignmentReservationExistsError,
    ParkingReservationAssignmentService,
)

TEST_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def service(db_session: Session) -> ParkingReservationAssignmentService:
    return create_service(db_session)


def create_service(db_session: Session) -> ParkingReservationAssignmentService:
    reservation_repository = ParkingReservationRepository(db_session)
    return ParkingReservationAssignmentService(
        availability_repository=ParkingAvailabilityRepository(db_session),
        application_repository=ParkingApplicationRepository(db_session),
        reservation_repository=reservation_repository,
        ranking_service=ParkingApplicationRankingService(
            now_provider=lambda: TEST_NOW,
            recent_win_count_provider=reservation_repository.count_recent_wins_by_user_ids,
        ),
    )


def create_user(
    db_session: Session,
    *,
    email: str,
    username: str,
    role: UserRole = UserRole.EMPLOYEE,
    team_id: int | None = None,
) -> User:
    return UserRepository(db_session).create(
        email=email,
        username=username,
        first_name="Test",
        last_name="User",
        hashed_password="hashed-password",
        role=role,
        team_id=team_id,
    )


def create_owner(db_session: Session, *, team_id: int | None = None) -> User:
    return create_user(
        db_session,
        email="assignment.owner@example.com",
        username="assignmentowner",
        role=UserRole.PARKING_OWNER,
        team_id=team_id,
    )


def create_applicant(db_session: Session, suffix: str, *, team_id: int | None = None) -> User:
    return create_user(
        db_session,
        email=f"assignment.applicant.{suffix}@example.com",
        username=f"assignmentapplicant{suffix}",
        team_id=team_id,
    )


def create_parking_spot(db_session: Session, owner_id: int) -> ParkingSpot:
    return ParkingSpotRepository(db_session).create(
        code="AS-01",
        location="Garage P1",
        owner_id=owner_id,
    )


def create_availability(
    db_session: Session,
    *,
    owner_id: int,
    parking_spot_id: int,
    status: ParkingAvailabilityStatus = ParkingAvailabilityStatus.OPEN,
    priority_until: datetime | None = None,
) -> ParkingAvailability:
    return ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
        start_at=TEST_NOW + timedelta(hours=1),
        end_at=TEST_NOW + timedelta(hours=5),
        status=status,
        priority_until=priority_until,
    )


def create_context(
    db_session: Session,
    *,
    availability_status: ParkingAvailabilityStatus = ParkingAvailabilityStatus.OPEN,
) -> tuple[User, ParkingSpot, ParkingAvailability]:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner.id)
    availability = create_availability(
        db_session,
        owner_id=owner.id,
        parking_spot_id=parking_spot.id,
        status=availability_status,
    )
    return owner, parking_spot, availability


def create_application(
    db_session: Session,
    *,
    availability_id: int,
    applicant: User,
    status: ParkingApplicationStatus = ParkingApplicationStatus.PENDING,
    created_at: datetime | None = None,
) -> ParkingApplication:
    application = ParkingApplicationRepository(db_session).create(
        availability_id=availability_id,
        applicant_id=applicant.id,
        status=status,
        note="Assignment request",
    )
    if created_at is not None:
        application.created_at = created_at
        application.updated_at = created_at
        db_session.flush()
        db_session.refresh(application)

    return application


def test_assigns_open_availability_with_one_pending_application(
    service: ParkingReservationAssignmentService,
    db_session: Session,
) -> None:
    _, _, availability = create_context(db_session)
    applicant = create_applicant(db_session, "one")
    application = create_application(db_session, availability_id=availability.id, applicant=applicant)

    result = service.assign_availability(availability.id)

    assert result.reservation.availability_id == availability.id
    assert result.reservation.application_id == application.id
    assert result.reservation.parking_spot_id == availability.parking_spot_id
    assert result.reservation.reserved_for_user_id == applicant.id
    assert result.reservation.start_at == availability.start_at
    assert result.reservation.end_at == availability.end_at
    assert result.reservation.status is ParkingReservationStatus.ACTIVE
    assert result.selected_application.id == application.id
    assert result.selected_application.status is ParkingApplicationStatus.SELECTED
    assert result.rejected_applications == []
    assert result.availability.status is ParkingAvailabilityStatus.ASSIGNED
    assert result.audit_log.availability_id == availability.id
    assert result.audit_log.reservation_id == result.reservation.id
    assert result.audit_log.selected_application_id == application.id
    assert result.audit_log.selected_user_id == applicant.id
    assert result.audit_log.rejected_application_ids == []
    assert result.audit_log.ranking_policy == ParkingReservationAssignmentService.RANKING_POLICY
    assert len(result.audit_log.ranking_details) == 1
    assert result.audit_log.ranking_details[0]["application_id"] == application.id
    assert result.audit_log.ranking_details[0]["selected"] is True
    assert result.audit_log.trigger_source is ParkingAssignmentTriggerSource.SYSTEM


def test_multiple_pending_applications_selects_oldest_and_rejects_the_rest(
    service: ParkingReservationAssignmentService,
    db_session: Session,
) -> None:
    _, _, availability = create_context(db_session)
    later_applicant = create_applicant(db_session, "later")
    older_applicant = create_applicant(db_session, "older")
    third_applicant = create_applicant(db_session, "third")
    later_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=later_applicant,
        created_at=TEST_NOW + timedelta(minutes=10),
    )
    older_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=older_applicant,
        created_at=TEST_NOW,
    )
    third_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=third_applicant,
        created_at=TEST_NOW + timedelta(minutes=20),
    )

    result = service.assign_availability(availability.id)

    assert result.selected_application.id == older_application.id
    assert result.reservation.application_id == older_application.id
    assert result.reservation.reserved_for_user_id == older_applicant.id
    assert {application.id for application in result.rejected_applications} == {
        later_application.id,
        third_application.id,
    }
    assert ParkingApplicationRepository(db_session).get_by_id(later_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(third_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )
    assert result.audit_details.assignment_method is ParkingReservationAssignmentMethod.AUTOMATIC
    assert result.audit_details.selected_application_id == older_application.id
    assert set(result.audit_details.rejected_application_ids) == {
        later_application.id,
        third_application.id,
    }
    assert [detail.application_id for detail in result.audit_details.candidate_rankings] == [
        older_application.id,
        later_application.id,
        third_application.id,
    ]
    assert [detail.final_rank_position for detail in result.audit_details.candidate_rankings] == [1, 2, 3]
    assert [detail.selected for detail in result.audit_details.candidate_rankings] == [True, False, False]
    assert result.audit_log.rejected_application_ids == [
        application.id for application in result.rejected_applications
    ]
    assert [detail["application_id"] for detail in result.audit_log.ranking_details] == [
        older_application.id,
        later_application.id,
        third_application.id,
    ]


def test_pending_applications_with_same_created_at_use_id_tie_breaker(
    service: ParkingReservationAssignmentService,
    db_session: Session,
) -> None:
    _, _, availability = create_context(db_session)
    first_applicant = create_applicant(db_session, "samefirst")
    second_applicant = create_applicant(db_session, "samesecond")
    first_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=first_applicant,
        created_at=TEST_NOW,
    )
    second_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=second_applicant,
        created_at=TEST_NOW,
    )

    result = service.assign_availability(availability.id)

    assert first_application.id < second_application.id
    assert result.selected_application.id == first_application.id
    assert {application.id for application in result.rejected_applications} == {second_application.id}


def test_non_pending_applications_are_ignored(
    service: ParkingReservationAssignmentService,
    db_session: Session,
) -> None:
    _, _, availability = create_context(db_session)
    pending_applicant = create_applicant(db_session, "pending")
    cancelled_applicant = create_applicant(db_session, "cancelled")
    rejected_applicant = create_applicant(db_session, "rejected")
    selected_applicant = create_applicant(db_session, "selected")
    pending_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=pending_applicant,
        created_at=TEST_NOW + timedelta(hours=3),
    )
    cancelled_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=cancelled_applicant,
        status=ParkingApplicationStatus.CANCELLED,
        created_at=TEST_NOW,
    )
    rejected_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=rejected_applicant,
        status=ParkingApplicationStatus.REJECTED,
        created_at=TEST_NOW + timedelta(minutes=1),
    )
    selected_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=selected_applicant,
        status=ParkingApplicationStatus.SELECTED,
        created_at=TEST_NOW + timedelta(minutes=2),
    )

    result = service.assign_availability(availability.id)

    assert result.selected_application.id == pending_application.id
    assert result.rejected_applications == []
    assert ParkingApplicationRepository(db_session).get_by_id(cancelled_application.id).status is (
        ParkingApplicationStatus.CANCELLED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(rejected_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(selected_application.id).status is (
        ParkingApplicationStatus.SELECTED
    )


def test_assignment_uses_same_team_priority_before_priority_until(db_session: Session) -> None:
    owner_team = TeamRepository(db_session).create(name="Assignment Engineering")
    other_team = TeamRepository(db_session).create(name="Assignment Finance")
    owner = create_owner(db_session, team_id=owner_team.id)
    parking_spot = create_parking_spot(db_session, owner.id)
    availability = create_availability(
        db_session,
        owner_id=owner.id,
        parking_spot_id=parking_spot.id,
        priority_until=TEST_NOW + timedelta(hours=1),
    )
    earlier_non_team_applicant = create_applicant(db_session, "earliernonteam", team_id=other_team.id)
    later_same_team_applicant = create_applicant(db_session, "latersameteam", team_id=owner_team.id)
    earlier_non_team_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=earlier_non_team_applicant,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    later_same_team_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=later_same_team_applicant,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    result = create_service(db_session).assign_availability(availability.id)

    assert result.selected_application.id == later_same_team_application.id
    assert result.reservation.reserved_for_user_id == later_same_team_applicant.id
    assert {application.id for application in result.rejected_applications} == {earlier_non_team_application.id}
    assert ParkingApplicationRepository(db_session).get_by_id(earlier_non_team_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )


def test_assignment_uses_first_applied_rule_after_priority_until(db_session: Session) -> None:
    owner_team = TeamRepository(db_session).create(name="Assignment Product")
    other_team = TeamRepository(db_session).create(name="Assignment Support")
    owner = create_owner(db_session, team_id=owner_team.id)
    parking_spot = create_parking_spot(db_session, owner.id)
    availability = create_availability(
        db_session,
        owner_id=owner.id,
        parking_spot_id=parking_spot.id,
        priority_until=TEST_NOW - timedelta(minutes=1),
    )
    earlier_non_team_applicant = create_applicant(db_session, "afternonteam", team_id=other_team.id)
    later_same_team_applicant = create_applicant(db_session, "aftersameteam", team_id=owner_team.id)
    earlier_non_team_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=earlier_non_team_applicant,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    later_same_team_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=later_same_team_applicant,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    result = create_service(db_session).assign_availability(availability.id)

    assert result.selected_application.id == earlier_non_team_application.id
    assert result.reservation.reserved_for_user_id == earlier_non_team_applicant.id
    assert {application.id for application in result.rejected_applications} == {later_same_team_application.id}
    assert result.availability.status is ParkingAvailabilityStatus.ASSIGNED


def test_assignment_selects_candidate_below_soft_limit_and_updates_assignment_state(db_session: Session) -> None:
    owner = create_owner(db_session)
    parking_spot = create_parking_spot(db_session, owner.id)
    availability = create_availability(
        db_session,
        owner_id=owner.id,
        parking_spot_id=parking_spot.id,
        priority_until=TEST_NOW - timedelta(minutes=1),
    )
    earlier_applicant_with_win = create_applicant(db_session, "fairnessmore")
    later_applicant_without_win = create_applicant(db_session, "fairnessfewer")
    earlier_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=earlier_applicant_with_win,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    later_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=later_applicant_without_win,
        created_at=TEST_NOW - timedelta(hours=1),
    )
    for days_ago in (1, 2):
        historic_start = datetime.now(UTC) - timedelta(days=days_ago)
        historic_availability = ParkingAvailabilityRepository(db_session).create(
            parking_spot_id=parking_spot.id,
            owner_id=owner.id,
            start_at=historic_start,
            end_at=historic_start + timedelta(hours=4),
            status=ParkingAvailabilityStatus.ASSIGNED,
        )
        historic_application = create_application(
            db_session,
            availability_id=historic_availability.id,
            applicant=earlier_applicant_with_win,
            status=ParkingApplicationStatus.SELECTED,
        )
        ParkingReservationRepository(db_session).create(
            availability_id=historic_availability.id,
            application_id=historic_application.id,
            parking_spot_id=parking_spot.id,
            reserved_for_user_id=earlier_applicant_with_win.id,
            start_at=historic_start,
            end_at=historic_start + timedelta(hours=4),
            status=ParkingReservationStatus.COMPLETED,
        )

    result = ParkingReservationAssignmentService(
        availability_repository=ParkingAvailabilityRepository(db_session),
        application_repository=ParkingApplicationRepository(db_session),
        reservation_repository=ParkingReservationRepository(db_session),
    ).assign_availability(availability.id)

    assert result.selected_application.id == later_application.id
    assert result.reservation.reserved_for_user_id == later_applicant_without_win.id
    assert {application.id for application in result.rejected_applications} == {earlier_application.id}
    assert ParkingApplicationRepository(db_session).get_by_id(earlier_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(later_application.id).status is (
        ParkingApplicationStatus.SELECTED
    )
    assert result.availability.status is ParkingAvailabilityStatus.ASSIGNED


def test_missing_availability_raises_clean_error(
    service: ParkingReservationAssignmentService,
) -> None:
    with pytest.raises(ParkingReservationAssignmentAvailabilityNotFoundError):
        service.assign_availability(999)


def test_non_open_availability_cannot_be_assigned(
    service: ParkingReservationAssignmentService,
    db_session: Session,
) -> None:
    _, _, availability = create_context(db_session, availability_status=ParkingAvailabilityStatus.CANCELLED)

    with pytest.raises(ParkingReservationAssignmentAvailabilityNotOpenError):
        service.assign_availability(availability.id)


def test_availability_with_no_pending_applications_cannot_be_assigned(
    service: ParkingReservationAssignmentService,
    db_session: Session,
) -> None:
    _, _, availability = create_context(db_session)

    with pytest.raises(ParkingReservationAssignmentNoPendingApplicationsError):
        service.assign_availability(availability.id)


def test_existing_reservation_blocks_assignment(
    service: ParkingReservationAssignmentService,
    db_session: Session,
) -> None:
    _, _, availability = create_context(db_session)
    applicant = create_applicant(db_session, "existing")
    application = create_application(db_session, availability_id=availability.id, applicant=applicant)
    ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=application.id,
        parking_spot_id=availability.parking_spot_id,
        reserved_for_user_id=applicant.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
    )

    with pytest.raises(ParkingReservationAssignmentReservationExistsError):
        service.assign_availability(availability.id)

    assert ParkingApplicationRepository(db_session).get_by_id(application.id).status is ParkingApplicationStatus.PENDING


def test_cancelled_reservation_history_requires_explicit_reassignment(
    service: ParkingReservationAssignmentService,
    db_session: Session,
) -> None:
    _, _, availability = create_context(db_session)
    previous_applicant = create_applicant(db_session, "cancelledhistory")
    previous_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=previous_applicant,
        status=ParkingApplicationStatus.CANCELLED,
    )
    ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=previous_application.id,
        parking_spot_id=availability.parking_spot_id,
        reserved_for_user_id=previous_applicant.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
        status=ParkingReservationStatus.CANCELLED,
    )
    pending_applicant = create_applicant(db_session, "pendingaftercancel")
    pending_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=pending_applicant,
    )

    with pytest.raises(ParkingReservationAssignmentReservationExistsError):
        service.assign_availability(availability.id)

    assert ParkingApplicationRepository(db_session).get_by_id(pending_application.id).status is (
        ParkingApplicationStatus.PENDING
    )


def test_integrity_error_during_reservation_create_rolls_back(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    availability_repository = ParkingAvailabilityRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    reservation_repository = ParkingReservationRepository(db_session)
    service = ParkingReservationAssignmentService(
        availability_repository=availability_repository,
        application_repository=application_repository,
        reservation_repository=reservation_repository,
    )
    _, _, availability = create_context(db_session)
    applicant = create_applicant(db_session, "integrity")
    application = create_application(db_session, availability_id=availability.id, applicant=applicant)
    availability_id = availability.id
    application_id = application.id
    db_session.commit()
    original_rollback = db_session.rollback
    rollback_called = False

    def raise_integrity_error(**_: object) -> None:
        raise IntegrityError("insert parking_reservations", {}, Exception("duplicate availability"))

    def rollback_spy() -> None:
        nonlocal rollback_called
        rollback_called = True
        original_rollback()

    monkeypatch.setattr(reservation_repository, "create", raise_integrity_error)
    monkeypatch.setattr(db_session, "rollback", rollback_spy)

    with pytest.raises(ParkingReservationAssignmentIntegrityError):
        service.assign_availability(availability_id)

    assert rollback_called is True
    assert ParkingApplicationRepository(db_session).get_by_id(application_id).status is ParkingApplicationStatus.PENDING
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability_id).status is ParkingAvailabilityStatus.OPEN


def test_audit_creation_failure_rolls_back_entire_assignment(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    availability_repository = ParkingAvailabilityRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    reservation_repository = ParkingReservationRepository(db_session)
    audit_repository = ParkingAssignmentAuditLogRepository(db_session)
    service = ParkingReservationAssignmentService(
        availability_repository=availability_repository,
        application_repository=application_repository,
        reservation_repository=reservation_repository,
        audit_log_repository=audit_repository,
        ranking_service=ParkingApplicationRankingService(now_provider=lambda: TEST_NOW),
    )
    _, _, availability = create_context(db_session)
    applicant = create_applicant(db_session, "auditfailure")
    application = create_application(db_session, availability_id=availability.id, applicant=applicant)
    availability_id = availability.id
    application_id = application.id
    db_session.commit()

    def fail_audit_create(**_: object) -> None:
        raise RuntimeError("simulated audit persistence failure")

    monkeypatch.setattr(audit_repository, "create", fail_audit_create)

    with pytest.raises(ParkingReservationAssignmentAuditPersistenceError):
        service.assign_availability(availability_id)

    assert reservation_repository.get_by_availability_id(availability_id) is None
    assert audit_repository.get_by_availability_id(availability_id) is None
    assert availability_repository.get_by_id(availability_id).status is ParkingAvailabilityStatus.OPEN
    assert application_repository.get_by_id(application_id).status is ParkingApplicationStatus.PENDING


def test_assignment_uses_lock_enabled_repository_paths(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    availability_repository = ParkingAvailabilityRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    reservation_repository = ParkingReservationRepository(db_session)
    service = ParkingReservationAssignmentService(
        availability_repository=availability_repository,
        application_repository=application_repository,
        reservation_repository=reservation_repository,
        ranking_service=ParkingApplicationRankingService(now_provider=lambda: TEST_NOW),
    )
    _, _, availability = create_context(db_session)
    applicant = create_applicant(db_session, "lockedpaths")
    create_application(db_session, availability_id=availability.id, applicant=applicant)
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

    service.assign_availability(availability.id)

    assert availability_lock_called is True
    assert application_lock_called is True


def test_lock_enabled_repository_methods_work_with_sqlite_and_compile_for_postgresql(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, availability = create_context(db_session)
    applicant = create_applicant(db_session, "locksql")
    application = create_application(db_session, availability_id=availability.id, applicant=applicant)
    availability_repository = ParkingAvailabilityRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    captured_statements: list[object] = []
    original_execute = db_session.execute

    def execute_spy(statement: object, *args: object, **kwargs: object) -> object:
        captured_statements.append(statement)
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", execute_spy)

    locked_availability = availability_repository.get_by_id_for_update(availability.id)
    availability_statement = captured_statements[0]
    captured_statements.clear()
    locked_applications = application_repository.list_pending_by_availability_id_for_update(availability.id)
    application_statement = captured_statements[0]

    availability_sql = str(
        availability_statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        ),
    )
    application_sql = str(
        application_statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        ),
    )

    assert locked_availability is not None
    assert [locked_application.id for locked_application in locked_applications] == [application.id]
    assert "FOR UPDATE OF parking_availabilities" in availability_sql
    assert "FOR UPDATE OF parking_applications" in application_sql


def test_integrity_error_after_partial_assignment_mutations_rolls_back_all_changes(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    availability_repository = ParkingAvailabilityRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    reservation_repository = ParkingReservationRepository(db_session)
    service = ParkingReservationAssignmentService(
        availability_repository=availability_repository,
        application_repository=application_repository,
        reservation_repository=reservation_repository,
        ranking_service=ParkingApplicationRankingService(now_provider=lambda: TEST_NOW),
    )
    _, _, availability = create_context(db_session)
    first_applicant = create_applicant(db_session, "partialfirst")
    second_applicant = create_applicant(db_session, "partialsecond")
    first_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=first_applicant,
        created_at=TEST_NOW,
    )
    second_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant=second_applicant,
        created_at=TEST_NOW + timedelta(minutes=1),
    )
    availability_id = availability.id
    first_application_id = first_application.id
    second_application_id = second_application.id
    db_session.commit()
    original_update = application_repository.update

    def fail_when_rejecting(application: ParkingApplication, updates: dict[str, object]) -> ParkingApplication:
        if updates.get("status") is ParkingApplicationStatus.REJECTED:
            raise IntegrityError("update parking_applications", {}, Exception("simulated update conflict"))

        return original_update(application, updates)

    monkeypatch.setattr(application_repository, "update", fail_when_rejecting)

    with pytest.raises(ParkingReservationAssignmentIntegrityError):
        service.assign_availability(availability_id)

    assert reservation_repository.get_by_availability_id(availability_id) is None
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability_id).status is ParkingAvailabilityStatus.OPEN
    assert ParkingApplicationRepository(db_session).get_by_id(first_application_id).status is (
        ParkingApplicationStatus.PENDING
    )
    assert ParkingApplicationRepository(db_session).get_by_id(second_application_id).status is (
        ParkingApplicationStatus.PENDING
    )


def test_duplicate_reservation_integrity_race_maps_to_reservation_exists_error(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    availability_repository = ParkingAvailabilityRepository(db_session)
    application_repository = ParkingApplicationRepository(db_session)
    reservation_repository = ParkingReservationRepository(db_session)
    service = ParkingReservationAssignmentService(
        availability_repository=availability_repository,
        application_repository=application_repository,
        reservation_repository=reservation_repository,
        ranking_service=ParkingApplicationRankingService(now_provider=lambda: TEST_NOW),
    )
    _, _, availability = create_context(db_session)
    applicant = create_applicant(db_session, "duplicaterace")
    application = create_application(db_session, availability_id=availability.id, applicant=applicant)
    availability_id = availability.id
    application_id = application.id
    db_session.commit()
    active_reservation_lookup_count = 0

    def active_reservation_lookup(_: int) -> object:
        nonlocal active_reservation_lookup_count
        active_reservation_lookup_count += 1
        return object()

    def raise_duplicate_integrity_error(**_: object) -> None:
        raise IntegrityError(
            "insert parking_reservations",
            {},
            Exception("uq_parking_reservations_active_availability_id"),
        )

    monkeypatch.setattr(reservation_repository, "get_by_availability_id", lambda _: None)
    monkeypatch.setattr(reservation_repository, "get_active_by_availability_id", active_reservation_lookup)
    monkeypatch.setattr(reservation_repository, "create", raise_duplicate_integrity_error)

    with pytest.raises(ParkingReservationAssignmentReservationExistsError):
        service.assign_availability(availability_id)

    assert active_reservation_lookup_count == 1
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability_id).status is ParkingAvailabilityStatus.OPEN
    assert ParkingApplicationRepository(db_session).get_by_id(application_id).status is ParkingApplicationStatus.PENDING

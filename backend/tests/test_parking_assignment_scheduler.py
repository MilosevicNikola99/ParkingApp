from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.commands import assign_due_availabilities as assignment_command
from app.db.base import Base
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_assignment_audit_log import ParkingAssignmentTriggerSource
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.models.parking_spot import ParkingSpot
from app.models.team import Team
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.teams import TeamRepository
from app.repositories.users import UserRepository
from app.services.parking_application_ranking import ParkingApplicationRankingService
from app.services.parking_assignment_scheduler import (
    ParkingAssignmentSchedulerService,
    ParkingAssignmentSchedulerSummary,
)
from app.services.parking_reservation_assignment import ParkingReservationAssignmentService

TEST_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def create_team(db_session: Session, suffix: str) -> Team:
    return TeamRepository(db_session).create(name=f"Scheduler Team {suffix}")


def create_user(
    db_session: Session,
    *,
    suffix: str,
    role: UserRole = UserRole.EMPLOYEE,
    team_id: int | None = None,
) -> User:
    return UserRepository(db_session).create(
        email=f"scheduler.{suffix}@example.com",
        username=f"scheduler{suffix}",
        first_name="Scheduler",
        last_name="User",
        hashed_password="hashed-password",
        role=role,
        team_id=team_id,
    )


def create_owner(db_session: Session, suffix: str, *, team_id: int | None = None) -> User:
    return create_user(db_session, suffix=suffix, role=UserRole.PARKING_OWNER, team_id=team_id)


def create_applicant(db_session: Session, suffix: str, *, team_id: int | None = None) -> User:
    return create_user(db_session, suffix=suffix, team_id=team_id)


def create_parking_spot(db_session: Session, *, suffix: str, owner_id: int) -> ParkingSpot:
    return ParkingSpotRepository(db_session).create(code=f"SC-{suffix}", owner_id=owner_id)


def create_availability(
    db_session: Session,
    *,
    suffix: str,
    owner_id: int,
    priority_until: datetime | None,
    end_at: datetime,
    status: ParkingAvailabilityStatus = ParkingAvailabilityStatus.OPEN,
) -> ParkingAvailability:
    parking_spot = create_parking_spot(db_session, suffix=suffix, owner_id=owner_id)
    return ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=parking_spot.id,
        owner_id=owner_id,
        start_at=end_at - timedelta(hours=4),
        end_at=end_at,
        status=status,
        priority_until=priority_until,
    )


def create_application(
    db_session: Session,
    *,
    availability_id: int,
    applicant_id: int,
    created_at: datetime = TEST_NOW - timedelta(hours=2),
    status: ParkingApplicationStatus = ParkingApplicationStatus.PENDING,
) -> ParkingApplication:
    application = ParkingApplicationRepository(db_session).create(
        availability_id=availability_id,
        applicant_id=applicant_id,
        status=status,
    )
    application.created_at = created_at
    application.updated_at = created_at
    db_session.flush()
    db_session.refresh(application)
    return application


def create_existing_reservation(
    db_session: Session,
    *,
    availability: ParkingAvailability,
    application: ParkingApplication,
    status: ParkingReservationStatus = ParkingReservationStatus.ACTIVE,
) -> ParkingReservation:
    return ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=application.id,
        parking_spot_id=availability.parking_spot_id,
        reserved_for_user_id=application.applicant_id,
        start_at=availability.start_at,
        end_at=availability.end_at,
        status=status,
    )


def create_assignment_service(db_session: Session) -> ParkingReservationAssignmentService:
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


def create_scheduler(
    db_session: Session,
    assignment_service: ParkingReservationAssignmentService | None = None,
) -> ParkingAssignmentSchedulerService:
    return ParkingAssignmentSchedulerService(
        db=db_session,
        availability_repository=ParkingAvailabilityRepository(db_session),
        assignment_service=assignment_service or create_assignment_service(db_session),
        now_provider=lambda: TEST_NOW,
    )


def create_due_context(
    db_session: Session,
    *,
    suffix: str,
    priority_until: datetime | None = None,
    end_at: datetime | None = None,
    applicant: User | None = None,
    owner: User | None = None,
    application_status: ParkingApplicationStatus = ParkingApplicationStatus.PENDING,
    application_created_at: datetime = TEST_NOW - timedelta(hours=2),
) -> tuple[User, User, ParkingAvailability, ParkingApplication]:
    owner = owner or create_owner(db_session, f"owner{suffix}")
    applicant = applicant or create_applicant(db_session, f"applicant{suffix}")
    availability = create_availability(
        db_session,
        suffix=suffix,
        owner_id=owner.id,
        priority_until=priority_until if priority_until is not None else TEST_NOW - timedelta(minutes=1),
        end_at=end_at or TEST_NOW + timedelta(hours=4),
    )
    application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=applicant.id,
        created_at=application_created_at,
        status=application_status,
    )
    return owner, applicant, availability, application


def test_list_assignable_returns_only_due_open_future_availability_with_pending_application(
    db_session: Session,
) -> None:
    _, _, due_availability, _ = create_due_context(db_session, suffix="due")
    owner = create_owner(db_session, "ownerbefore")
    applicant = create_applicant(db_session, "applicantbefore")
    before_priority = create_availability(
        db_session,
        suffix="before",
        owner_id=owner.id,
        priority_until=TEST_NOW + timedelta(minutes=1),
        end_at=TEST_NOW + timedelta(hours=4),
    )
    create_application(db_session, availability_id=before_priority.id, applicant_id=applicant.id)
    owner_none = create_owner(db_session, "ownernone")
    applicant_none = create_applicant(db_session, "applicantnone")
    no_priority = create_availability(
        db_session,
        suffix="none",
        owner_id=owner_none.id,
        priority_until=None,
        end_at=TEST_NOW + timedelta(hours=4),
    )
    create_application(db_session, availability_id=no_priority.id, applicant_id=applicant_none.id)
    create_due_context(db_session, suffix="expired", end_at=TEST_NOW - timedelta(minutes=1))
    owner_no_pending = create_owner(db_session, "ownernopending")
    create_availability(
        db_session,
        suffix="nopending",
        owner_id=owner_no_pending.id,
        priority_until=TEST_NOW - timedelta(minutes=1),
        end_at=TEST_NOW + timedelta(hours=4),
    )
    _, _, reserved_availability, reserved_application = create_due_context(db_session, suffix="reserved")
    create_existing_reservation(
        db_session,
        availability=reserved_availability,
        application=reserved_application,
    )
    _, _, cancelled_history_availability, cancelled_application = create_due_context(
        db_session,
        suffix="cancelledhistory",
        application_status=ParkingApplicationStatus.CANCELLED,
    )
    create_existing_reservation(
        db_session,
        availability=cancelled_history_availability,
        application=cancelled_application,
        status=ParkingReservationStatus.CANCELLED,
    )
    pending_after_cancellation = create_applicant(db_session, "pendingaftercancellation")
    create_application(
        db_session,
        availability_id=cancelled_history_availability.id,
        applicant_id=pending_after_cancellation.id,
    )

    assignable = ParkingAvailabilityRepository(db_session).list_assignable(now=TEST_NOW)

    assert [availability.id for availability in assignable] == [due_availability.id]


def test_due_open_availability_with_pending_application_is_assigned(db_session: Session) -> None:
    _, applicant, availability, application = create_due_context(db_session, suffix="assign")

    summary = create_scheduler(db_session).assign_due_availabilities(now=TEST_NOW)

    assert summary == ParkingAssignmentSchedulerSummary(
        processed_count=1,
        assigned_count=1,
        skipped_count=0,
        failed_count=0,
        issues=(),
    )
    assert ParkingReservationRepository(db_session).get_by_availability_id(availability.id).reserved_for_user_id == (
        applicant.id
    )
    assert ParkingAvailabilityRepository(db_session).get_by_id(availability.id).status is (
        ParkingAvailabilityStatus.ASSIGNED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(application.id).status is (
        ParkingApplicationStatus.SELECTED
    )
    audit_log = ParkingAssignmentAuditLogRepository(db_session).get_by_availability_id(availability.id)
    assert audit_log is not None
    assert audit_log.trigger_source is ParkingAssignmentTriggerSource.SCHEDULED


def test_scheduler_reuses_assignment_service_ranking_at_priority_boundary(db_session: Session) -> None:
    owner_team = create_team(db_session, "ranking-owner")
    other_team = create_team(db_session, "ranking-other")
    owner = create_owner(db_session, "rankingowner", team_id=owner_team.id)
    earlier_non_team = create_applicant(db_session, "rankingnonteam", team_id=other_team.id)
    later_same_team = create_applicant(db_session, "rankingsameteam", team_id=owner_team.id)
    availability = create_availability(
        db_session,
        suffix="ranking",
        owner_id=owner.id,
        priority_until=TEST_NOW,
        end_at=TEST_NOW + timedelta(hours=4),
    )
    earlier_non_team_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=earlier_non_team.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    later_same_team_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=later_same_team.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    summary = create_scheduler(db_session).assign_due_availabilities(now=TEST_NOW)

    reservation = ParkingReservationRepository(db_session).get_by_availability_id(availability.id)
    assert summary.assigned_count == 1
    assert reservation.application_id == later_same_team_application.id
    assert ParkingApplicationRepository(db_session).get_by_id(earlier_non_team_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )


def test_scheduler_reuses_assignment_service_soft_limit_ranking(db_session: Session) -> None:
    owner = create_owner(db_session, "softlimitowner")
    at_limit_applicant = create_applicant(db_session, "softlimitat")
    below_limit_applicant = create_applicant(db_session, "softlimitbelow")
    availability = create_availability(
        db_session,
        suffix="softlimit",
        owner_id=owner.id,
        priority_until=TEST_NOW - timedelta(minutes=1),
        end_at=TEST_NOW + timedelta(hours=4),
    )
    at_limit_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=at_limit_applicant.id,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    below_limit_application = create_application(
        db_session,
        availability_id=availability.id,
        applicant_id=below_limit_applicant.id,
        created_at=TEST_NOW - timedelta(hours=1),
    )
    availability_repository = ParkingAvailabilityRepository(db_session)
    assignment_service = ParkingReservationAssignmentService(
        availability_repository=availability_repository,
        application_repository=ParkingApplicationRepository(db_session),
        reservation_repository=ParkingReservationRepository(db_session),
        ranking_service=ParkingApplicationRankingService(
            now_provider=lambda: TEST_NOW,
            recent_win_count_provider=lambda user_ids, since: {
                at_limit_applicant.id: 2,
                below_limit_applicant.id: 1,
            },
        ),
    )

    summary = ParkingAssignmentSchedulerService(
        db=db_session,
        availability_repository=availability_repository,
        assignment_service=assignment_service,
        now_provider=lambda: TEST_NOW,
    ).assign_due_availabilities(now=TEST_NOW)

    reservation = ParkingReservationRepository(db_session).get_by_availability_id(availability.id)
    assert summary.assigned_count == 1
    assert reservation.application_id == below_limit_application.id
    assert ParkingApplicationRepository(db_session).get_by_id(at_limit_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )


def test_multiple_due_availabilities_are_processed_with_limit(db_session: Session) -> None:
    _, _, first, _ = create_due_context(
        db_session,
        suffix="multiplefirst",
        priority_until=TEST_NOW - timedelta(minutes=2),
    )
    _, _, second, _ = create_due_context(
        db_session,
        suffix="multiplesecond",
        priority_until=TEST_NOW - timedelta(minutes=1),
    )

    first_summary = create_scheduler(db_session).assign_due_availabilities(now=TEST_NOW, limit=1)
    second_summary = create_scheduler(db_session).assign_due_availabilities(now=TEST_NOW, limit=100)

    assert first_summary.processed_count == 1
    assert first_summary.assigned_count == 1
    assert ParkingReservationRepository(db_session).get_by_availability_id(first.id) is not None
    assert ParkingReservationRepository(db_session).get_by_availability_id(second.id) is not None
    assert second_summary.processed_count == 1
    assert second_summary.assigned_count == 1


def test_failure_on_one_availability_does_not_stop_other_assignments(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, failing_availability, failing_application = create_due_context(
        db_session,
        suffix="failurefirst",
        priority_until=TEST_NOW - timedelta(minutes=2),
    )
    _, _, successful_availability, successful_application = create_due_context(
        db_session,
        suffix="failuresecond",
        priority_until=TEST_NOW - timedelta(minutes=1),
    )
    db_session.commit()
    assignment_service = create_assignment_service(db_session)
    original_assign = assignment_service.assign_availability

    def assign_with_failure(
        availability_id: int,
        *,
        trigger_source: ParkingAssignmentTriggerSource,
    ) -> object:
        if availability_id == failing_availability.id:
            raise RuntimeError("simulated assignment failure")

        return original_assign(availability_id, trigger_source=trigger_source)

    monkeypatch.setattr(assignment_service, "assign_availability", assign_with_failure)

    summary = create_scheduler(db_session, assignment_service).assign_due_availabilities(now=TEST_NOW)

    assert summary.processed_count == 2
    assert summary.assigned_count == 1
    assert summary.skipped_count == 0
    assert summary.failed_count == 1
    assert summary.issues[0].availability_id == failing_availability.id
    assert summary.issues[0].code == "unexpected_error"
    assert ParkingReservationRepository(db_session).get_by_availability_id(failing_availability.id) is None
    assert ParkingApplicationRepository(db_session).get_by_id(failing_application.id).status is (
        ParkingApplicationStatus.PENDING
    )
    assert ParkingReservationRepository(db_session).get_by_availability_id(successful_availability.id) is not None
    assert ParkingApplicationRepository(db_session).get_by_id(successful_application.id).status is (
        ParkingApplicationStatus.SELECTED
    )


def test_stale_due_candidate_is_skipped_and_batch_continues(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, stale_availability, _ = create_due_context(
        db_session,
        suffix="stalefirst",
        priority_until=TEST_NOW - timedelta(minutes=2),
    )
    _, _, successful_availability, _ = create_due_context(
        db_session,
        suffix="stalesecond",
        priority_until=TEST_NOW - timedelta(minutes=1),
    )
    db_session.commit()
    assignment_service = create_assignment_service(db_session)
    original_assign = assignment_service.assign_availability

    def assign_with_stale_candidate(
        availability_id: int,
        *,
        trigger_source: ParkingAssignmentTriggerSource,
    ) -> object:
        if availability_id == stale_availability.id:
            availability = ParkingAvailabilityRepository(db_session).get_by_id(availability_id)
            ParkingAvailabilityRepository(db_session).update(
                availability,
                {"status": ParkingAvailabilityStatus.CANCELLED},
            )

        return original_assign(availability_id, trigger_source=trigger_source)

    monkeypatch.setattr(assignment_service, "assign_availability", assign_with_stale_candidate)

    summary = create_scheduler(db_session, assignment_service).assign_due_availabilities(now=TEST_NOW)

    assert summary.processed_count == 2
    assert summary.assigned_count == 1
    assert summary.skipped_count == 1
    assert summary.failed_count == 0
    assert summary.issues[0].availability_id == stale_availability.id
    assert summary.issues[0].code == "availability_not_open"
    assert ParkingReservationRepository(db_session).get_by_availability_id(successful_availability.id) is not None


def test_command_main_is_import_safe_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    summary = ParkingAssignmentSchedulerSummary(
        processed_count=3,
        assigned_count=2,
        skipped_count=1,
        failed_count=0,
        issues=(),
    )
    captured_limit = 0

    def run_batch(*, limit: int) -> ParkingAssignmentSchedulerSummary:
        nonlocal captured_limit
        captured_limit = limit
        return summary

    monkeypatch.setattr(assignment_command, "run_assignment_batch", run_batch)

    exit_code = assignment_command.main(["--limit", "25"])

    assert exit_code == 0
    assert captured_limit == 25
    assert capsys.readouterr().out.strip() == "processed=3 assigned=2 skipped=1 failed=0"


def test_command_main_returns_nonzero_for_fatal_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_batch(*, limit: int) -> ParkingAssignmentSchedulerSummary:
        raise RuntimeError(f"fatal with limit {limit}")

    monkeypatch.setattr(assignment_command, "run_assignment_batch", fail_batch)

    exit_code = assignment_command.main([])

    assert exit_code == 1
    assert capsys.readouterr().err.strip() == "fatal assignment command error: RuntimeError"

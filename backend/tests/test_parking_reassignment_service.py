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
from app.repositories.teams import TeamRepository
from app.repositories.users import UserRepository
from app.services.parking_application_ranking import ParkingApplicationRankingService
from app.services.parking_reassignment import (
    ParkingReassignmentActiveReservationExistsError,
    ParkingReassignmentAuditPersistenceError,
    ParkingReassignmentAvailabilityExpiredError,
    ParkingReassignmentAvailabilityNotFoundError,
    ParkingReassignmentAvailabilityNotOpenError,
    ParkingReassignmentCancelledReservationNotFoundError,
    ParkingReassignmentNoPendingApplicationsError,
    ParkingReassignmentPermissionError,
    ParkingReassignmentService,
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
    ranking_service: ParkingApplicationRankingService | None = None,
) -> ParkingReassignmentService:
    reservation_repository = ParkingReservationRepository(db_session)
    return ParkingReassignmentService(
        availability_repository=ParkingAvailabilityRepository(db_session),
        application_repository=ParkingApplicationRepository(db_session),
        reservation_repository=reservation_repository,
        audit_log_repository=audit_repository,
        user_repository=UserRepository(db_session),
        ranking_service=ranking_service
        or ParkingApplicationRankingService(
            now_provider=lambda: TEST_NOW,
            recent_win_count_provider=reservation_repository.count_recent_wins_by_user_ids,
        ),
        now_provider=lambda: TEST_NOW,
    )


def create_user(
    db_session: Session,
    suffix: str,
    *,
    role: UserRole = UserRole.EMPLOYEE,
    team_id: int | None = None,
) -> User:
    return UserRepository(db_session).create(
        email=f"reassignment.{suffix}@example.com",
        username=f"reassignment{suffix}",
        first_name="Reassignment",
        last_name="Service",
        hashed_password="hashed-password",
        role=role,
        team_id=team_id,
    )


def create_application(
    db_session: Session,
    availability: ParkingAvailability,
    applicant: User,
    *,
    status: ParkingApplicationStatus,
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


def create_cancelled_context(
    db_session: Session,
    suffix: str,
    *,
    availability_status: ParkingAvailabilityStatus = ParkingAvailabilityStatus.OPEN,
    end_at: datetime | None = None,
    owner_team_id: int | None = None,
) -> tuple[User, ParkingAvailability, ParkingApplication, ParkingReservation]:
    owner = create_user(db_session, f"owner{suffix}", role=UserRole.PARKING_OWNER, team_id=owner_team_id)
    previous_user = create_user(db_session, f"previous{suffix}")
    spot = ParkingSpotRepository(db_session).create(code=f"REA-{suffix}", owner_id=owner.id)
    resolved_end_at = end_at or TEST_NOW + timedelta(hours=8)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=spot.id,
        owner_id=owner.id,
        start_at=resolved_end_at - timedelta(hours=4),
        end_at=resolved_end_at,
        status=availability_status,
        priority_until=TEST_NOW + timedelta(hours=1),
    )
    previous_application = create_application(
        db_session,
        availability,
        previous_user,
        status=ParkingApplicationStatus.CANCELLED,
    )
    previous_reservation = ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=previous_application.id,
        parking_spot_id=spot.id,
        reserved_for_user_id=previous_user.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
        status=ParkingReservationStatus.CANCELLED,
    )
    return owner, availability, previous_application, previous_reservation


def test_reassigns_open_availability_and_preserves_cancelled_reservation_history(db_session: Session) -> None:
    owner, availability, previous_application, previous_reservation = create_cancelled_context(db_session, "success")
    older_user = create_user(db_session, "older")
    later_user = create_user(db_session, "later")
    older_application = create_application(
        db_session,
        availability,
        older_user,
        status=ParkingApplicationStatus.PENDING,
        created_at=TEST_NOW,
    )
    later_application = create_application(
        db_session,
        availability,
        later_user,
        status=ParkingApplicationStatus.PENDING,
        created_at=TEST_NOW + timedelta(minutes=10),
    )

    result = create_service(db_session).reassign_open_availability(
        availability.id,
        trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
        actor_user_id=owner.id,
        reason="  Reassign after cancellation  ",
    )

    assert result.previous_reservation.id == previous_reservation.id
    assert result.previous_reservation.status is ParkingReservationStatus.CANCELLED
    assert result.reservation.id != previous_reservation.id
    assert result.reservation.status is ParkingReservationStatus.ACTIVE
    assert result.reservation.application_id == older_application.id
    assert result.reservation.reserved_for_user_id == older_user.id
    assert result.selected_application.status is ParkingApplicationStatus.SELECTED
    assert [application.id for application in result.rejected_applications] == [later_application.id]
    assert result.availability.status is ParkingAvailabilityStatus.ASSIGNED
    assert ParkingApplicationRepository(db_session).get_by_id(previous_application.id).status is (
        ParkingApplicationStatus.CANCELLED
    )
    history = ParkingReservationRepository(db_session).list_by_availability_id(availability.id)
    assert [reservation.id for reservation in history] == [result.reservation.id, previous_reservation.id]
    assert [reservation.status for reservation in history] == [
        ParkingReservationStatus.ACTIVE,
        ParkingReservationStatus.CANCELLED,
    ]

    assert result.audit_log.reservation_id == result.reservation.id
    assert result.audit_log.trigger_source is ParkingAssignmentTriggerSource.MANUAL_OWNER
    assert result.audit_log.ranking_policy == ParkingReassignmentService.RANKING_POLICY
    assert result.audit_log.ranking_details[0]["action"] == "reassignment"
    assert result.audit_log.ranking_details[0]["actor_user_id"] == owner.id
    assert result.audit_log.ranking_details[0]["reason"] == "Reassign after cancellation"
    assert result.audit_log.ranking_details[0]["previous_reservation_id"] == previous_reservation.id
    assert result.audit_log.ranking_details[0]["previous_application_id"] == previous_application.id
    assert result.audit_log.ranking_details[0]["selected_application_id"] == older_application.id
    assert result.audit_log.ranking_details[0]["rejected_application_ids"] == [later_application.id]
    assert [detail["application_id"] for detail in result.audit_log.ranking_details[1:]] == [
        older_application.id,
        later_application.id,
    ]
    assert [detail["selected"] for detail in result.audit_log.ranking_details[1:]] == [True, False]


def test_reassignment_reuses_same_team_priority_ranking(db_session: Session) -> None:
    owner_team = TeamRepository(db_session).create(name="Reassignment Owner Team")
    other_team = TeamRepository(db_session).create(name="Reassignment Other Team")
    owner, availability, _, _ = create_cancelled_context(
        db_session,
        "ranking",
        owner_team_id=owner_team.id,
    )
    earlier_other_user = create_user(db_session, "earlierother", team_id=other_team.id)
    later_same_team_user = create_user(db_session, "latersame", team_id=owner_team.id)
    earlier_other_application = create_application(
        db_session,
        availability,
        earlier_other_user,
        status=ParkingApplicationStatus.PENDING,
        created_at=TEST_NOW - timedelta(hours=2),
    )
    later_same_team_application = create_application(
        db_session,
        availability,
        later_same_team_user,
        status=ParkingApplicationStatus.PENDING,
        created_at=TEST_NOW - timedelta(hours=1),
    )

    result = create_service(db_session).reassign_open_availability(
        availability.id,
        trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
        actor_user_id=owner.id,
    )

    assert result.selected_application.id == later_same_team_application.id
    assert [application.id for application in result.rejected_applications] == [earlier_other_application.id]


def test_non_pending_applications_are_not_reassignment_candidates(db_session: Session) -> None:
    owner, availability, previous_application, _ = create_cancelled_context(db_session, "candidates")
    rejected_user = create_user(db_session, "rejected")
    selected_user = create_user(db_session, "selected")
    pending_user = create_user(db_session, "pending")
    rejected_application = create_application(
        db_session,
        availability,
        rejected_user,
        status=ParkingApplicationStatus.REJECTED,
    )
    selected_application = create_application(
        db_session,
        availability,
        selected_user,
        status=ParkingApplicationStatus.SELECTED,
    )
    pending_application = create_application(
        db_session,
        availability,
        pending_user,
        status=ParkingApplicationStatus.PENDING,
    )

    result = create_service(db_session).reassign_open_availability(
        availability.id,
        trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
        actor_user_id=owner.id,
    )

    assert result.selected_application.id == pending_application.id
    assert result.rejected_applications == []
    assert ParkingApplicationRepository(db_session).get_by_id(previous_application.id).status is (
        ParkingApplicationStatus.CANCELLED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(rejected_application.id).status is (
        ParkingApplicationStatus.REJECTED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(selected_application.id).status is (
        ParkingApplicationStatus.SELECTED
    )


def test_admin_can_reassign_and_owner_or_admin_permission_is_required(db_session: Session) -> None:
    owner, availability, _, _ = create_cancelled_context(db_session, "permissions")
    admin = create_user(db_session, "admin", role=UserRole.ADMIN)
    unrelated = create_user(db_session, "unrelated")
    applicant = create_user(db_session, "applicant")
    create_application(db_session, availability, applicant, status=ParkingApplicationStatus.PENDING)

    with pytest.raises(ParkingReassignmentPermissionError):
        create_service(db_session).reassign_open_availability(
            availability.id,
            trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            actor_user_id=unrelated.id,
        )

    result = create_service(db_session).reassign_open_availability(
        availability.id,
        trigger_source=ParkingAssignmentTriggerSource.MANUAL_ADMIN,
        actor_user_id=admin.id,
    )

    assert owner.id != admin.id
    assert result.audit_log.trigger_source is ParkingAssignmentTriggerSource.MANUAL_ADMIN


def test_reassignment_validation_failures(db_session: Session) -> None:
    owner = create_user(db_session, "owner", role=UserRole.PARKING_OWNER)
    service = create_service(db_session)

    with pytest.raises(ParkingReassignmentAvailabilityNotFoundError):
        service.reassign_open_availability(
            999,
            trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            actor_user_id=owner.id,
        )

    non_open_owner, non_open, _, _ = create_cancelled_context(
        db_session,
        "nonopen",
        availability_status=ParkingAvailabilityStatus.ASSIGNED,
    )
    with pytest.raises(ParkingReassignmentAvailabilityNotOpenError):
        service.reassign_open_availability(
            non_open.id,
            trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            actor_user_id=non_open_owner.id,
        )

    expired_owner, expired, _, _ = create_cancelled_context(
        db_session,
        "expired",
        end_at=TEST_NOW,
    )
    with pytest.raises(ParkingReassignmentAvailabilityExpiredError):
        service.reassign_open_availability(
            expired.id,
            trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            actor_user_id=expired_owner.id,
        )

    no_pending_owner, no_pending, _, _ = create_cancelled_context(db_session, "nopending")
    with pytest.raises(ParkingReassignmentNoPendingApplicationsError):
        service.reassign_open_availability(
            no_pending.id,
            trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            actor_user_id=no_pending_owner.id,
        )


def test_active_reservation_blocks_reassignment(db_session: Session) -> None:
    owner, availability, _, _ = create_cancelled_context(db_session, "active")
    active_user = create_user(db_session, "activeuser")
    active_application = create_application(
        db_session,
        availability,
        active_user,
        status=ParkingApplicationStatus.SELECTED,
    )
    ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=active_application.id,
        parking_spot_id=availability.parking_spot_id,
        reserved_for_user_id=active_user.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
    )
    pending_user = create_user(db_session, "pending")
    create_application(db_session, availability, pending_user, status=ParkingApplicationStatus.PENDING)

    with pytest.raises(ParkingReassignmentActiveReservationExistsError):
        create_service(db_session).reassign_open_availability(
            availability.id,
            trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            actor_user_id=owner.id,
        )


def test_reassignment_requires_cancelled_reservation_history(db_session: Session) -> None:
    owner = create_user(db_session, "owner", role=UserRole.PARKING_OWNER)
    applicant = create_user(db_session, "applicant")
    spot = ParkingSpotRepository(db_session).create(code="REA-NOHISTORY", owner_id=owner.id)
    availability = ParkingAvailabilityRepository(db_session).create(
        parking_spot_id=spot.id,
        owner_id=owner.id,
        start_at=TEST_NOW + timedelta(hours=1),
        end_at=TEST_NOW + timedelta(hours=8),
        status=ParkingAvailabilityStatus.OPEN,
    )
    create_application(db_session, availability, applicant, status=ParkingApplicationStatus.PENDING)

    with pytest.raises(ParkingReassignmentCancelledReservationNotFoundError):
        create_service(db_session).reassign_open_availability(
            availability.id,
            trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            actor_user_id=owner.id,
        )


def test_reassignment_requires_latest_reservation_history_to_be_cancelled(db_session: Session) -> None:
    owner, availability, _, _ = create_cancelled_context(db_session, "latesthistory")
    completed_user = create_user(db_session, "completed")
    completed_application = create_application(
        db_session,
        availability,
        completed_user,
        status=ParkingApplicationStatus.SELECTED,
    )
    ParkingReservationRepository(db_session).create(
        availability_id=availability.id,
        application_id=completed_application.id,
        parking_spot_id=availability.parking_spot_id,
        reserved_for_user_id=completed_user.id,
        start_at=availability.start_at,
        end_at=availability.end_at,
        status=ParkingReservationStatus.COMPLETED,
    )
    pending_user = create_user(db_session, "latestpending")
    create_application(db_session, availability, pending_user, status=ParkingApplicationStatus.PENDING)

    with pytest.raises(ParkingReassignmentCancelledReservationNotFoundError):
        create_service(db_session).reassign_open_availability(
            availability.id,
            trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            actor_user_id=owner.id,
        )


def test_audit_failure_rolls_back_reassignment_and_preserves_history(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner, availability, previous_application, previous_reservation = create_cancelled_context(db_session, "rollback")
    applicant = create_user(db_session, "applicant")
    pending_application = create_application(
        db_session,
        availability,
        applicant,
        status=ParkingApplicationStatus.PENDING,
    )
    audit_repository = ParkingAssignmentAuditLogRepository(db_session)
    service = create_service(db_session, audit_repository=audit_repository)
    owner_id = owner.id
    availability_id = availability.id
    previous_application_id = previous_application.id
    previous_reservation_id = previous_reservation.id
    pending_application_id = pending_application.id
    db_session.commit()

    def fail_audit_create(**_: object) -> None:
        raise RuntimeError("simulated reassignment audit failure")

    monkeypatch.setattr(audit_repository, "create", fail_audit_create)

    with pytest.raises(ParkingReassignmentAuditPersistenceError):
        service.reassign_open_availability(
            availability_id,
            trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            actor_user_id=owner_id,
        )

    assert ParkingAvailabilityRepository(db_session).get_by_id(availability_id).status is ParkingAvailabilityStatus.OPEN
    assert ParkingApplicationRepository(db_session).get_by_id(previous_application_id).status is (
        ParkingApplicationStatus.CANCELLED
    )
    assert ParkingApplicationRepository(db_session).get_by_id(pending_application_id).status is (
        ParkingApplicationStatus.PENDING
    )
    history = ParkingReservationRepository(db_session).list_by_availability_id(availability_id)
    assert [reservation.id for reservation in history] == [previous_reservation_id]
    assert history[0].status is ParkingReservationStatus.CANCELLED
    assert audit_repository.list(availability_id=availability_id) == []

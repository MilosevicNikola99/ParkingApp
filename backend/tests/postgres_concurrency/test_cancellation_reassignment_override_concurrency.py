from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from threading import Barrier, Event
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog, ParkingAssignmentTriggerSource
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.models.user import UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.teams import TeamRepository
from app.repositories.users import UserRepository
from app.services.admin_reservation_override import (
    AdminReservationOverrideService,
    AdminReservationOverrideServiceError,
)
from app.services.parking_application_ranking import ParkingApplicationRankingService
from app.services.parking_reassignment import ParkingReassignmentService, ParkingReassignmentServiceError
from app.services.parking_reservation_cancellation import (
    ParkingReservationCancellationService,
    ParkingReservationCancellationServiceError,
)
from tests.postgres_concurrency.test_assignment_application_concurrency import (
    TEST_NOW,
    SessionFactory,
    Worker,
    configure_worker_session,
    direct_assignment_worker,
    make_concurrency_settings,
    postgres_database_url as postgres_database_url,
    postgres_engine as postgres_engine,
    run_concurrently,
    session_factory as session_factory,
)

pytestmark = pytest.mark.postgres_concurrency


@dataclass(frozen=True)
class AssignedContext:
    availability_id: int
    reservation_id: int
    owner_id: int
    admin_ids: tuple[int, ...]
    reserved_user_id: int
    selected_application_id: int
    pending_user_ids: tuple[int, ...]
    pending_application_ids: tuple[int, ...]


@dataclass(frozen=True)
class CancelledContext:
    availability_id: int
    previous_reservation_id: int
    owner_id: int
    admin_ids: tuple[int, ...]
    previous_user_id: int
    previous_application_id: int
    pending_user_ids: tuple[int, ...]
    pending_application_ids: tuple[int, ...]


class BlockingAfterInitialReservationReadRepository(ParkingReservationRepository):
    def __init__(
        self,
        db: Session,
        reservation_id: int,
        snapshot_event: Event,
        release_event: Event,
    ) -> None:
        super().__init__(db)
        self.reservation_id = reservation_id
        self.snapshot_event = snapshot_event
        self.release_event = release_event
        self._has_waited = False

    def get_by_id(self, reservation_id: int) -> ParkingReservation | None:
        reservation = super().get_by_id(reservation_id)
        if reservation_id == self.reservation_id and not self._has_waited:
            self._has_waited = True
            self.snapshot_event.set()
            assert self.release_event.wait(timeout=10)
        return reservation


class BarrierBeforeAvailabilityLockRepository(ParkingAvailabilityRepository):
    def __init__(self, db: Session, availability_id: int, lock_barrier: Barrier) -> None:
        super().__init__(db)
        self.availability_id = availability_id
        self.lock_barrier = lock_barrier
        self._has_waited = False

    def get_by_id_for_update(self, availability_id: int) -> ParkingAvailability | None:
        if availability_id == self.availability_id and not self._has_waited:
            self._has_waited = True
            self.lock_barrier.wait(timeout=10)
        return super().get_by_id_for_update(availability_id)


def build_cancellation_service(
    db: Session,
    *,
    reservation_repository: ParkingReservationRepository | None = None,
) -> ParkingReservationCancellationService:
    reservation_repository = reservation_repository or ParkingReservationRepository(db)
    return ParkingReservationCancellationService(
        reservation_repository=reservation_repository,
        availability_repository=ParkingAvailabilityRepository(db),
        application_repository=ParkingApplicationRepository(db),
        audit_log_repository=ParkingAssignmentAuditLogRepository(db),
        user_repository=UserRepository(db),
        now_provider=lambda: TEST_NOW,
    )


def build_reassignment_service(db: Session) -> ParkingReassignmentService:
    reservation_repository = ParkingReservationRepository(db)
    return ParkingReassignmentService(
        availability_repository=ParkingAvailabilityRepository(db),
        application_repository=ParkingApplicationRepository(db),
        reservation_repository=reservation_repository,
        audit_log_repository=ParkingAssignmentAuditLogRepository(db),
        user_repository=UserRepository(db),
        ranking_service=ParkingApplicationRankingService(
            now_provider=lambda: TEST_NOW,
            recent_win_count_provider=reservation_repository.count_recent_wins_by_user_ids,
            settings=make_concurrency_settings(),
        ),
        now_provider=lambda: TEST_NOW,
    )


def build_override_service(
    db: Session,
    *,
    availability_repository: ParkingAvailabilityRepository | None = None,
) -> AdminReservationOverrideService:
    return AdminReservationOverrideService(
        availability_repository=availability_repository or ParkingAvailabilityRepository(db),
        application_repository=ParkingApplicationRepository(db),
        reservation_repository=ParkingReservationRepository(db),
        audit_log_repository=ParkingAssignmentAuditLogRepository(db),
        user_repository=UserRepository(db),
    )


def seed_assigned_context(
    session_factory: SessionFactory,
    *,
    suffix: str,
    pending_count: int = 3,
    admin_count: int = 2,
) -> AssignedContext:
    with session_factory() as db:
        team = TeamRepository(db).create(name=f"Phase2 Assigned Team {suffix}")
        owner = UserRepository(db).create(
            email=f"phase2.assigned.owner.{suffix}@example.com",
            username=f"phase2assignedowner{suffix}",
            first_name="Owner",
            last_name=suffix,
            hashed_password="hashed-password",
            role=UserRole.PARKING_OWNER,
            team_id=team.id,
        )
        admin_ids = []
        for index in range(admin_count):
            admin = UserRepository(db).create(
                email=f"phase2.assigned.admin.{suffix}.{index}@example.com",
                username=f"phase2assignedadmin{suffix}{index}",
                first_name="Admin",
                last_name=f"{suffix}{index}",
                hashed_password="hashed-password",
                role=UserRole.ADMIN,
                team_id=team.id,
            )
            admin_ids.append(admin.id)
        reserved_user = UserRepository(db).create(
            email=f"phase2.assigned.reserved.{suffix}@example.com",
            username=f"phase2assignedreserved{suffix}",
            first_name="Reserved",
            last_name=suffix,
            hashed_password="hashed-password",
            role=UserRole.EMPLOYEE,
            team_id=team.id,
        )
        spot = ParkingSpotRepository(db).create(
            code=f"P2A-{suffix}",
            location="Phase 2 Garage",
            owner_id=owner.id,
        )
        availability = ParkingAvailabilityRepository(db).create(
            parking_spot_id=spot.id,
            owner_id=owner.id,
            start_at=TEST_NOW + timedelta(hours=1),
            end_at=TEST_NOW + timedelta(hours=5),
            status=ParkingAvailabilityStatus.ASSIGNED,
            priority_until=TEST_NOW - timedelta(minutes=1),
        )
        selected_application = ParkingApplicationRepository(db).create(
            availability_id=availability.id,
            applicant_id=reserved_user.id,
            status=ParkingApplicationStatus.SELECTED,
            note="Selected application",
        )
        reservation = ParkingReservationRepository(db).create(
            availability_id=availability.id,
            application_id=selected_application.id,
            parking_spot_id=spot.id,
            reserved_for_user_id=reserved_user.id,
            start_at=availability.start_at,
            end_at=availability.end_at,
            status=ParkingReservationStatus.ACTIVE,
        )

        pending_user_ids = []
        pending_application_ids = []
        for index in range(pending_count):
            applicant = UserRepository(db).create(
                email=f"phase2.assigned.applicant.{suffix}.{index}@example.com",
                username=f"phase2assignedapplicant{suffix}{index}",
                first_name="Applicant",
                last_name=f"{suffix}{index}",
                hashed_password="hashed-password",
                role=UserRole.EMPLOYEE,
                team_id=team.id,
            )
            application = ParkingApplicationRepository(db).create(
                availability_id=availability.id,
                applicant_id=applicant.id,
                status=ParkingApplicationStatus.PENDING,
                note=f"Pending {index}",
            )
            application.created_at = TEST_NOW - timedelta(minutes=pending_count - index)
            application.updated_at = application.created_at
            db.flush()
            db.refresh(application)
            pending_user_ids.append(applicant.id)
            pending_application_ids.append(application.id)

        db.commit()
        return AssignedContext(
            availability_id=availability.id,
            reservation_id=reservation.id,
            owner_id=owner.id,
            admin_ids=tuple(admin_ids),
            reserved_user_id=reserved_user.id,
            selected_application_id=selected_application.id,
            pending_user_ids=tuple(pending_user_ids),
            pending_application_ids=tuple(pending_application_ids),
        )


def seed_cancelled_context(
    session_factory: SessionFactory,
    *,
    suffix: str,
    pending_count: int = 3,
    admin_count: int = 2,
) -> CancelledContext:
    assigned = seed_assigned_context(
        session_factory,
        suffix=f"{suffix}base",
        pending_count=pending_count,
        admin_count=admin_count,
    )
    with session_factory() as db:
        availability = ParkingAvailabilityRepository(db).get_by_id(assigned.availability_id)
        reservation = ParkingReservationRepository(db).get_by_id(assigned.reservation_id)
        selected_application = ParkingApplicationRepository(db).get_by_id(assigned.selected_application_id)
        assert availability is not None
        assert reservation is not None
        assert selected_application is not None
        availability.status = ParkingAvailabilityStatus.OPEN
        reservation.status = ParkingReservationStatus.CANCELLED
        selected_application.status = ParkingApplicationStatus.CANCELLED
        db.commit()

    return CancelledContext(
        availability_id=assigned.availability_id,
        previous_reservation_id=assigned.reservation_id,
        owner_id=assigned.owner_id,
        admin_ids=assigned.admin_ids,
        previous_user_id=assigned.reserved_user_id,
        previous_application_id=assigned.selected_application_id,
        pending_user_ids=assigned.pending_user_ids,
        pending_application_ids=assigned.pending_application_ids,
    )


def admin_cancellation_worker(
    session_factory: SessionFactory,
    *,
    reservation_id: int,
    admin_user_id: int,
    reservation_repository_factory: Any | None = None,
) -> Worker:
    def worker(start_barrier: Barrier) -> dict[str, Any]:
        with session_factory() as db:
            configure_worker_session(db)
            repository = (
                reservation_repository_factory(db)
                if reservation_repository_factory is not None
                else ParkingReservationRepository(db)
            )
            service = build_cancellation_service(db, reservation_repository=repository)
            start_barrier.wait(timeout=10)
            try:
                result = service.cancel_as_admin(reservation_id, admin_user_id, "Concurrent admin cancellation")
                db.commit()
                return {"outcome": "cancelled", "reservation_id": result.reservation.id}
            except ParkingReservationCancellationServiceError as exc:
                db.rollback()
                return {"outcome": "controlled_error", "error_type": type(exc).__name__}
            except IntegrityError as exc:
                db.rollback()
                raise AssertionError("raw cancellation IntegrityError escaped the service boundary") from exc

    return worker


def employee_cancellation_worker(
    session_factory: SessionFactory,
    *,
    reservation_id: int,
    employee_user_id: int,
) -> Worker:
    def worker(start_barrier: Barrier) -> dict[str, Any]:
        with session_factory() as db:
            configure_worker_session(db)
            service = build_cancellation_service(db)
            start_barrier.wait(timeout=10)
            try:
                result = service.cancel_my_reservation(reservation_id, employee_user_id, "Concurrent employee cancel")
                db.commit()
                return {"outcome": "cancelled", "reservation_id": result.reservation.id}
            except ParkingReservationCancellationServiceError as exc:
                db.rollback()
                return {"outcome": "controlled_error", "error_type": type(exc).__name__}
            except IntegrityError as exc:
                db.rollback()
                raise AssertionError("raw cancellation IntegrityError escaped the service boundary") from exc

    return worker


def reassignment_worker(
    session_factory: SessionFactory,
    *,
    availability_id: int,
    actor_user_id: int | None,
    trigger_source: ParkingAssignmentTriggerSource,
) -> Worker:
    def worker(start_barrier: Barrier) -> dict[str, Any]:
        with session_factory() as db:
            configure_worker_session(db)
            service = build_reassignment_service(db)
            start_barrier.wait(timeout=10)
            try:
                result = service.reassign_open_availability(
                    availability_id,
                    trigger_source=trigger_source,
                    actor_user_id=actor_user_id,
                    reason="Concurrent reassignment",
                )
                db.commit()
                return {
                    "outcome": "reassigned",
                    "reservation_id": result.reservation.id,
                    "application_id": result.selected_application.id,
                }
            except ParkingReassignmentServiceError as exc:
                db.rollback()
                return {"outcome": "controlled_error", "error_type": type(exc).__name__}
            except IntegrityError as exc:
                db.rollback()
                raise AssertionError("raw reassignment IntegrityError escaped the service boundary") from exc

    return worker


def manual_override_worker(
    session_factory: SessionFactory,
    *,
    availability_id: int,
    application_id: int,
    admin_user_id: int,
) -> Worker:
    def worker(start_barrier: Barrier) -> dict[str, Any]:
        with session_factory() as db:
            configure_worker_session(db)
            service = build_override_service(db)
            start_barrier.wait(timeout=10)
            try:
                result = service.override_assign_availability(
                    availability_id,
                    application_id,
                    admin_user_id,
                    "Concurrent manual override",
                )
                db.commit()
                return {
                    "outcome": "overrode",
                    "reservation_id": result.reservation.id,
                    "application_id": result.selected_application.id,
                }
            except AdminReservationOverrideServiceError as exc:
                db.rollback()
                return {"outcome": "controlled_error", "error_type": type(exc).__name__}
            except IntegrityError as exc:
                db.rollback()
                raise AssertionError("raw override IntegrityError escaped the service boundary") from exc

    return worker


def replacement_worker(
    session_factory: SessionFactory,
    *,
    availability_id: int,
    admin_user_id: int,
    application_id: int | None = None,
    applicant_id: int | None = None,
    availability_repository_factory: Any | None = None,
) -> Worker:
    def worker(start_barrier: Barrier) -> dict[str, Any]:
        with session_factory() as db:
            configure_worker_session(db)
            availability_repository = (
                availability_repository_factory(db)
                if availability_repository_factory is not None
                else ParkingAvailabilityRepository(db)
            )
            service = build_override_service(db, availability_repository=availability_repository)
            start_barrier.wait(timeout=10)
            try:
                result = service.replace_existing_reservation(
                    availability_id,
                    application_id,
                    admin_user_id,
                    "Concurrent replacement",
                    applicant_id=applicant_id,
                )
                db.commit()
                return {
                    "outcome": "replaced",
                    "reservation_id": result.reservation.id,
                    "application_id": result.selected_application.id,
                    "reserved_for_user_id": result.reservation.reserved_for_user_id,
                }
            except AdminReservationOverrideServiceError as exc:
                db.rollback()
                return {"outcome": "controlled_error", "error_type": type(exc).__name__}
            except IntegrityError as exc:
                db.rollback()
                raise AssertionError("raw replacement IntegrityError escaped the service boundary") from exc

    return worker


def active_reservation_count(db: Session, availability_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ParkingReservation.id))
            .where(ParkingReservation.availability_id == availability_id)
            .where(ParkingReservation.status == ParkingReservationStatus.ACTIVE),
        )
        or 0,
    )


def selected_application_count(db: Session, availability_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ParkingApplication.id))
            .where(ParkingApplication.availability_id == availability_id)
            .where(ParkingApplication.status == ParkingApplicationStatus.SELECTED),
        )
        or 0,
    )


def success_audit_count(db: Session, availability_id: int, ranking_policy: str) -> int:
    return int(
        db.scalar(
            select(func.count(ParkingAssignmentAuditLog.id))
            .where(ParkingAssignmentAuditLog.availability_id == availability_id)
            .where(ParkingAssignmentAuditLog.ranking_policy == ranking_policy),
        )
        or 0,
    )


def assert_one_active_assignment(session_factory: SessionFactory, availability_id: int) -> None:
    with session_factory() as db:
        assert active_reservation_count(db, availability_id) == 1
        assert selected_application_count(db, availability_id) == 1
        assert (
            db.scalar(select(ParkingAvailability.status).where(ParkingAvailability.id == availability_id))
            is ParkingAvailabilityStatus.ASSIGNED
        )


def assert_cancelled_without_active_reservation(session_factory: SessionFactory, availability_id: int) -> None:
    with session_factory() as db:
        assert active_reservation_count(db, availability_id) == 0
        assert selected_application_count(db, availability_id) == 0
        assert (
            db.scalar(select(ParkingAvailability.status).where(ParkingAvailability.id == availability_id))
            is ParkingAvailabilityStatus.OPEN
        )


def assert_no_pending_or_duplicate_selected(session_factory: SessionFactory, availability_id: int) -> None:
    with session_factory() as db:
        assert selected_application_count(db, availability_id) <= 1


def test_two_admin_cancellations_same_reservation_are_serialized(session_factory: SessionFactory) -> None:
    context = seed_assigned_context(session_factory, suffix="cancel-admin-admin")

    results = run_concurrently(
        {
            "admin-a": admin_cancellation_worker(
                session_factory,
                reservation_id=context.reservation_id,
                admin_user_id=context.admin_ids[0],
            ),
            "admin-b": admin_cancellation_worker(
                session_factory,
                reservation_id=context.reservation_id,
                admin_user_id=context.admin_ids[1],
            ),
        },
    )

    assert sum(result["outcome"] == "cancelled" for result in results.values()) == 1
    assert sum(result["outcome"] == "controlled_error" for result in results.values()) == 1
    assert_cancelled_without_active_reservation(session_factory, context.availability_id)
    with session_factory() as db:
        assert success_audit_count(
            db,
            context.availability_id,
            ParkingReservationCancellationService.AUDIT_POLICY,
        ) == 1


def test_employee_and_admin_cancellation_same_reservation_are_serialized(session_factory: SessionFactory) -> None:
    context = seed_assigned_context(session_factory, suffix="cancel-employee-admin")

    results = run_concurrently(
        {
            "employee": employee_cancellation_worker(
                session_factory,
                reservation_id=context.reservation_id,
                employee_user_id=context.reserved_user_id,
            ),
            "admin": admin_cancellation_worker(
                session_factory,
                reservation_id=context.reservation_id,
                admin_user_id=context.admin_ids[0],
            ),
        },
    )

    assert sum(result["outcome"] == "cancelled" for result in results.values()) == 1
    assert sum(result["outcome"] == "controlled_error" for result in results.values()) == 1
    assert_cancelled_without_active_reservation(session_factory, context.availability_id)


def test_cancellation_that_started_before_replacement_does_not_cancel_replacement(
    session_factory: SessionFactory,
) -> None:
    context = seed_assigned_context(session_factory, suffix="cancel-replace", pending_count=2)
    cancellation_snapshot_read = Event()
    replacement_finished = Event()

    def cancellation_repository_factory(db: Session) -> ParkingReservationRepository:
        return BlockingAfterInitialReservationReadRepository(
            db,
            context.reservation_id,
            cancellation_snapshot_read,
            replacement_finished,
        )

    def replacement_after_cancellation_snapshot(start_barrier: Barrier) -> dict[str, Any]:
        start_barrier.wait(timeout=10)
        assert cancellation_snapshot_read.wait(timeout=10)
        try:
            return replacement_worker(
                session_factory,
                availability_id=context.availability_id,
                application_id=context.pending_application_ids[0],
                admin_user_id=context.admin_ids[1],
            )(Barrier(1))
        finally:
            replacement_finished.set()

    results = run_concurrently(
        {
            "cancellation": admin_cancellation_worker(
                session_factory,
                reservation_id=context.reservation_id,
                admin_user_id=context.admin_ids[0],
                reservation_repository_factory=cancellation_repository_factory,
            ),
            "replacement": replacement_after_cancellation_snapshot,
        },
    )

    assert results["replacement"]["outcome"] == "replaced"
    assert results["cancellation"]["outcome"] == "controlled_error"
    assert_one_active_assignment(session_factory, context.availability_id)
    with session_factory() as db:
        reservation = ParkingReservationRepository(db).get_by_id(context.reservation_id)
        assert reservation is not None
        assert reservation.reserved_for_user_id == context.pending_user_ids[0]
        assert success_audit_count(db, context.availability_id, AdminReservationOverrideService.REPLACEMENT_POLICY) == 1


def test_cancellation_can_be_followed_by_reassignment_without_incoherent_history(
    session_factory: SessionFactory,
) -> None:
    context = seed_assigned_context(session_factory, suffix="cancel-reassign", pending_count=2)

    def cancellation_then_reassignment(start_barrier: Barrier) -> dict[str, Any]:
        start_barrier.wait(timeout=10)
        first = admin_cancellation_worker(
            session_factory,
            reservation_id=context.reservation_id,
            admin_user_id=context.admin_ids[0],
        )(Barrier(1))
        second = reassignment_worker(
            session_factory,
            availability_id=context.availability_id,
            actor_user_id=context.owner_id,
            trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
        )(Barrier(1))
        return {"outcome": "cancel_then_reassign", "first": first, "second": second}

    results = run_concurrently({"flow": cancellation_then_reassignment})

    assert results["flow"]["first"]["outcome"] == "cancelled"
    assert results["flow"]["second"]["outcome"] == "reassigned"
    assert_one_active_assignment(session_factory, context.availability_id)
    with session_factory() as db:
        history = ParkingReservationRepository(db).list_by_availability_id(context.availability_id)
        assert [reservation.status for reservation in history] == [
            ParkingReservationStatus.ACTIVE,
            ParkingReservationStatus.CANCELLED,
        ]


def test_two_reassignments_same_cancelled_availability_are_serialized(session_factory: SessionFactory) -> None:
    context = seed_cancelled_context(session_factory, suffix="reassign-reassign", pending_count=3)

    results = run_concurrently(
        {
            "reassign-a": reassignment_worker(
                session_factory,
                availability_id=context.availability_id,
                actor_user_id=context.owner_id,
                trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            ),
            "reassign-b": reassignment_worker(
                session_factory,
                availability_id=context.availability_id,
                actor_user_id=context.admin_ids[0],
                trigger_source=ParkingAssignmentTriggerSource.MANUAL_ADMIN,
            ),
        },
    )

    assert sum(result["outcome"] == "reassigned" for result in results.values()) == 1
    assert sum(result["outcome"] == "controlled_error" for result in results.values()) == 1
    assert_one_active_assignment(session_factory, context.availability_id)
    with session_factory() as db:
        assert success_audit_count(db, context.availability_id, ParkingReassignmentService.RANKING_POLICY) == 1


def test_reassignment_racing_direct_assignment_is_serialized(session_factory: SessionFactory) -> None:
    context = seed_cancelled_context(session_factory, suffix="reassign-assignment", pending_count=3)

    results = run_concurrently(
        {
            "reassign": reassignment_worker(
                session_factory,
                availability_id=context.availability_id,
                actor_user_id=context.owner_id,
                trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            ),
            "direct-assignment": direct_assignment_worker(
                session_factory,
                availability_id=context.availability_id,
                trigger_source=ParkingAssignmentTriggerSource.SYSTEM,
            ),
        },
    )

    assert sum(result["outcome"] in {"reassigned", "assigned"} for result in results.values()) == 1
    assert sum(result["outcome"] == "controlled_error" for result in results.values()) == 1
    assert_one_active_assignment(session_factory, context.availability_id)
    assert_no_pending_or_duplicate_selected(session_factory, context.availability_id)


def test_reassignment_racing_manual_override_is_serialized(session_factory: SessionFactory) -> None:
    context = seed_cancelled_context(session_factory, suffix="reassign-override", pending_count=2)

    results = run_concurrently(
        {
            "reassign": reassignment_worker(
                session_factory,
                availability_id=context.availability_id,
                actor_user_id=context.owner_id,
                trigger_source=ParkingAssignmentTriggerSource.MANUAL_OWNER,
            ),
            "manual-override": manual_override_worker(
                session_factory,
                availability_id=context.availability_id,
                application_id=context.pending_application_ids[1],
                admin_user_id=context.admin_ids[0],
            ),
        },
    )

    assert sum(result["outcome"] == "reassigned" for result in results.values()) == 1
    assert sum(result["outcome"] == "controlled_error" for result in results.values()) == 1
    assert_one_active_assignment(session_factory, context.availability_id)


def test_two_manual_overrides_same_availability_are_serialized(session_factory: SessionFactory) -> None:
    context = seed_cancelled_context(session_factory, suffix="override-override", pending_count=2)
    with session_factory() as db:
        availability = ParkingAvailabilityRepository(db).get_by_id(context.availability_id)
        previous_reservation = ParkingReservationRepository(db).get_by_id(context.previous_reservation_id)
        assert availability is not None
        assert previous_reservation is not None
        previous_reservation.status = ParkingReservationStatus.COMPLETED
        db.flush()
        db.delete(previous_reservation)
        db.commit()

    results = run_concurrently(
        {
            "override-a": manual_override_worker(
                session_factory,
                availability_id=context.availability_id,
                application_id=context.pending_application_ids[0],
                admin_user_id=context.admin_ids[0],
            ),
            "override-b": manual_override_worker(
                session_factory,
                availability_id=context.availability_id,
                application_id=context.pending_application_ids[1],
                admin_user_id=context.admin_ids[1],
            ),
        },
    )

    assert sum(result["outcome"] == "overrode" for result in results.values()) == 1
    assert sum(result["outcome"] == "controlled_error" for result in results.values()) == 1
    assert_one_active_assignment(session_factory, context.availability_id)
    with session_factory() as db:
        assert success_audit_count(db, context.availability_id, AdminReservationOverrideService.RANKING_POLICY) == 1


def test_manual_override_racing_direct_assignment_is_serialized(session_factory: SessionFactory) -> None:
    context = seed_cancelled_context(session_factory, suffix="override-assignment", pending_count=2)
    with session_factory() as db:
        previous_reservation = ParkingReservationRepository(db).get_by_id(context.previous_reservation_id)
        assert previous_reservation is not None
        db.delete(previous_reservation)
        db.commit()

    results = run_concurrently(
        {
            "manual-override": manual_override_worker(
                session_factory,
                availability_id=context.availability_id,
                application_id=context.pending_application_ids[1],
                admin_user_id=context.admin_ids[0],
            ),
            "direct-assignment": direct_assignment_worker(
                session_factory,
                availability_id=context.availability_id,
                trigger_source=ParkingAssignmentTriggerSource.SYSTEM,
            ),
        },
    )

    assert sum(result["outcome"] in {"overrode", "assigned"} for result in results.values()) == 1
    assert sum(result["outcome"] == "controlled_error" for result in results.values()) == 1
    assert_one_active_assignment(session_factory, context.availability_id)


def test_two_application_id_replacements_same_reservation_are_serialized(session_factory: SessionFactory) -> None:
    context = seed_assigned_context(session_factory, suffix="replace-app-app", pending_count=2)

    results = run_concurrently(
        {
            "replace-a": replacement_worker(
                session_factory,
                availability_id=context.availability_id,
                application_id=context.pending_application_ids[0],
                admin_user_id=context.admin_ids[0],
            ),
            "replace-b": replacement_worker(
                session_factory,
                availability_id=context.availability_id,
                application_id=context.pending_application_ids[1],
                admin_user_id=context.admin_ids[1],
            ),
        },
    )

    assert sum(result["outcome"] == "replaced" for result in results.values()) == 1
    assert sum(result["outcome"] == "controlled_error" for result in results.values()) == 1
    assert_one_active_assignment(session_factory, context.availability_id)
    with session_factory() as db:
        assert success_audit_count(db, context.availability_id, AdminReservationOverrideService.REPLACEMENT_POLICY) == 1


def test_two_applicant_id_replacements_same_original_reservation_are_serialized(
    session_factory: SessionFactory,
) -> None:
    context = seed_assigned_context(session_factory, suffix="replace-applicant-applicant", pending_count=2)
    lock_barrier = Barrier(2)

    def availability_repository_factory(db: Session) -> ParkingAvailabilityRepository:
        return BarrierBeforeAvailabilityLockRepository(db, context.availability_id, lock_barrier)

    results = run_concurrently(
        {
            "replace-a": replacement_worker(
                session_factory,
                availability_id=context.availability_id,
                applicant_id=context.pending_user_ids[0],
                admin_user_id=context.admin_ids[0],
                availability_repository_factory=availability_repository_factory,
            ),
            "replace-b": replacement_worker(
                session_factory,
                availability_id=context.availability_id,
                applicant_id=context.pending_user_ids[1],
                admin_user_id=context.admin_ids[1],
                availability_repository_factory=availability_repository_factory,
            ),
        },
    )

    assert sum(result["outcome"] == "replaced" for result in results.values()) == 1
    assert sum(result["outcome"] == "controlled_error" for result in results.values()) == 1
    assert_one_active_assignment(session_factory, context.availability_id)
    with session_factory() as db:
        assert success_audit_count(db, context.availability_id, AdminReservationOverrideService.REPLACEMENT_POLICY) == 1


def test_identical_applicant_id_replacement_repetition_is_controlled(session_factory: SessionFactory) -> None:
    context = seed_assigned_context(session_factory, suffix="replace-identical", pending_count=1)

    first = run_concurrently(
        {
            "replace": replacement_worker(
                session_factory,
                availability_id=context.availability_id,
                applicant_id=context.pending_user_ids[0],
                admin_user_id=context.admin_ids[0],
            ),
        },
    )
    second = run_concurrently(
        {
            "replace": replacement_worker(
                session_factory,
                availability_id=context.availability_id,
                applicant_id=context.pending_user_ids[0],
                admin_user_id=context.admin_ids[1],
            ),
        },
    )

    assert first["replace"]["outcome"] == "replaced"
    assert second["replace"]["outcome"] == "controlled_error"
    assert_one_active_assignment(session_factory, context.availability_id)


def test_application_id_and_applicant_id_replacements_same_original_reservation_are_serialized(
    session_factory: SessionFactory,
) -> None:
    context = seed_assigned_context(session_factory, suffix="replace-app-mixed", pending_count=2)
    lock_barrier = Barrier(2)

    def availability_repository_factory(db: Session) -> ParkingAvailabilityRepository:
        return BarrierBeforeAvailabilityLockRepository(db, context.availability_id, lock_barrier)

    results = run_concurrently(
        {
            "replace-application": replacement_worker(
                session_factory,
                availability_id=context.availability_id,
                application_id=context.pending_application_ids[0],
                admin_user_id=context.admin_ids[0],
                availability_repository_factory=availability_repository_factory,
            ),
            "replace-applicant": replacement_worker(
                session_factory,
                availability_id=context.availability_id,
                applicant_id=context.pending_user_ids[1],
                admin_user_id=context.admin_ids[1],
                availability_repository_factory=availability_repository_factory,
            ),
        },
    )

    assert sum(result["outcome"] == "replaced" for result in results.values()) == 1
    assert sum(result["outcome"] == "controlled_error" for result in results.values()) == 1
    assert_one_active_assignment(session_factory, context.availability_id)
    with session_factory() as db:
        assert success_audit_count(db, context.availability_id, AdminReservationOverrideService.REPLACEMENT_POLICY) == 1


def test_replacement_racing_cancellation_is_serialized(session_factory: SessionFactory) -> None:
    context = seed_assigned_context(session_factory, suffix="replace-cancel", pending_count=2)

    results = run_concurrently(
        {
            "replacement": replacement_worker(
                session_factory,
                availability_id=context.availability_id,
                application_id=context.pending_application_ids[0],
                admin_user_id=context.admin_ids[0],
            ),
            "cancellation": admin_cancellation_worker(
                session_factory,
                reservation_id=context.reservation_id,
                admin_user_id=context.admin_ids[1],
            ),
        },
    )

    assert sum(result["outcome"] in {"replaced", "cancelled"} for result in results.values()) == 1
    assert sum(result["outcome"] == "controlled_error" for result in results.values()) == 1
    with session_factory() as db:
        assert active_reservation_count(db, context.availability_id) in {0, 1}
        assert selected_application_count(db, context.availability_id) <= 1

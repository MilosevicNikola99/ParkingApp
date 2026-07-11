from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from queue import Empty, Queue
from threading import Barrier, Event, Thread
from typing import Any
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.core.config import Settings
from app.db.base import Base
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog, ParkingAssignmentTriggerSource
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.models.user import UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.teams import TeamRepository
from app.repositories.users import UserRepository
from app.schemas.parking_application import ParkingApplicationCreate
from app.services.assignment_scheduler_runner import AssignmentSchedulerRunner
from app.services.parking_application_ranking import ParkingApplicationRankingService
from app.services.parking_applications import (
    ParkingApplicationAvailabilityNotOpenError,
    ParkingApplicationDuplicateError,
    ParkingApplicationService,
)
from app.services.parking_assignment_scheduler import ParkingAssignmentSchedulerService
from app.services.parking_reservation_assignment import (
    ParkingReservationAssignmentAvailabilityNotOpenError,
    ParkingReservationAssignmentNoPendingApplicationsError,
    ParkingReservationAssignmentReservationExistsError,
    ParkingReservationAssignmentService,
)

pytestmark = pytest.mark.postgres_concurrency

POSTGRES_URL_ENV = "POSTGRES_CONCURRENCY_DATABASE_URL"
TEST_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
WORKER_TIMEOUT_SECONDS = 30
SAFE_DATABASE_NAME_FRAGMENTS = ("concurrency", "test", "tmp", "temporary", "disposable")


SessionFactory = sessionmaker[Session]
Worker = Callable[[Barrier], dict[str, Any]]


CONTROLLED_ASSIGNMENT_ERRORS = (
    ParkingReservationAssignmentAvailabilityNotOpenError,
    ParkingReservationAssignmentNoPendingApplicationsError,
    ParkingReservationAssignmentReservationExistsError,
)

CONTROLLED_APPLICATION_ERRORS = (
    ParkingApplicationAvailabilityNotOpenError,
    ParkingApplicationDuplicateError,
)


@dataclass(frozen=True)
class AvailabilityContext:
    availability_id: int
    applicant_ids: tuple[int, ...]
    application_ids: tuple[int, ...]


@dataclass(frozen=True)
class WorkerResult:
    label: str
    value: dict[str, Any] | None = None
    exception: BaseException | None = None


@pytest.fixture(scope="session")
def postgres_database_url() -> str:
    database_url = os.getenv(POSTGRES_URL_ENV)
    if not database_url:
        pytest.skip(f"{POSTGRES_URL_ENV} is not set; PostgreSQL concurrency tests require a disposable database")

    parsed = urlsplit(database_url)
    if not parsed.scheme.startswith("postgresql"):
        pytest.fail(f"{POSTGRES_URL_ENV} must use a PostgreSQL URL")

    database_name = parsed.path.lstrip("/").lower()
    if not database_name or not any(fragment in database_name for fragment in SAFE_DATABASE_NAME_FRAGMENTS):
        pytest.fail(
            f"{POSTGRES_URL_ENV} must point to a disposable database whose name contains one of "
            f"{SAFE_DATABASE_NAME_FRAGMENTS}; got {database_name!r}",
        )

    return database_url


@pytest.fixture(scope="session")
def postgres_engine(postgres_database_url: str) -> Engine:
    engine = create_engine(
        postgres_database_url,
        pool_pre_ping=True,
        pool_size=8,
        max_overflow=8,
    )
    with engine.connect() as connection:
        if connection.dialect.name != "postgresql":
            pytest.fail("PostgreSQL concurrency tests must run against the PostgreSQL dialect")

    yield engine

    engine.dispose()


@pytest.fixture()
def session_factory(postgres_engine: Engine) -> SessionFactory:
    truncate_model_tables(postgres_engine)
    factory = sessionmaker(bind=postgres_engine, autocommit=False, autoflush=False, expire_on_commit=False)

    yield factory

    truncate_model_tables(postgres_engine)


def truncate_model_tables(engine: Engine) -> None:
    table_names = [table.name for table in reversed(Base.metadata.sorted_tables)]
    quoted_names = ", ".join(f'"{table_name}"' for table_name in table_names)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {quoted_names} RESTART IDENTITY CASCADE"))


def configure_worker_session(db: Session) -> None:
    db.execute(text("SET lock_timeout = '5000ms'"))
    db.execute(text("SET statement_timeout = '15000ms'"))


def make_concurrency_settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url=os.getenv(
            POSTGRES_URL_ENV,
            "postgresql+psycopg://parking_app:parking_app@localhost:5432/parking_app_concurrency",
        ),
        metrics_enabled=False,
    )


def build_assignment_service(db: Session) -> ParkingReservationAssignmentService:
    reservation_repository = ParkingReservationRepository(db)
    return ParkingReservationAssignmentService(
        availability_repository=ParkingAvailabilityRepository(db),
        application_repository=ParkingApplicationRepository(db),
        reservation_repository=reservation_repository,
        ranking_service=ParkingApplicationRankingService(
            now_provider=lambda: TEST_NOW,
            recent_win_count_provider=reservation_repository.count_recent_wins_by_user_ids,
            settings=make_concurrency_settings(),
        ),
    )


def build_scheduler(
    db: Session,
    availability_repository: ParkingAvailabilityRepository | None = None,
) -> ParkingAssignmentSchedulerService:
    availability_repository = availability_repository or ParkingAvailabilityRepository(db)
    reservation_repository = ParkingReservationRepository(db)
    assignment_service = ParkingReservationAssignmentService(
        availability_repository=availability_repository,
        application_repository=ParkingApplicationRepository(db),
        reservation_repository=reservation_repository,
        ranking_service=ParkingApplicationRankingService(
            now_provider=lambda: TEST_NOW,
            recent_win_count_provider=reservation_repository.count_recent_wins_by_user_ids,
            settings=make_concurrency_settings(),
        ),
    )
    return ParkingAssignmentSchedulerService(
        db=db,
        availability_repository=availability_repository,
        assignment_service=assignment_service,
        now_provider=lambda: TEST_NOW,
    )


def seed_availability_context(
    session_factory: SessionFactory,
    *,
    suffix: str,
    application_count: int = 2,
) -> AvailabilityContext:
    with session_factory() as db:
        team = TeamRepository(db).create(name=f"Concurrency Team {suffix}")
        owner = UserRepository(db).create(
            email=f"owner.{suffix}@example.com",
            username=f"owner{suffix}",
            first_name="Owner",
            last_name=suffix,
            hashed_password="hashed-password",
            role=UserRole.PARKING_OWNER,
            team_id=team.id,
        )
        parking_spot = ParkingSpotRepository(db).create(
            code=f"CONC-{suffix}",
            location="Concurrency Garage",
            owner_id=owner.id,
        )
        availability = ParkingAvailabilityRepository(db).create(
            parking_spot_id=parking_spot.id,
            owner_id=owner.id,
            start_at=TEST_NOW + timedelta(hours=1),
            end_at=TEST_NOW + timedelta(hours=5),
            status=ParkingAvailabilityStatus.OPEN,
            priority_until=TEST_NOW - timedelta(minutes=1),
        )

        applicant_ids: list[int] = []
        application_ids: list[int] = []
        for index in range(application_count):
            applicant = UserRepository(db).create(
                email=f"employee.{suffix}.{index}@example.com",
                username=f"employee{suffix}{index}",
                first_name="Employee",
                last_name=f"{suffix}{index}",
                hashed_password="hashed-password",
                role=UserRole.EMPLOYEE,
                team_id=team.id,
            )
            application = ParkingApplicationRepository(db).create(
                availability_id=availability.id,
                applicant_id=applicant.id,
                status=ParkingApplicationStatus.PENDING,
                note=f"Application {index}",
            )
            application.created_at = TEST_NOW - timedelta(minutes=application_count - index)
            application.updated_at = application.created_at
            db.flush()
            db.refresh(application)
            applicant_ids.append(applicant.id)
            application_ids.append(application.id)

        db.commit()
        return AvailabilityContext(
            availability_id=availability.id,
            applicant_ids=tuple(applicant_ids),
            application_ids=tuple(application_ids),
        )


def seed_application_context(session_factory: SessionFactory, *, suffix: str) -> tuple[int, int, int]:
    context = seed_availability_context(session_factory, suffix=suffix, application_count=0)
    with session_factory() as db:
        team = TeamRepository(db).get_by_name(f"Concurrency Team {suffix}")
        assert team is not None
        first_employee = UserRepository(db).create(
            email=f"applicant.{suffix}.0@example.com",
            username=f"applicant{suffix}0",
            first_name="Applicant",
            last_name=f"{suffix}0",
            hashed_password="hashed-password",
            role=UserRole.EMPLOYEE,
            team_id=team.id,
        )
        second_employee = UserRepository(db).create(
            email=f"applicant.{suffix}.1@example.com",
            username=f"applicant{suffix}1",
            first_name="Applicant",
            last_name=f"{suffix}1",
            hashed_password="hashed-password",
            role=UserRole.EMPLOYEE,
            team_id=team.id,
        )
        db.commit()
        return context.availability_id, first_employee.id, second_employee.id


def run_concurrently(workers: dict[str, Worker], *, timeout_seconds: int = WORKER_TIMEOUT_SECONDS) -> dict[str, dict[str, Any]]:
    start_barrier = Barrier(len(workers))
    results: Queue[WorkerResult] = Queue()
    threads = [
        Thread(
            target=run_worker,
            args=(label, worker, start_barrier, results),
            daemon=True,
            name=f"postgres-concurrency-{label}",
        )
        for label, worker in workers.items()
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout_seconds)

    alive_threads = [thread.name for thread in threads if thread.is_alive()]
    if alive_threads:
        pytest.fail(f"concurrency worker timeout after {timeout_seconds}s: {alive_threads}")

    collected: dict[str, WorkerResult] = {}
    while len(collected) < len(workers):
        try:
            result = results.get_nowait()
        except Empty as exc:
            raise AssertionError("a concurrency worker exited without reporting a result") from exc
        collected[result.label] = result

    unexpected = {
        label: result.exception
        for label, result in collected.items()
        if result.exception is not None
    }
    if unexpected:
        detail = ", ".join(f"{label}: {type(exc).__name__}: {exc}" for label, exc in unexpected.items())
        pytest.fail(f"unexpected worker exception(s): {detail}")

    return {label: result.value or {} for label, result in collected.items()}


def run_worker(
    label: str,
    worker: Worker,
    start_barrier: Barrier,
    results: Queue[WorkerResult],
) -> None:
    try:
        results.put(WorkerResult(label=label, value=worker(start_barrier)))
    except BaseException as exc:  # noqa: BLE001 - worker failures are surfaced by the parent test thread.
        results.put(WorkerResult(label=label, exception=exc))


def direct_assignment_worker(
    session_factory: SessionFactory,
    *,
    availability_id: int,
    trigger_source: ParkingAssignmentTriggerSource = ParkingAssignmentTriggerSource.SYSTEM,
) -> Worker:
    def worker(start_barrier: Barrier) -> dict[str, Any]:
        with session_factory() as db:
            configure_worker_session(db)
            service = build_assignment_service(db)
            start_barrier.wait(timeout=10)
            try:
                result = service.assign_availability(availability_id, trigger_source=trigger_source)
                reservation_id = result.reservation.id
                db.commit()
                return {"outcome": "assigned", "reservation_id": reservation_id}
            except CONTROLLED_ASSIGNMENT_ERRORS as exc:
                db.rollback()
                return {"outcome": "controlled_error", "error_type": type(exc).__name__}
            except IntegrityError as exc:
                db.rollback()
                raise AssertionError("raw assignment IntegrityError escaped the service boundary") from exc

    return worker


def scheduler_batch_worker(
    session_factory: SessionFactory,
    *,
    list_barrier: Barrier | None = None,
) -> Worker:
    def worker(start_barrier: Barrier) -> dict[str, Any]:
        with session_factory() as db:
            configure_worker_session(db)
            start_barrier.wait(timeout=10)
            availability_repository: ParkingAvailabilityRepository
            if list_barrier is None:
                availability_repository = ParkingAvailabilityRepository(db)
            else:
                availability_repository = CoordinatedListAssignableRepository(db, list_barrier)
            summary = build_scheduler(db, availability_repository).assign_due_availabilities(limit=100)
            return {
                "outcome": "scheduler_cycle",
                "assigned": summary.assigned_count,
                "skipped": summary.skipped_count,
                "failed": summary.failed_count,
                "issues": [issue.code for issue in summary.issues],
            }

    return worker


def application_worker(
    session_factory: SessionFactory,
    *,
    availability_id: int,
    applicant_id: int,
    availability_repository_factory: Callable[[Session], ParkingAvailabilityRepository] = ParkingAvailabilityRepository,
) -> Worker:
    def worker(start_barrier: Barrier) -> dict[str, Any]:
        with session_factory() as db:
            configure_worker_session(db)
            current_user = UserRepository(db).get_by_id(applicant_id)
            assert current_user is not None
            service = ParkingApplicationService(
                application_repository=ParkingApplicationRepository(db),
                availability_repository=availability_repository_factory(db),
                now_provider=lambda: TEST_NOW,
            )
            start_barrier.wait(timeout=10)
            try:
                application = service.apply_for_availability(
                    ParkingApplicationCreate(
                        availability_id=availability_id,
                        note=f"Concurrent application from user {applicant_id}",
                    ),
                    current_user,
                )
                application_id = application.id
                db.commit()
                return {"outcome": "created", "application_id": application_id}
            except CONTROLLED_APPLICATION_ERRORS as exc:
                db.rollback()
                return {"outcome": "controlled_error", "error_type": type(exc).__name__}
            except IntegrityError as exc:
                db.rollback()
                raise AssertionError("raw application IntegrityError escaped the service boundary") from exc

    return worker


class CoordinatedListAssignableRepository(ParkingAvailabilityRepository):
    def __init__(self, db: Session, list_barrier: Barrier) -> None:
        super().__init__(db)
        self.list_barrier = list_barrier

    def list_assignable(self, *, now: datetime, limit: int = 100) -> list[ParkingAvailability]:
        availabilities = super().list_assignable(now=now, limit=limit)
        self.list_barrier.wait(timeout=10)
        return availabilities


class BarrierAfterAvailabilityLockRepository(ParkingAvailabilityRepository):
    def __init__(self, db: Session, lock_barrier: Barrier) -> None:
        super().__init__(db)
        self.lock_barrier = lock_barrier

    def get_by_id_for_update(self, availability_id: int) -> ParkingAvailability | None:
        availability = super().get_by_id_for_update(availability_id)
        self.lock_barrier.wait(timeout=10)
        return availability


def assert_assignment_invariants(session_factory: SessionFactory, availability_id: int) -> None:
    with session_factory() as db:
        active_reservation_count = db.scalar(
            select(func.count(ParkingReservation.id))
            .where(ParkingReservation.availability_id == availability_id)
            .where(ParkingReservation.status == ParkingReservationStatus.ACTIVE),
        )
        selected_application_count = db.scalar(
            select(func.count(ParkingApplication.id))
            .where(ParkingApplication.availability_id == availability_id)
            .where(ParkingApplication.status == ParkingApplicationStatus.SELECTED),
        )
        assignment_audit_count = db.scalar(
            select(func.count(ParkingAssignmentAuditLog.id)).where(
                ParkingAssignmentAuditLog.availability_id == availability_id,
            ),
        )
        availability_status = db.scalar(
            select(ParkingAvailability.status).where(ParkingAvailability.id == availability_id),
        )

        assert active_reservation_count == 1
        assert selected_application_count == 1
        assert assignment_audit_count == 1
        assert availability_status is ParkingAvailabilityStatus.ASSIGNED


def application_status_counts(session_factory: SessionFactory, availability_id: int) -> dict[ParkingApplicationStatus, int]:
    with session_factory() as db:
        rows = db.execute(
            select(ParkingApplication.status, func.count(ParkingApplication.id))
            .where(ParkingApplication.availability_id == availability_id)
            .group_by(ParkingApplication.status),
        ).all()
        return {status: count for status, count in rows}


def test_two_scheduler_workers_attempt_same_due_availability(session_factory: SessionFactory) -> None:
    context = seed_availability_context(session_factory, suffix="scheduler-same", application_count=2)
    list_barrier = Barrier(2)

    results = run_concurrently(
        {
            "scheduler-a": scheduler_batch_worker(session_factory, list_barrier=list_barrier),
            "scheduler-b": scheduler_batch_worker(session_factory, list_barrier=list_barrier),
        },
    )

    assert sum(result["assigned"] for result in results.values()) == 1
    assert sum(result["failed"] for result in results.values()) == 0
    assert sum(result["skipped"] for result in results.values()) == 1
    assert_assignment_invariants(session_factory, context.availability_id)


def test_scheduler_protected_cycle_overlaps_direct_assignment(session_factory: SessionFactory) -> None:
    context = seed_availability_context(session_factory, suffix="runner-direct", application_count=2)
    session_factory_for_runner = session_factory
    listed_barrier = Barrier(2)
    batch_started = Event()

    def coordinated_batch_runner(db: Session, *, limit: int) -> Any:
        availability_repository = CoordinatedListAssignableRepository(db, listed_barrier)
        batch_started.set()
        return build_scheduler(db, availability_repository).assign_due_availabilities(limit=limit)

    settings = make_concurrency_settings()

    def runner_worker(start_barrier: Barrier) -> dict[str, Any]:
        start_barrier.wait(timeout=10)
        runner = AssignmentSchedulerRunner(
            settings=settings,
            session_factory=session_factory_for_runner,
            assignment_batch_runner=coordinated_batch_runner,
        )
        result = runner.run_cycle()
        summary = result.summary
        return {
            "outcome": "runner_cycle",
            "lock_acquired": result.lock_acquired,
            "assigned": summary.assigned_count if summary else 0,
            "skipped": summary.skipped_count if summary else 0,
            "failed": summary.failed_count if summary else 0,
            "error_type": result.error_type,
        }

    def direct_worker(start_barrier: Barrier) -> dict[str, Any]:
        start_barrier.wait(timeout=10)
        assert batch_started.wait(timeout=10)
        return direct_assignment_worker(session_factory, availability_id=context.availability_id)(
            listed_barrier,
        )

    results = run_concurrently(
        {
            "scheduler-runner": runner_worker,
            "direct": direct_worker,
        },
    )

    assert results["scheduler-runner"]["lock_acquired"] is True
    assert results["scheduler-runner"]["failed"] == 0
    assert sum(1 for result in results.values() if result.get("outcome") == "assigned") <= 1
    assigned_total = results["scheduler-runner"]["assigned"] + int(results["direct"]["outcome"] == "assigned")
    assert assigned_total == 1
    assert_assignment_invariants(session_factory, context.availability_id)


def test_two_direct_assignment_calls_overlap(session_factory: SessionFactory) -> None:
    context = seed_availability_context(session_factory, suffix="direct-same", application_count=2)

    results = run_concurrently(
        {
            "direct-a": direct_assignment_worker(session_factory, availability_id=context.availability_id),
            "direct-b": direct_assignment_worker(session_factory, availability_id=context.availability_id),
        },
    )

    assert sum(result["outcome"] == "assigned" for result in results.values()) == 1
    assert sum(result["outcome"] == "controlled_error" for result in results.values()) == 1
    assert_assignment_invariants(session_factory, context.availability_id)


def test_two_different_availabilities_assign_concurrently(session_factory: SessionFactory) -> None:
    first_context = seed_availability_context(session_factory, suffix="direct-independent-a", application_count=2)
    second_context = seed_availability_context(session_factory, suffix="direct-independent-b", application_count=2)

    results = run_concurrently(
        {
            "direct-a": direct_assignment_worker(session_factory, availability_id=first_context.availability_id),
            "direct-b": direct_assignment_worker(session_factory, availability_id=second_context.availability_id),
        },
    )

    assert {result["outcome"] for result in results.values()} == {"assigned"}
    assert_assignment_invariants(session_factory, first_context.availability_id)
    assert_assignment_invariants(session_factory, second_context.availability_id)


def test_same_employee_duplicate_application_creation_is_controlled(session_factory: SessionFactory) -> None:
    availability_id, applicant_id, _ = seed_application_context(session_factory, suffix="same-employee")

    results = run_concurrently(
        {
            "application-a": application_worker(
                session_factory,
                availability_id=availability_id,
                applicant_id=applicant_id,
            ),
            "application-b": application_worker(
                session_factory,
                availability_id=availability_id,
                applicant_id=applicant_id,
            ),
        },
    )

    assert sum(result["outcome"] == "created" for result in results.values()) == 1
    assert sum(result.get("error_type") == "ParkingApplicationDuplicateError" for result in results.values()) == 1
    assert application_status_counts(session_factory, availability_id) == {ParkingApplicationStatus.PENDING: 1}


def test_different_employee_applications_are_retained(session_factory: SessionFactory) -> None:
    availability_id, first_applicant_id, second_applicant_id = seed_application_context(
        session_factory,
        suffix="different-employees",
    )

    results = run_concurrently(
        {
            "application-a": application_worker(
                session_factory,
                availability_id=availability_id,
                applicant_id=first_applicant_id,
            ),
            "application-b": application_worker(
                session_factory,
                availability_id=availability_id,
                applicant_id=second_applicant_id,
            ),
        },
    )

    assert {result["outcome"] for result in results.values()} == {"created"}
    assert application_status_counts(session_factory, availability_id) == {ParkingApplicationStatus.PENDING: 2}


def test_application_submission_overlaps_assignment_start_without_pending_orphan(
    session_factory: SessionFactory,
) -> None:
    context = seed_availability_context(session_factory, suffix="apply-assign", application_count=1)
    _, new_applicant_id, _ = seed_application_context(session_factory, suffix="apply-assign-applicant")
    lock_barrier = Barrier(2)

    def availability_repository_factory(db: Session) -> ParkingAvailabilityRepository:
        return BarrierAfterAvailabilityLockRepository(db, lock_barrier)

    def assignment_after_application_lock_worker(start_barrier: Barrier) -> dict[str, Any]:
        start_barrier.wait(timeout=10)
        lock_barrier.wait(timeout=10)
        return direct_assignment_worker(
            session_factory,
            availability_id=context.availability_id,
            trigger_source=ParkingAssignmentTriggerSource.SYSTEM,
        )(Barrier(1))

    results = run_concurrently(
        {
            "application": application_worker(
                session_factory,
                availability_id=context.availability_id,
                applicant_id=new_applicant_id,
                availability_repository_factory=availability_repository_factory,
            ),
            "assignment": assignment_after_application_lock_worker,
        },
    )

    assert results["application"]["outcome"] == "created"
    assert results["assignment"]["outcome"] == "assigned"
    assert_assignment_invariants(session_factory, context.availability_id)
    status_counts = application_status_counts(session_factory, context.availability_id)
    assert status_counts.get(ParkingApplicationStatus.PENDING, 0) == 0
    assert status_counts.get(ParkingApplicationStatus.SELECTED, 0) == 1
    assert status_counts.get(ParkingApplicationStatus.REJECTED, 0) == 1

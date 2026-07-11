import importlib
import logging

from pydantic import ValidationError
import pytest

from app.commands import run_assignment_scheduler as scheduler_command
from app.core.config import Settings
from app.services.assignment_scheduler_runner import (
    AssignmentSchedulerRunner,
    PostgresAdvisoryLock,
)
from app.services.parking_assignment_scheduler import ParkingAssignmentSchedulerSummary


class FakeSession:
    def __init__(self) -> None:
        self.rollback_count = 0
        self.closed = False

    def rollback(self) -> None:
        self.rollback_count += 1

    def close(self) -> None:
        self.closed = True


class FakeScalarResult:
    def __init__(self, value: bool) -> None:
        self.value = value

    def scalar(self) -> bool:
        return self.value


class FakeExecutingSession(FakeSession):
    def __init__(self, results: list[bool]) -> None:
        super().__init__()
        self.results = results
        self.executed: list[tuple[str, dict[str, int]]] = []

    def execute(self, statement: object, params: dict[str, int]) -> FakeScalarResult:
        self.executed.append((str(statement), params))
        return FakeScalarResult(self.results.pop(0))


class FakeLock:
    def __init__(self, *, acquired: bool = True, release_error: Exception | None = None) -> None:
        self.acquired = acquired
        self.release_error = release_error
        self.acquire_count = 0
        self.release_count = 0

    def acquire(self) -> bool:
        self.acquire_count += 1
        return self.acquired

    def release(self) -> bool:
        self.release_count += 1
        if self.release_error is not None:
            raise self.release_error
        return True


class SharedFakeLock:
    active = False

    def __init__(self) -> None:
        self.acquired = False

    def acquire(self) -> bool:
        if SharedFakeLock.active:
            return False
        SharedFakeLock.active = True
        self.acquired = True
        return True

    def release(self) -> bool:
        if self.acquired:
            SharedFakeLock.active = False
            self.acquired = False
        return True


def scheduler_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "assignment_scheduler_enabled": True,
        "assignment_scheduler_interval_seconds": 5,
        "assignment_scheduler_batch_limit": 25,
        "assignment_scheduler_lock_key": 123456,
        "assignment_scheduler_run_immediately": True,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def summary(
    *,
    processed: int = 2,
    assigned: int = 1,
    skipped: int = 1,
    failed: int = 0,
) -> ParkingAssignmentSchedulerSummary:
    return ParkingAssignmentSchedulerSummary(
        processed_count=processed,
        assigned_count=assigned,
        skipped_count=skipped,
        failed_count=failed,
        issues=(),
    )


def test_scheduler_settings_defaults_and_bounds() -> None:
    settings = Settings(_env_file=None)

    assert settings.assignment_scheduler_enabled is False
    assert settings.assignment_scheduler_interval_seconds == 60
    assert settings.assignment_scheduler_batch_limit == 100
    assert settings.assignment_scheduler_lock_key == 740730001
    assert settings.assignment_scheduler_run_immediately is True
    assert settings.metrics_enabled is True
    assert settings.metrics_path == "/metrics"
    assert settings.scheduler_metrics_port == 9101
    assert settings.readiness_database_timeout_seconds == 2

    with pytest.raises(ValidationError):
        Settings(_env_file=None, assignment_scheduler_interval_seconds=4)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, assignment_scheduler_batch_limit=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, assignment_scheduler_batch_limit=1001)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, assignment_scheduler_lock_key=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, scheduler_metrics_port=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, readiness_database_timeout_seconds=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, metrics_path="metrics")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, metrics_path="/metrics/{tenant}")


def test_run_assignment_scheduler_module_is_import_safe() -> None:
    module = importlib.reload(scheduler_command)

    assert hasattr(module, "main")
    assert hasattr(module, "build_runner")


def test_command_once_runs_single_scheduler_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRunner:
        def __init__(self) -> None:
            self.max_cycles: list[int | None] = []

        def run_forever(self, *, max_cycles: int | None = None) -> int:
            self.max_cycles.append(max_cycles)
            return 0

    fake_runner = FakeRunner()
    monkeypatch.setattr(scheduler_command, "install_signal_handlers", lambda runner: None)

    exit_code = scheduler_command.main(
        ["--once"],
        settings=scheduler_settings(),
        runner_factory=lambda settings: fake_runner,
    )

    assert exit_code == 0
    assert fake_runner.max_cycles == [1]


def test_postgres_advisory_lock_uses_expected_sql() -> None:
    session = FakeExecutingSession([True, True])
    lock = PostgresAdvisoryLock(session, 123456)

    assert lock.acquire() is True
    assert lock.release() is True
    assert session.executed == [
        ("SELECT pg_try_advisory_lock(:lock_key)", {"lock_key": 123456}),
        ("SELECT pg_advisory_unlock(:lock_key)", {"lock_key": 123456}),
    ]


def test_successful_cycle_acquires_lock_runs_batch_logs_summary_and_releases(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = FakeSession()
    lock = FakeLock()
    calls: list[tuple[FakeSession, int]] = []
    logger = logging.getLogger("tests.assignment_scheduler.success")
    expected_summary = summary(processed=3, assigned=2, skipped=1)

    def run_batch(db: FakeSession, *, limit: int) -> ParkingAssignmentSchedulerSummary:
        calls.append((db, limit))
        return expected_summary

    runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(),
        session_factory=lambda: session,
        assignment_batch_runner=run_batch,
        lock_factory=lambda db, lock_key: lock,
        logger=logger,
        run_id_provider=lambda: "run-success",
        monotonic_provider=iter([10.0, 10.25]).__next__,
    )

    with caplog.at_level(logging.INFO, logger=logger.name):
        result = runner.run_cycle()

    assert result.lock_acquired is True
    assert result.summary == expected_summary
    assert result.duration_ms == 250
    assert calls == [(session, 25)]
    assert lock.acquire_count == 1
    assert lock.release_count == 1
    assert session.closed is True
    completed_records = [
        record for record in caplog.records if record.getMessage() == "assignment_scheduler_cycle_completed"
    ]
    assert len(completed_records) == 1
    assert completed_records[0].run_id == "run-success"
    assert completed_records[0].processed_count == 3
    assert completed_records[0].assigned_count == 2
    assert completed_records[0].skipped_count == 1
    assert completed_records[0].failed_count == 0


def test_cycle_skips_when_advisory_lock_is_unavailable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = FakeSession()
    lock = FakeLock(acquired=False)
    calls = 0
    logger = logging.getLogger("tests.assignment_scheduler.lock_unavailable")

    def run_batch(db: FakeSession, *, limit: int) -> ParkingAssignmentSchedulerSummary:
        nonlocal calls
        calls += 1
        return summary()

    runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(),
        session_factory=lambda: session,
        assignment_batch_runner=run_batch,
        lock_factory=lambda db, lock_key: lock,
        logger=logger,
        run_id_provider=lambda: "run-skip",
    )

    with caplog.at_level(logging.INFO, logger=logger.name):
        result = runner.run_cycle()

    assert result.lock_acquired is False
    assert result.summary is None
    assert calls == 0
    assert session.rollback_count == 1
    assert session.closed is True
    assert lock.release_count == 0
    assert any(record.getMessage() == "assignment_scheduler_cycle_skipped_lock_unavailable" for record in caplog.records)


def test_advisory_lock_is_released_after_batch_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = FakeSession()
    lock = FakeLock()
    logger = logging.getLogger("tests.assignment_scheduler.failure")

    def fail_batch(db: FakeSession, *, limit: int) -> ParkingAssignmentSchedulerSummary:
        raise RuntimeError("simulated failure")

    runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(),
        session_factory=lambda: session,
        assignment_batch_runner=fail_batch,
        lock_factory=lambda db, lock_key: lock,
        logger=logger,
        run_id_provider=lambda: "run-fail",
    )

    with caplog.at_level(logging.ERROR, logger=logger.name):
        result = runner.run_cycle()

    assert result.lock_acquired is True
    assert result.summary is None
    assert result.error_type == "RuntimeError"
    assert session.rollback_count == 1
    assert session.closed is True
    assert lock.release_count == 1
    failed_records = [record for record in caplog.records if record.getMessage() == "assignment_scheduler_cycle_failed"]
    assert len(failed_records) == 1
    assert failed_records[0].error_type == "RuntimeError"


def test_recoverable_cycle_failure_does_not_stop_future_cycles() -> None:
    lock = FakeLock()
    calls = 0

    def run_batch(db: FakeSession, *, limit: int) -> ParkingAssignmentSchedulerSummary:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("recoverable")
        return summary(processed=1, assigned=1, skipped=0)

    runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(),
        session_factory=FakeSession,
        assignment_batch_runner=run_batch,
        lock_factory=lambda db, lock_key: lock,
    )
    runner.wait_for_shutdown = lambda seconds: False

    exit_code = runner.run_forever(max_cycles=2)

    assert exit_code == 0
    assert calls == 2


def test_run_forever_respects_immediate_first_cycle() -> None:
    calls = 0
    waits: list[int] = []

    def run_batch(db: FakeSession, *, limit: int) -> ParkingAssignmentSchedulerSummary:
        nonlocal calls
        calls += 1
        return summary(processed=1, assigned=1, skipped=0)

    runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(assignment_scheduler_run_immediately=True),
        session_factory=FakeSession,
        assignment_batch_runner=run_batch,
        lock_factory=lambda db, lock_key: FakeLock(),
    )
    runner.wait_for_shutdown = lambda seconds: waits.append(seconds) or False

    runner.run_forever(max_cycles=1)

    assert calls == 1
    assert waits == []


def test_run_forever_waits_before_first_cycle_when_not_immediate() -> None:
    calls = 0
    waits: list[int] = []

    def run_batch(db: FakeSession, *, limit: int) -> ParkingAssignmentSchedulerSummary:
        nonlocal calls
        calls += 1
        return summary(processed=1, assigned=1, skipped=0)

    runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(
            assignment_scheduler_run_immediately=False,
            assignment_scheduler_interval_seconds=7,
        ),
        session_factory=FakeSession,
        assignment_batch_runner=run_batch,
        lock_factory=lambda db, lock_key: FakeLock(),
    )
    runner.wait_for_shutdown = lambda seconds: waits.append(seconds) or False

    runner.run_forever(max_cycles=1)

    assert waits == [7]
    assert calls == 1


def test_shutdown_signal_stops_before_next_cycle() -> None:
    calls = 0

    def run_batch(db: FakeSession, *, limit: int) -> ParkingAssignmentSchedulerSummary:
        nonlocal calls
        calls += 1
        return summary()

    runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(),
        session_factory=FakeSession,
        assignment_batch_runner=run_batch,
        lock_factory=lambda db, lock_key: FakeLock(),
    )
    runner.request_shutdown(signum=15)

    assert runner.run_forever() == 0
    assert calls == 0


def test_two_scheduler_instances_cannot_execute_the_same_cycle_concurrently() -> None:
    SharedFakeLock.active = False
    nested_results = []
    first_calls = 0
    second_calls = 0

    def lock_factory(db: FakeSession, lock_key: int) -> SharedFakeLock:
        return SharedFakeLock()

    def second_batch(db: FakeSession, *, limit: int) -> ParkingAssignmentSchedulerSummary:
        nonlocal second_calls
        second_calls += 1
        return summary(processed=1, assigned=1, skipped=0)

    second_runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(),
        session_factory=FakeSession,
        assignment_batch_runner=second_batch,
        lock_factory=lock_factory,
        run_id_provider=lambda: "second-run",
    )

    def first_batch(db: FakeSession, *, limit: int) -> ParkingAssignmentSchedulerSummary:
        nonlocal first_calls
        first_calls += 1
        nested_results.append(second_runner.run_cycle())
        return summary(processed=1, assigned=1, skipped=0)

    first_runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(),
        session_factory=FakeSession,
        assignment_batch_runner=first_batch,
        lock_factory=lock_factory,
        run_id_provider=lambda: "first-run",
    )

    first_result = first_runner.run_cycle()

    assert first_result.lock_acquired is True
    assert nested_results[0].lock_acquired is False
    assert first_calls == 1
    assert second_calls == 0
    assert SharedFakeLock.active is False

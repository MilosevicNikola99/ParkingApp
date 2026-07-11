from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from logging import Logger, getLogger
from threading import Event
from time import monotonic
from types import FrameType
from typing import Protocol
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import metrics
from app.core.config import Settings
from app.services.parking_assignment_scheduler import ParkingAssignmentSchedulerSummary


class AssignmentBatchRunner(Protocol):
    def __call__(self, db: Session, *, limit: int) -> ParkingAssignmentSchedulerSummary: ...


class SchedulerLock(Protocol):
    def acquire(self) -> bool: ...

    def release(self) -> bool: ...


SessionFactory = Callable[[], Session]
LockFactory = Callable[[Session, int], SchedulerLock]


@dataclass(frozen=True)
class AssignmentSchedulerCycleResult:
    run_id: str
    lock_acquired: bool
    summary: ParkingAssignmentSchedulerSummary | None
    duration_ms: int
    error_type: str | None = None


class PostgresAdvisoryLock:
    """Session-level PostgreSQL advisory lock used to prevent overlapping scheduler cycles."""

    def __init__(self, db: Session, lock_key: int) -> None:
        self.db = db
        self.lock_key = lock_key

    def acquire(self) -> bool:
        return bool(
            self.db.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": self.lock_key},
            ).scalar(),
        )

    def release(self) -> bool:
        return bool(
            self.db.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": self.lock_key},
            ).scalar(),
        )


def run_assignment_batch_with_session(
    db: Session,
    *,
    limit: int,
) -> ParkingAssignmentSchedulerSummary:
    from app.commands.assign_due_availabilities import build_scheduler

    return build_scheduler(db).assign_due_availabilities(limit=limit)


class AssignmentSchedulerRunner:
    """Continuously run due-availability assignment with PostgreSQL overlap protection."""

    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: SessionFactory,
        assignment_batch_runner: AssignmentBatchRunner = run_assignment_batch_with_session,
        lock_factory: LockFactory = PostgresAdvisoryLock,
        logger: Logger | None = None,
        shutdown_event: Event | None = None,
        run_id_provider: Callable[[], str] | None = None,
        monotonic_provider: Callable[[], float] = monotonic,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.assignment_batch_runner = assignment_batch_runner
        self.lock_factory = lock_factory
        self.logger = logger or getLogger("app.assignment_scheduler")
        self.shutdown_event = shutdown_event or Event()
        self.run_id_provider = run_id_provider or (lambda: str(uuid4()))
        self.monotonic = monotonic_provider

    def run_cycle(self) -> AssignmentSchedulerCycleResult:
        run_id = self.run_id_provider()
        started_at = self.monotonic()
        db = self.session_factory()
        lock: SchedulerLock | None = None
        lock_acquired = False
        extra = self._log_extra(run_id)
        self.logger.info("assignment_scheduler_cycle_started", extra=extra)
        if self.settings.metrics_enabled:
            self._record_metric(metrics.mark_scheduler_cycle_started, event_name="assignment_scheduler_metric_started")

        try:
            lock = self.lock_factory(db, self.settings.assignment_scheduler_lock_key)
            lock_acquired = lock.acquire()
            if not lock_acquired:
                duration_ms = self._duration_ms(started_at)
                self._rollback_if_possible(db)
                self.logger.info(
                    "assignment_scheduler_cycle_skipped_lock_unavailable",
                    extra={
                        **extra,
                        "lock_acquired": False,
                        "duration_ms": duration_ms,
                    },
                )
                if self.settings.metrics_enabled:
                    self._record_metric(
                        metrics.mark_scheduler_cycle_finished,
                        event_name="assignment_scheduler_metric_lock_skipped",
                        result="lock_skipped",
                        duration_seconds=duration_ms / 1000,
                    )
                return AssignmentSchedulerCycleResult(
                    run_id=run_id,
                    lock_acquired=False,
                    summary=None,
                    duration_ms=duration_ms,
                )

            summary = self.assignment_batch_runner(
                db,
                limit=self.settings.assignment_scheduler_batch_limit,
            )
            duration_ms = self._duration_ms(started_at)
            self.logger.info(
                "assignment_scheduler_cycle_completed",
                extra={
                    **extra,
                    "lock_acquired": True,
                    "duration_ms": duration_ms,
                    "processed_count": summary.processed_count,
                    "assigned_count": summary.assigned_count,
                    "skipped_count": summary.skipped_count,
                    "failed_count": summary.failed_count,
                    "issue_count": len(summary.issues),
                },
            )
            if self.settings.metrics_enabled:
                self._record_metric(
                    metrics.mark_scheduler_cycle_finished,
                    event_name="assignment_scheduler_metric_success",
                    result="success",
                    duration_seconds=duration_ms / 1000,
                    assigned_count=summary.assigned_count,
                )
            return AssignmentSchedulerCycleResult(
                run_id=run_id,
                lock_acquired=True,
                summary=summary,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            self._rollback_if_possible(db)
            duration_ms = self._duration_ms(started_at)
            error_type = type(exc).__name__
            self.logger.exception(
                "assignment_scheduler_cycle_failed",
                extra={
                    **extra,
                    "lock_acquired": lock_acquired,
                    "duration_ms": duration_ms,
                    "error_type": error_type,
                },
            )
            if self.settings.metrics_enabled:
                self._record_metric(
                    metrics.mark_scheduler_cycle_finished,
                    event_name="assignment_scheduler_metric_error",
                    result="error",
                    duration_seconds=duration_ms / 1000,
                )
            return AssignmentSchedulerCycleResult(
                run_id=run_id,
                lock_acquired=lock_acquired,
                summary=None,
                duration_ms=duration_ms,
                error_type=error_type,
            )
        finally:
            if self.settings.metrics_enabled:
                self._record_metric(
                    metrics.mark_scheduler_cycle_not_running,
                    event_name="assignment_scheduler_metric_not_running",
                )
            if lock_acquired and lock is not None:
                try:
                    released = lock.release()
                    if not released:
                        self.logger.warning(
                            "assignment_scheduler_lock_release_returned_false",
                            extra={**extra, "lock_acquired": True},
                        )
                except Exception as exc:
                    self.logger.exception(
                        "assignment_scheduler_lock_release_failed",
                        extra={
                            **extra,
                            "lock_acquired": True,
                            "error_type": type(exc).__name__,
                        },
                    )
            self._close_if_possible(db)

    def run_forever(self, *, max_cycles: int | None = None) -> int:
        if not self.settings.assignment_scheduler_enabled:
            self.logger.info(
                "assignment_scheduler_disabled",
                extra={
                    "interval_seconds": self.settings.assignment_scheduler_interval_seconds,
                    "batch_limit": self.settings.assignment_scheduler_batch_limit,
                    "lock_key": self.settings.assignment_scheduler_lock_key,
                },
            )
            return 0

        completed_cycles = 0
        if not self.settings.assignment_scheduler_run_immediately:
            if self.wait_for_shutdown(self.settings.assignment_scheduler_interval_seconds):
                return 0

        while not self.shutdown_event.is_set():
            self.run_cycle()
            completed_cycles += 1
            if max_cycles is not None and completed_cycles >= max_cycles:
                break
            if self.wait_for_shutdown(self.settings.assignment_scheduler_interval_seconds):
                break

        return 0

    def request_shutdown(self, signum: int | None = None, frame: FrameType | None = None) -> None:
        del frame
        self.shutdown_event.set()
        self.logger.info(
            "assignment_scheduler_shutdown_requested",
            extra={
                "interval_seconds": self.settings.assignment_scheduler_interval_seconds,
                "batch_limit": self.settings.assignment_scheduler_batch_limit,
                "lock_key": self.settings.assignment_scheduler_lock_key,
                "signal": signum,
            },
        )

    def wait_for_shutdown(self, seconds: int) -> bool:
        return self.shutdown_event.wait(seconds)

    def _log_extra(self, run_id: str) -> dict[str, int | str]:
        return {
            "run_id": run_id,
            "request_id": run_id,
            "lock_key": self.settings.assignment_scheduler_lock_key,
            "batch_limit": self.settings.assignment_scheduler_batch_limit,
            "interval_seconds": self.settings.assignment_scheduler_interval_seconds,
        }

    def _duration_ms(self, started_at: float) -> int:
        return max(0, int((self.monotonic() - started_at) * 1000))

    def _record_metric(self, recorder: Callable[..., object], *, event_name: str, **kwargs: object) -> None:
        try:
            recorder(**kwargs)
        except Exception as exc:  # pragma: no cover - defensive logging only
            self.logger.warning(
                "assignment_scheduler_metrics_recording_failed",
                extra={**self._safe_error_extra(event_name), "error_type": type(exc).__name__},
            )

    def _safe_error_extra(self, event_name: str) -> dict[str, str]:
        return {"event_name": event_name}

    def _rollback_if_possible(self, db: Session) -> None:
        rollback = getattr(db, "rollback", None)
        if callable(rollback):
            rollback()

    def _close_if_possible(self, db: Session) -> None:
        close = getattr(db, "close", None)
        if callable(close):
            close()

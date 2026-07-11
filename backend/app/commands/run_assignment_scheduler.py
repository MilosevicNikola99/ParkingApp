from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import logging
import signal
import sys

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.metrics import start_standalone_metrics_server
from app.services.assignment_scheduler_runner import AssignmentSchedulerRunner


RunnerFactory = Callable[[Settings], AssignmentSchedulerRunner]


def build_runner(settings: Settings) -> AssignmentSchedulerRunner:
    from app.db.session import SessionLocal

    return AssignmentSchedulerRunner(
        settings=settings,
        session_factory=SessionLocal,
    )


def install_signal_handlers(runner: AssignmentSchedulerRunner) -> None:
    signal.signal(signal.SIGTERM, runner.request_shutdown)
    signal.signal(signal.SIGINT, runner.request_shutdown)


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: Settings | None = None,
    runner_factory: RunnerFactory = build_runner,
) -> int:
    parser = argparse.ArgumentParser(description="Run the due-availability assignment scheduler.")
    parser.add_argument("--once", action="store_true", help="Run one protected scheduler cycle and exit.")
    args = parser.parse_args(argv)

    try:
        resolved_settings = settings or get_settings()
        configure_logging(
            log_level=resolved_settings.log_level,
            log_json=resolved_settings.log_json,
        )
        runner = runner_factory(resolved_settings)
    except Exception as exc:
        print(f"fatal scheduler configuration error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    install_signal_handlers(runner)
    logger = logging.getLogger("app.assignment_scheduler")
    logger.info(
        "assignment_scheduler_started",
        extra={
            "interval_seconds": resolved_settings.assignment_scheduler_interval_seconds,
            "batch_limit": resolved_settings.assignment_scheduler_batch_limit,
            "lock_key": resolved_settings.assignment_scheduler_lock_key,
        },
    )
    if resolved_settings.metrics_enabled:
        if start_standalone_metrics_server(port=resolved_settings.scheduler_metrics_port):
            logger.info(
                "assignment_scheduler_metrics_server_started",
                extra={"metrics_port": resolved_settings.scheduler_metrics_port, "metrics_path": "/metrics"},
            )
        else:
            logger.warning(
                "assignment_scheduler_metrics_server_unavailable",
                extra={"metrics_port": resolved_settings.scheduler_metrics_port, "metrics_path": "/metrics"},
            )

    try:
        return runner.run_forever(max_cycles=1 if args.once else None)
    except Exception as exc:
        logger.exception(
            "assignment_scheduler_fatal_error",
            extra={"error_type": type(exc).__name__},
        )
        return 1
    finally:
        logger.info(
            "assignment_scheduler_stopped",
            extra={
                "interval_seconds": resolved_settings.assignment_scheduler_interval_seconds,
                "batch_limit": resolved_settings.assignment_scheduler_batch_limit,
                "lock_key": resolved_settings.assignment_scheduler_lock_key,
            },
        )


if __name__ == "__main__":
    raise SystemExit(main())

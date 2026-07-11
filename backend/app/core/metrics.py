from __future__ import annotations

import logging
from collections.abc import Callable
from time import time
from typing import TypeVar

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest, start_http_server


logger = logging.getLogger("app.metrics")
T = TypeVar("T")

HTTP_REQUESTS_TOTAL = Counter(
    "parking_http_requests_total",
    "HTTP requests processed by method, normalized route, and status.",
    ("method", "route", "status_code", "status_class"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "parking_http_request_duration_seconds",
    "HTTP request duration in seconds by method, normalized route, and status.",
    ("method", "route", "status_code", "status_class"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "parking_http_requests_in_progress",
    "HTTP requests currently in progress by method.",
    ("method",),
)
UNHANDLED_EXCEPTIONS_TOTAL = Counter(
    "parking_unhandled_exceptions_total",
    "Unhandled application exceptions by broad exception type and normalized route.",
    ("exception_type", "route"),
)
AUTH_FAILURES_TOTAL = Counter(
    "parking_auth_failures_total",
    "Authentication failures by broad safe reason.",
    ("reason",),
)
READINESS_DEPENDENCY_STATUS = Gauge(
    "parking_readiness_dependency_status",
    "Readiness dependency status, where 1 is healthy and 0 is unhealthy.",
    ("dependency",),
)
ASSIGNMENT_CYCLES_TOTAL = Counter(
    "parking_assignment_scheduler_cycles_total",
    "Assignment scheduler cycles by result.",
    ("result",),
)
ASSIGNMENTS_PRODUCED_TOTAL = Counter(
    "parking_assignment_scheduler_assignments_produced_total",
    "Parking reservations produced by the assignment scheduler.",
)
ASSIGNMENT_CYCLE_DURATION_SECONDS = Histogram(
    "parking_assignment_scheduler_cycle_duration_seconds",
    "Assignment scheduler cycle duration in seconds by result.",
    ("result",),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)
ASSIGNMENT_SCHEDULER_LAST_SUCCESS_TIMESTAMP_SECONDS = Gauge(
    "parking_assignment_scheduler_last_success_timestamp_seconds",
    "Unix timestamp of the last successful assignment scheduler cycle.",
)
ASSIGNMENT_SCHEDULER_RUNNING_CYCLES = Gauge(
    "parking_assignment_scheduler_running_cycles",
    "Assignment scheduler cycles currently running.",
)
ASSIGNMENT_SCHEDULER_LOCK_SKIPS_TOTAL = Counter(
    "parking_assignment_scheduler_lock_skips_total",
    "Assignment scheduler cycles skipped because the advisory lock was unavailable.",
)

SCHEDULER_RESULTS = frozenset({"success", "error", "lock_skipped"})


def safe_metric_call(operation: Callable[[], T], *, event_name: str) -> T | None:
    try:
        return operation()
    except Exception as exc:  # pragma: no cover - defensive logging only
        logger.warning(
            "metrics_operation_failed",
            extra={"event_name": event_name, "error_type": type(exc).__name__},
        )
        return None


def status_class(status_code: int) -> str:
    if 100 <= status_code <= 599:
        return f"{status_code // 100}xx"
    return "unknown"


def normalize_route(route: str | None) -> str:
    if not route:
        return "<unmatched>"
    if "{" in route and "}" in route:
        return route
    if route.startswith("/"):
        return route
    return "<unmatched>"


def increment_http_in_progress(method: str) -> None:
    safe_metric_call(
        lambda: HTTP_REQUESTS_IN_PROGRESS.labels(method=method.upper()).inc(),
        event_name="http_in_progress_increment",
    )


def decrement_http_in_progress(method: str) -> None:
    safe_metric_call(
        lambda: HTTP_REQUESTS_IN_PROGRESS.labels(method=method.upper()).dec(),
        event_name="http_in_progress_decrement",
    )


def record_http_request(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    normalized_route = normalize_route(route)
    labels = {
        "method": method.upper(),
        "route": normalized_route,
        "status_code": str(status_code),
        "status_class": status_class(status_code),
    }

    def observe() -> None:
        HTTP_REQUESTS_TOTAL.labels(**labels).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(max(duration_seconds, 0.0))

    safe_metric_call(observe, event_name="http_request_observe")


def record_unhandled_exception(*, exception_type: str, route: str) -> None:
    safe_metric_call(
        lambda: UNHANDLED_EXCEPTIONS_TOTAL.labels(
            exception_type=exception_type,
            route=normalize_route(route),
        ).inc(),
        event_name="unhandled_exception_observe",
    )


def record_auth_failure(reason: str = "invalid_credentials") -> None:
    safe_reason = reason if reason in {"invalid_credentials"} else "other"
    safe_metric_call(
        lambda: AUTH_FAILURES_TOTAL.labels(reason=safe_reason).inc(),
        event_name="auth_failure_observe",
    )


def set_readiness_dependency_status(*, dependency: str, healthy: bool) -> None:
    safe_metric_call(
        lambda: READINESS_DEPENDENCY_STATUS.labels(dependency=dependency).set(1 if healthy else 0),
        event_name="readiness_dependency_observe",
    )


def mark_scheduler_cycle_started() -> None:
    safe_metric_call(
        lambda: ASSIGNMENT_SCHEDULER_RUNNING_CYCLES.inc(),
        event_name="assignment_scheduler_cycle_start_observe",
    )


def mark_scheduler_cycle_finished(
    *,
    result: str,
    duration_seconds: float,
    assigned_count: int = 0,
) -> None:
    safe_result = result if result in SCHEDULER_RESULTS else "error"

    def observe() -> None:
        ASSIGNMENT_CYCLES_TOTAL.labels(result=safe_result).inc()
        ASSIGNMENT_CYCLE_DURATION_SECONDS.labels(result=safe_result).observe(max(duration_seconds, 0.0))
        if safe_result == "success":
            ASSIGNMENTS_PRODUCED_TOTAL.inc(max(assigned_count, 0))
            ASSIGNMENT_SCHEDULER_LAST_SUCCESS_TIMESTAMP_SECONDS.set(time())
        elif safe_result == "lock_skipped":
            ASSIGNMENT_SCHEDULER_LOCK_SKIPS_TOTAL.inc()

    safe_metric_call(observe, event_name="assignment_scheduler_cycle_finish_observe")


def mark_scheduler_cycle_not_running() -> None:
    safe_metric_call(
        lambda: ASSIGNMENT_SCHEDULER_RUNNING_CYCLES.dec(),
        event_name="assignment_scheduler_cycle_running_decrement",
    )


def render_prometheus_metrics() -> bytes:
    return generate_latest()


def start_standalone_metrics_server(*, port: int) -> bool:
    return (
        safe_metric_call(
            lambda: start_http_server(port, addr="0.0.0.0"),
            event_name="standalone_metrics_server_start",
        )
        is not None
    )

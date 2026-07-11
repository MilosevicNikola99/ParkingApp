from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
import json
import math
from pathlib import Path
import random
import re
import socket
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.models.parking_spot import ParkingSpot
from app.models.team import Team
from app.models.user import User


SMOKE_PROFILE = "smoke"
MODERATE_PROFILE = "moderate"
MIN_SMOKE_CONCURRENCY = 5
MAX_SMOKE_CONCURRENCY = 10
MIN_MODERATE_CONCURRENCY = 25
MAX_MODERATE_CONCURRENCY = 50
MAX_SMOKE_ITERATIONS = 3
MAX_MODERATE_ITERATIONS = 2
MAX_REQUEST_TIMEOUT_SECONDS = 30.0
MIN_GLOBAL_TIMEOUT_SECONDS = 30.0
MAX_GLOBAL_TIMEOUT_SECONDS = 600.0
MODERATE_TEAMS = 3
MODERATE_OWNERS = 3
MODERATE_SPOTS_PER_OWNER = 2
MODERATE_AVAILABILITIES_PER_ITERATION = 8
MODERATE_APPLICANTS_PER_AVAILABILITY = 6
POOL_DIAGNOSTIC_TIMEOUT_SECONDS = 0.35
LOCAL_TARGET_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
SENSITIVE_KEY_PARTS = (
    "authorization",
    "credential",
    "database_url",
    "email",
    "identifier",
    "jwt",
    "password",
    "secret",
    "token",
    "url",
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
CREDENTIAL_URL_RE = re.compile(r"([a-z][a-z0-9+.-]*://[^:/\s]+):([^@\s]+)@")


class LoadValidationConfigurationError(ValueError):
    """Raised when the load-validation command is unsafe or invalid."""


class LoadValidationControlledFailure(RuntimeError):
    """Raised when a bounded smoke step fails in a controlled way."""

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        classification: str | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.classification = classification


class ResultClassification(str, Enum):
    SUCCESS = "success"
    EXPECTED_DOMAIN_CONFLICT = "expected_domain_conflict"
    VALIDATION_FAILURE = "validation_failure"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"
    INTENTIONAL_POOL_TIMEOUT = "intentional_pool_timeout"
    TIMEOUT = "timeout"
    UNEXPECTED_SERVER_ERROR = "unexpected_server_error"
    HARNESS_CLIENT_ERROR = "harness_client_error"
    METRIC_COLLECTION_ERROR = "metric_collection_error"
    CLEANUP_ERROR = "cleanup_error"


class CompletionClassification(str, Enum):
    READY = "READY"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class LoadValidationConfig:
    profile: str
    target_base_url: str
    seed: int
    concurrency: int
    iterations: int
    request_timeout_seconds: float
    report_path: Path
    markdown_report_path: Path | None
    cleanup: bool
    allow_non_local_target: bool
    admin_identifier: str
    admin_password: str
    confirm_moderate: bool = False
    global_timeout_seconds: float = 120.0
    scheduler_metrics_url: str | None = None
    collect_metrics: bool = True
    run_pool_diagnostic: bool = True


@dataclass(frozen=True)
class ApiResponse:
    operation: str
    classification: ResultClassification
    status_code: int | None
    latency_ms: float
    json_body: Any = None
    text_body: str | None = None


@dataclass(frozen=True)
class RequestRecord:
    operation: str
    classification: ResultClassification
    status_code: int | None
    latency_ms: float


@dataclass
class RequestRecorder:
    records: list[RequestRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, record: RequestRecord) -> None:
        with self._lock:
            self.records.append(record)

    def snapshot(self) -> list[RequestRecord]:
        with self._lock:
            return list(self.records)


@dataclass
class SmokeContext:
    run_slug: str
    team_ids: list[int] = field(default_factory=list)
    user_ids: list[int] = field(default_factory=list)
    parking_spot_ids: list[int] = field(default_factory=list)
    availability_ids: list[int] = field(default_factory=list)
    reservation_ids: list[int] = field(default_factory=list)
    application_ids: list[int] = field(default_factory=list)
    expected_audit_records: int = 0


@dataclass(frozen=True)
class CleanupResult:
    attempted: bool
    succeeded: bool
    deleted_counts: dict[str, int]
    issue: str | None = None


class ApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        recorder: RequestRecorder,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.recorder = recorder

    def request(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        token: str | None = None,
        json_body: Mapping[str, object] | None = None,
        expected_conflict: bool = False,
        accept_text: bool = False,
    ) -> ApiResponse:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        data: bytes | None = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"

        started = time.perf_counter()
        status_code: int | None = None
        response_text = ""
        try:
            request = Request(url, data=data, headers=headers, method=method.upper())
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status_code = response.status
                response_text = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            status_code = exc.code
            response_text = exc.read().decode("utf-8", errors="replace")
        except (TimeoutError, socket.timeout):
            latency_ms = elapsed_ms(started)
            return self._record(
                ApiResponse(
                    operation=operation,
                    classification=ResultClassification.TIMEOUT,
                    status_code=None,
                    latency_ms=latency_ms,
                ),
            )
        except URLError:
            latency_ms = elapsed_ms(started)
            return self._record(
                ApiResponse(
                    operation=operation,
                    classification=ResultClassification.HARNESS_CLIENT_ERROR,
                    status_code=None,
                    latency_ms=latency_ms,
                ),
            )

        latency_ms = elapsed_ms(started)
        classification = classify_status(status_code, expected_conflict=expected_conflict)
        parsed_json: Any = None
        text_body: str | None = None
        if response_text and not accept_text:
            try:
                parsed_json = json.loads(response_text)
            except json.JSONDecodeError:
                parsed_json = None
        elif accept_text:
            text_body = response_text

        return self._record(
            ApiResponse(
                operation=operation,
                classification=classification,
                status_code=status_code,
                latency_ms=latency_ms,
                json_body=parsed_json,
                text_body=text_body,
            ),
        )

    def _record(self, response: ApiResponse) -> ApiResponse:
        self.recorder.add(
            RequestRecord(
                operation=response.operation,
                classification=response.classification,
                status_code=response.status_code,
                latency_ms=response.latency_ms,
            ),
        )
        return response


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def classify_status(
    status_code: int | None,
    *,
    expected_conflict: bool = False,
) -> ResultClassification:
    if status_code is None:
        return ResultClassification.HARNESS_CLIENT_ERROR
    if 200 <= status_code <= 299:
        return ResultClassification.SUCCESS
    if status_code == 409 and expected_conflict:
        return ResultClassification.EXPECTED_DOMAIN_CONFLICT
    if status_code == 401:
        return ResultClassification.AUTHENTICATION_FAILURE
    if status_code == 403:
        return ResultClassification.AUTHORIZATION_FAILURE
    if status_code in {400, 409, 422}:
        return ResultClassification.VALIDATION_FAILURE
    if status_code >= 500:
        return ResultClassification.UNEXPECTED_SERVER_ERROR
    return ResultClassification.HARNESS_CLIENT_ERROR


def require_success(response: ApiResponse) -> Any:
    if response.classification is not ResultClassification.SUCCESS:
        raise LoadValidationControlledFailure(
            "required smoke operation failed",
            operation=response.operation,
            classification=response.classification.value,
        )
    return response.json_body


def require_expected_conflict(response: ApiResponse) -> None:
    if response.classification is not ResultClassification.EXPECTED_DOMAIN_CONFLICT:
        raise LoadValidationControlledFailure(
            "expected domain conflict did not occur",
            operation=response.operation,
            classification=response.classification.value,
        )


def validate_config(config: LoadValidationConfig) -> None:
    if config.profile == SMOKE_PROFILE:
        validate_smoke_config(config)
    elif config.profile == MODERATE_PROFILE:
        validate_moderate_config(config)
    else:
        raise LoadValidationConfigurationError("profile must be one of: smoke, moderate")

    if not (0.1 <= config.request_timeout_seconds <= MAX_REQUEST_TIMEOUT_SECONDS):
        raise LoadValidationConfigurationError(
            f"request timeout must be between 0.1 and {MAX_REQUEST_TIMEOUT_SECONDS} seconds",
        )
    if not (MIN_GLOBAL_TIMEOUT_SECONDS <= config.global_timeout_seconds <= MAX_GLOBAL_TIMEOUT_SECONDS):
        raise LoadValidationConfigurationError(
            f"global timeout must be between {MIN_GLOBAL_TIMEOUT_SECONDS} and {MAX_GLOBAL_TIMEOUT_SECONDS} seconds",
        )
    if config.seed < 0:
        raise LoadValidationConfigurationError("random seed must be zero or greater")
    if not config.admin_identifier.strip():
        raise LoadValidationConfigurationError("admin identifier is required")
    if not config.admin_password:
        raise LoadValidationConfigurationError("admin password is required")

    validate_target_base_url(
        config.target_base_url,
        allow_non_local_target=config.allow_non_local_target,
    )
    if config.scheduler_metrics_url is not None:
        validate_target_base_url(
            config.scheduler_metrics_url,
            allow_non_local_target=True,
            allow_path=True,
        )


def validate_smoke_config(config: LoadValidationConfig) -> None:
    if not (MIN_SMOKE_CONCURRENCY <= config.concurrency <= MAX_SMOKE_CONCURRENCY):
        raise LoadValidationConfigurationError(
            f"smoke concurrency must be between {MIN_SMOKE_CONCURRENCY} and {MAX_SMOKE_CONCURRENCY}",
        )
    if not (1 <= config.iterations <= MAX_SMOKE_ITERATIONS):
        raise LoadValidationConfigurationError(
            f"smoke iterations must be between 1 and {MAX_SMOKE_ITERATIONS}",
        )


def validate_moderate_config(config: LoadValidationConfig) -> None:
    if not config.confirm_moderate:
        raise LoadValidationConfigurationError("moderate profile requires --confirm-moderate")
    if not (MIN_MODERATE_CONCURRENCY <= config.concurrency <= MAX_MODERATE_CONCURRENCY):
        raise LoadValidationConfigurationError(
            f"moderate concurrency must be between {MIN_MODERATE_CONCURRENCY} and {MAX_MODERATE_CONCURRENCY}",
        )
    if not (1 <= config.iterations <= MAX_MODERATE_ITERATIONS):
        raise LoadValidationConfigurationError(
            f"moderate iterations must be between 1 and {MAX_MODERATE_ITERATIONS}",
        )


def validate_target_base_url(
    target_base_url: str,
    *,
    allow_non_local_target: bool,
    allow_path: bool = False,
) -> None:
    parsed = urlsplit(target_base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise LoadValidationConfigurationError("target base URL must be an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise LoadValidationConfigurationError("target base URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise LoadValidationConfigurationError("target base URL must not include query or fragment components")
    if not allow_path and parsed.path not in {"", "/"}:
        raise LoadValidationConfigurationError("target base URL must point to the API origin root")
    if not is_local_target(parsed.hostname) and not allow_non_local_target:
        raise LoadValidationConfigurationError(
            "refusing non-local target without --allow-non-local-target",
        )


def is_local_target(hostname: str) -> bool:
    normalized = hostname.strip().lower()
    return normalized in LOCAL_TARGET_HOSTS or normalized.endswith(".localhost")


def generate_run_slug(seed: int) -> str:
    rng = random.Random(seed)
    return f"lv_{seed}_{rng.randrange(100_000, 1_000_000)}"


def percentile(values: Sequence[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    if not (0 <= percentile_value <= 100):
        raise ValueError("percentile must be between 0 and 100")

    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return round(sorted_values[0], 3)

    rank = (percentile_value / 100) * (len(sorted_values) - 1)
    lower_index = math.floor(rank)
    upper_index = math.ceil(rank)
    if lower_index == upper_index:
        return round(sorted_values[lower_index], 3)

    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    weight = rank - lower_index
    return round(lower_value + (upper_value - lower_value) * weight, 3)


def sanitize_report_value(value: Any, *, key: str = "") -> Any:
    lowered_key = key.lower()
    if any(part in lowered_key for part in SENSITIVE_KEY_PARTS):
        return "<redacted>"
    if isinstance(value, Mapping):
        return {
            str(child_key): sanitize_report_value(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [sanitize_report_value(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_report_value(item) for item in value]
    if isinstance(value, str):
        redacted = EMAIL_RE.sub("<redacted-email>", value)
        redacted = BEARER_RE.sub("Bearer <redacted-token>", redacted)
        return CREDENTIAL_URL_RE.sub(r"\1:<redacted>@", redacted)
    return value


def target_report_metadata(target_base_url: str, *, allow_non_local_target: bool) -> dict[str, object]:
    parsed = urlsplit(target_base_url)
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "port": parsed.port,
        "is_local": is_local_target(parsed.hostname or ""),
        "non_local_override": allow_non_local_target,
    }


def pool_report_metadata(settings: Settings) -> dict[str, object]:
    return {
        "db_pool_size": settings.db_pool_size,
        "db_max_overflow": settings.db_max_overflow,
        "db_pool_timeout_seconds": settings.db_pool_timeout_seconds,
        "db_pool_recycle_seconds": settings.db_pool_recycle_seconds,
        "db_pool_pre_ping": settings.db_pool_pre_ping,
    }


RELEVANT_METRIC_NAMES = frozenset(
    {
        "parking_http_requests_total",
        "parking_http_request_duration_seconds_count",
        "parking_http_request_duration_seconds_sum",
        "parking_http_request_duration_seconds_bucket",
        "parking_http_requests_in_progress",
        "parking_unhandled_exceptions_total",
        "parking_auth_failures_total",
        "parking_readiness_dependency_status",
        "parking_assignment_scheduler_cycles_total",
        "parking_assignment_scheduler_assignments_produced_total",
        "parking_assignment_scheduler_cycle_duration_seconds_count",
        "parking_assignment_scheduler_cycle_duration_seconds_sum",
        "parking_assignment_scheduler_running_cycles",
        "parking_assignment_scheduler_lock_skips_total",
        "parking_assignment_scheduler_last_success_timestamp_seconds",
    },
)


def parse_prometheus_text(text_value: str) -> dict[str, dict[str, object]]:
    samples: dict[str, dict[str, object]] = {}
    for raw_line in text_value.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            metric_and_labels, raw_value = line.rsplit(" ", 1)
            value = float(raw_value)
        except ValueError:
            continue

        metric_name, labels = parse_metric_name_and_labels(metric_and_labels)
        if metric_name not in RELEVANT_METRIC_NAMES:
            continue
        key = metric_sample_key(metric_name, labels)
        samples[key] = {
            "name": metric_name,
            "labels": labels,
            "value": value,
        }
    return samples


def parse_metric_name_and_labels(metric_and_labels: str) -> tuple[str, dict[str, str]]:
    if "{" not in metric_and_labels:
        return metric_and_labels, {}

    metric_name, raw_labels = metric_and_labels.split("{", 1)
    labels_text = raw_labels.rstrip("}")
    labels: dict[str, str] = {}
    for part in split_prometheus_labels(labels_text):
        if not part or "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        labels[key] = raw_value.strip().strip('"').replace(r"\"", '"').replace(r"\\", "\\")
    return metric_name, labels


def split_prometheus_labels(labels_text: str) -> list[str]:
    labels: list[str] = []
    current: list[str] = []
    in_quotes = False
    escaped = False
    for character in labels_text:
        if escaped:
            current.append(character)
            escaped = False
            continue
        if character == "\\":
            current.append(character)
            escaped = True
            continue
        if character == '"':
            current.append(character)
            in_quotes = not in_quotes
            continue
        if character == "," and not in_quotes:
            labels.append("".join(current))
            current = []
            continue
        current.append(character)
    if current:
        labels.append("".join(current))
    return labels


def metric_sample_key(metric_name: str, labels: Mapping[str, str]) -> str:
    if not labels:
        return metric_name
    label_text = ",".join(f"{key}={labels[key]}" for key in sorted(labels))
    return f"{metric_name}{{{label_text}}}"


def fetch_text_url(url: str, *, timeout_seconds: float) -> str:
    request = Request(url, headers={"Accept": "text/plain"}, method="GET")
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace")


def collect_metric_snapshot(
    *,
    name: str,
    metrics_url: str | None,
    timeout_seconds: float,
) -> dict[str, object]:
    if not metrics_url:
        return {
            "name": name,
            "available": False,
            "error_type": "not_configured",
            "collected_at_utc": datetime.now(UTC).isoformat(),
            "samples": {},
        }
    try:
        text_value = fetch_text_url(metrics_url, timeout_seconds=timeout_seconds)
        samples = parse_prometheus_text(text_value)
        return {
            "name": name,
            "available": True,
            "error_type": None,
            "collected_at_utc": datetime.now(UTC).isoformat(),
            "samples": samples,
        }
    except Exception as exc:
        return {
            "name": name,
            "available": False,
            "error_type": type(exc).__name__,
            "collected_at_utc": datetime.now(UTC).isoformat(),
            "samples": {},
        }


def calculate_metric_deltas(
    baseline: Mapping[str, object],
    final: Mapping[str, object],
) -> dict[str, object]:
    if not baseline.get("available") or not final.get("available"):
        return {
            "available": False,
            "error_type": baseline.get("error_type") or final.get("error_type") or "metric_unavailable",
            "samples": {},
        }

    baseline_samples = baseline.get("samples", {})
    final_samples = final.get("samples", {})
    if not isinstance(baseline_samples, Mapping) or not isinstance(final_samples, Mapping):
        return {"available": False, "error_type": "invalid_snapshot", "samples": {}}

    deltas: dict[str, dict[str, object]] = {}
    for key, final_sample in final_samples.items():
        if not isinstance(final_sample, Mapping):
            continue
        baseline_sample = baseline_samples.get(key, {})
        if not isinstance(baseline_sample, Mapping):
            baseline_value = 0.0
        else:
            baseline_value = float(baseline_sample.get("value", 0.0))
        final_value = float(final_sample.get("value", 0.0))
        delta = final_value - baseline_value
        if delta != 0:
            deltas[key] = {
                "name": final_sample.get("name"),
                "labels": final_sample.get("labels", {}),
                "delta": round(delta, 6),
                "baseline": baseline_value,
                "final": final_value,
            }

    return {"available": True, "error_type": None, "samples": deltas}


def latency_statistics(latencies: Sequence[float]) -> dict[str, float]:
    if not latencies:
        return {
            "p50": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "min": 0.0,
            "max": 0.0,
            "average": 0.0,
        }
    return {
        "p50": percentile(latencies, 50),
        "p95": percentile(latencies, 95),
        "p99": percentile(latencies, 99),
        "min": round(min(latencies), 3),
        "max": round(max(latencies), 3),
        "average": round(sum(latencies) / len(latencies), 3),
    }


def collect_postgres_diagnostics(session_factory: Callable[[], Session]) -> dict[str, object]:
    try:
        with session_factory() as db:
            version = db.execute(text("select version()")).scalar_one()
            activity = db.execute(
                text(
                    """
                    select
                        count(*) filter (where state = 'active') as active_connections,
                        count(*) filter (where state = 'idle') as idle_connections,
                        count(*) filter (where state = 'idle in transaction') as idle_in_transaction_connections,
                        count(*) filter (where wait_event_type is not null) as waiting_sessions,
                        count(*) filter (where cardinality(pg_blocking_pids(pid)) > 0) as blocked_sessions
                    from pg_stat_activity
                    where datname = current_database()
                    """,
                ),
            ).mappings().one()
            lock_count = db.execute(
                text(
                    """
                    select count(*)
                    from pg_locks locks
                    join pg_database db on db.oid = locks.database
                    where db.datname = current_database()
                    """,
                ),
            ).scalar_one()
            deadlocks = db.execute(
                text("select deadlocks from pg_stat_database where datname = current_database()"),
            ).scalar_one_or_none()

        return {
            "available": True,
            "error_type": None,
            "server_version": str(version).split(" on ", 1)[0],
            "active_connections": int(activity["active_connections"] or 0),
            "idle_connections": int(activity["idle_connections"] or 0),
            "idle_in_transaction_connections": int(activity["idle_in_transaction_connections"] or 0),
            "waiting_sessions": int(activity["waiting_sessions"] or 0),
            "total_lock_count": int(lock_count or 0),
            "blocked_sessions": int(activity["blocked_sessions"] or 0),
            "deadlock_count": int(deadlocks or 0),
            "collected_at_utc": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        return {
            "available": False,
            "error_type": type(exc).__name__,
            "collected_at_utc": datetime.now(UTC).isoformat(),
        }


def summarize_postgres_diagnostics(samples: Sequence[Mapping[str, object]]) -> dict[str, object]:
    available_samples = [sample for sample in samples if sample.get("available")]
    if not available_samples:
        return {
            "available": False,
            "error_type": "no_available_samples",
            "samples_collected": len(samples),
        }
    return {
        "available": True,
        "samples_collected": len(samples),
        "maximum_observed_active_sessions": max(
            int(sample.get("active_connections", 0))
            for sample in available_samples
        ),
        "maximum_observed_waiting_sessions": max(
            int(sample.get("waiting_sessions", 0))
            for sample in available_samples
        ),
        "maximum_observed_blocked_sessions": max(
            int(sample.get("blocked_sessions", 0))
            for sample in available_samples
        ),
        "maximum_observed_locks": max(
            int(sample.get("total_lock_count", 0))
            for sample in available_samples
        ),
        "deadlock_count_delta": (
            int(available_samples[-1].get("deadlock_count", 0))
            - int(available_samples[0].get("deadlock_count", 0))
        ),
    }


def run_pool_saturation_diagnostic(database_url: str) -> dict[str, object]:
    if not database_url.startswith("postgresql"):
        return {
            "available": False,
            "classification": "skipped",
            "reason": "pool diagnostic requires PostgreSQL",
        }

    engine = create_engine(
        database_url,
        pool_size=1,
        max_overflow=0,
        pool_timeout=POOL_DIAGNOSTIC_TIMEOUT_SECONDS,
        pool_pre_ping=True,
    )
    holder_ready = threading.Event()
    release_holder = threading.Event()
    results: dict[str, object] = {
        "available": True,
        "classification": "blocked",
        "pool_size": 1,
        "max_overflow": 0,
        "pool_timeout_seconds": POOL_DIAGNOSTIC_TIMEOUT_SECONDS,
        "expected_pool_timeout_observed": False,
        "recovery_success": False,
        "workers_completed": False,
        "checked_out_after_recovery": None,
    }

    def hold_connection() -> None:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
            holder_ready.set()
            release_holder.wait(timeout=2.0)

    def wait_for_connection() -> None:
        holder_ready.wait(timeout=2.0)
        try:
            with engine.connect() as connection:
                connection.execute(text("select 1"))
        except SQLAlchemyTimeoutError:
            results["expected_pool_timeout_observed"] = True

    holder = threading.Thread(target=hold_connection, daemon=True)
    waiter = threading.Thread(target=wait_for_connection, daemon=True)
    holder.start()
    waiter.start()
    waiter.join(timeout=3.0)
    release_holder.set()
    holder.join(timeout=3.0)
    results["workers_completed"] = not holder.is_alive() and not waiter.is_alive()

    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        results["recovery_success"] = True
        pool = engine.pool
        checked_out = getattr(pool, "checkedout", None)
        if callable(checked_out):
            results["checked_out_after_recovery"] = checked_out()
    except Exception as exc:
        results["recovery_error_type"] = type(exc).__name__
    finally:
        engine.dispose()

    if (
        results["expected_pool_timeout_observed"]
        and results["workers_completed"]
        and results["recovery_success"]
    ):
        results["classification"] = ResultClassification.INTENTIONAL_POOL_TIMEOUT.value

    return results


class LoadValidationRunner:
    def __init__(
        self,
        config: LoadValidationConfig,
        *,
        settings: Settings | None = None,
        session_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        validate_config(config)
        self.config = config
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        self.recorder = RequestRecorder()
        self.client = ApiClient(
            base_url=config.target_base_url,
            timeout_seconds=config.request_timeout_seconds,
            recorder=self.recorder,
        )
        self.context = SmokeContext(run_slug=generate_run_slug(config.seed))
        self.started_at: datetime | None = None
        self.ended_at: datetime | None = None
        self.invariant_results: list[dict[str, object]] = []
        self.cleanup_result = CleanupResult(
            attempted=False,
            succeeded=False,
            deleted_counts={},
            issue=None,
        )
        self.issues: list[dict[str, object]] = []
        self.backend_metrics_baseline: dict[str, object] | None = None
        self.backend_metrics_final: dict[str, object] | None = None
        self.scheduler_metrics_baseline: dict[str, object] | None = None
        self.scheduler_metrics_final: dict[str, object] | None = None
        self.metric_deltas: dict[str, object] = {}
        self.postgres_diagnostic_samples: list[dict[str, object]] = []
        self.pool_diagnostic_result: dict[str, object] | None = None
        self._deadline_monotonic: float | None = None
        self._pg_sampler_stop = threading.Event()
        self._pg_sampler_thread: threading.Thread | None = None

    def run(self) -> dict[str, object]:
        self.started_at = datetime.now(UTC)
        self._deadline_monotonic = time.perf_counter() + self.config.global_timeout_seconds
        completion = CompletionClassification.BLOCKED
        partial = False

        try:
            if self.config.profile == MODERATE_PROFILE:
                self._collect_metric_baselines()
                self._start_postgres_sampler()

            self._run_selected_profile()

            if self.config.profile == MODERATE_PROFILE:
                self._stop_postgres_sampler()
                self._collect_metric_finals_and_deltas()

            self.invariant_results = self._check_invariants()
            if self.config.profile == MODERATE_PROFILE and self.config.run_pool_diagnostic:
                self.pool_diagnostic_result = run_pool_saturation_diagnostic(self.settings.database_url)
            if any(not result["passed"] for result in self.invariant_results):
                self.issues.append({"code": "invariant_failed"})
                completion = CompletionClassification.BLOCKED
            elif self._pool_diagnostic_failed():
                self.issues.append({"code": "pool_diagnostic_failed"})
                completion = CompletionClassification.BLOCKED
            else:
                completion = CompletionClassification.READY
        except KeyboardInterrupt:
            partial = True
            self.issues.append({"code": "interrupted"})
            completion = CompletionClassification.BLOCKED
        except LoadValidationControlledFailure as exc:
            partial = True
            self.issues.append(
                {
                    "code": "controlled_failure",
                    "operation": exc.operation,
                    "classification": exc.classification,
                },
            )
            completion = CompletionClassification.BLOCKED
        except Exception as exc:
            partial = True
            self.issues.append(
                {
                    "code": "harness_error",
                    "error_type": type(exc).__name__,
                },
            )
            completion = CompletionClassification.BLOCKED
        finally:
            self._stop_postgres_sampler()
            self.ended_at = datetime.now(UTC)
            if self.config.cleanup:
                self.cleanup_result = self._cleanup_disposable_data()
                if not self.cleanup_result.succeeded:
                    self.issues.append({"code": ResultClassification.CLEANUP_ERROR.value})
                    completion = CompletionClassification.BLOCKED
            else:
                self.cleanup_result = CleanupResult(
                    attempted=False,
                    succeeded=True,
                    deleted_counts={},
                    issue="cleanup disabled by command option",
                )

        report = self._build_report(completion=completion, partial=partial)
        write_json_report(self.config.report_path, report)
        if self.config.markdown_report_path is not None:
            write_markdown_report(self.config.markdown_report_path, report)
        return report

    def _run_selected_profile(self) -> None:
        if self.config.profile == SMOKE_PROFILE:
            self._run_smoke_profile()
            return
        if self.config.profile == MODERATE_PROFILE:
            self._run_moderate_profile()
            return
        raise LoadValidationConfigurationError("unsupported profile")

    def _ensure_within_global_timeout(self) -> None:
        if self._deadline_monotonic is None:
            return
        if time.perf_counter() > self._deadline_monotonic:
            raise LoadValidationControlledFailure(
                "global profile timeout exceeded",
                classification=ResultClassification.TIMEOUT.value,
            )

    def _collect_metric_baselines(self) -> None:
        if not self.config.collect_metrics:
            return
        self.backend_metrics_baseline = collect_metric_snapshot(
            name="backend",
            metrics_url=f"{self.config.target_base_url.rstrip('/')}/metrics",
            timeout_seconds=min(self.config.request_timeout_seconds, 5.0),
        )
        self.scheduler_metrics_baseline = collect_metric_snapshot(
            name="scheduler",
            metrics_url=self.config.scheduler_metrics_url,
            timeout_seconds=min(self.config.request_timeout_seconds, 5.0),
        )

    def _collect_metric_finals_and_deltas(self) -> None:
        if not self.config.collect_metrics:
            return
        self.backend_metrics_final = collect_metric_snapshot(
            name="backend",
            metrics_url=f"{self.config.target_base_url.rstrip('/')}/metrics",
            timeout_seconds=min(self.config.request_timeout_seconds, 5.0),
        )
        self.scheduler_metrics_final = collect_metric_snapshot(
            name="scheduler",
            metrics_url=self.config.scheduler_metrics_url,
            timeout_seconds=min(self.config.request_timeout_seconds, 5.0),
        )
        self.metric_deltas = {
            "backend": calculate_metric_deltas(
                self.backend_metrics_baseline or {},
                self.backend_metrics_final or {},
            ),
            "scheduler": calculate_metric_deltas(
                self.scheduler_metrics_baseline or {},
                self.scheduler_metrics_final or {},
            ),
        }

    def _start_postgres_sampler(self) -> None:
        self.postgres_diagnostic_samples.append(collect_postgres_diagnostics(self.session_factory))
        self._pg_sampler_stop.clear()

        def sample() -> None:
            while not self._pg_sampler_stop.wait(timeout=0.5):
                self.postgres_diagnostic_samples.append(
                    collect_postgres_diagnostics(self.session_factory),
                )

        self._pg_sampler_thread = threading.Thread(target=sample, daemon=True)
        self._pg_sampler_thread.start()

    def _stop_postgres_sampler(self) -> None:
        self._pg_sampler_stop.set()
        if self._pg_sampler_thread is not None:
            self._pg_sampler_thread.join(timeout=2.0)
            self._pg_sampler_thread = None
        if self.config.profile == MODERATE_PROFILE:
            self.postgres_diagnostic_samples.append(
                collect_postgres_diagnostics(self.session_factory),
            )

    def _pool_diagnostic_failed(self) -> bool:
        if self.config.profile != MODERATE_PROFILE or not self.config.run_pool_diagnostic:
            return False
        if not self.pool_diagnostic_result:
            return True
        return self.pool_diagnostic_result.get("classification") != ResultClassification.INTENTIONAL_POOL_TIMEOUT.value

    def _run_smoke_profile(self) -> None:
        admin_token = self._login(
            identifier=self.config.admin_identifier,
            password=self.config.admin_password,
            operation="admin_login",
        )
        require_success(
            self.client.request(
                "GET",
                "/auth/me",
                operation="admin_auth_me",
                token=admin_token,
            ),
        )

        for iteration in range(self.config.iterations):
            self._run_smoke_iteration(iteration=iteration, admin_token=admin_token)

    def _run_smoke_iteration(self, *, iteration: int, admin_token: str) -> None:
        prefix = f"{self.context.run_slug}_i{iteration}"
        disposable_password = f"LoadValidation-{self.config.seed}-{iteration}-pw!"

        team = require_success(
            self.client.request(
                "POST",
                "/admin/teams",
                operation="create_team",
                token=admin_token,
                json_body={
                    "name": f"{prefix}_team",
                    "description": "Disposable load validation team",
                },
            ),
        )
        team_id = int(team["id"])
        self.context.team_ids.append(team_id)

        owner = self._create_user(
            admin_token=admin_token,
            username=f"{prefix}_owner",
            password=disposable_password,
            role="parking_owner",
            team_id=team_id,
        )
        owner_id = int(owner["id"])
        owner_token = self._login(
            identifier=f"{prefix}_owner",
            password=disposable_password,
            operation="owner_login",
        )
        require_success(
            self.client.request(
                "GET",
                "/auth/me",
                operation="owner_auth_me",
                token=owner_token,
            ),
        )

        employee_count = max(self.config.concurrency + 4, 9)
        employees = [
            self._create_user(
                admin_token=admin_token,
                username=f"{prefix}_employee_{index}",
                password=disposable_password,
                role="employee",
                team_id=team_id,
            )
            for index in range(employee_count)
        ]
        employee_tokens = {
            int(employee["id"]): self._login(
                identifier=employee["username"],
                password=disposable_password,
                operation="employee_login",
            )
            for employee in employees
        }

        spot = require_success(
            self.client.request(
                "POST",
                "/admin/parking-spots",
                operation="create_parking_spot",
                token=admin_token,
                json_body={
                    "code": f"{prefix}_spot",
                    "location": "Disposable load validation location",
                    "description": "Disposable load validation spot",
                    "owner_id": owner_id,
                    "is_active": True,
                },
            ),
        )
        parking_spot_id = int(spot["id"])
        self.context.parking_spot_ids.append(parking_spot_id)

        availability_one = self._create_availability(
            owner_token=owner_token,
            parking_spot_id=parking_spot_id,
            iteration=iteration,
            offset_days=7,
            operation="create_availability_for_assignment",
        )
        availability_one_id = int(availability_one["id"])
        self.context.availability_ids.append(availability_one_id)

        self._list_availabilities(owner_token=owner_token, employee_token=next(iter(employee_tokens.values())))
        self._apply_concurrently(
            availability_id=availability_one_id,
            employees=employees[: self.config.concurrency],
            employee_tokens=employee_tokens,
        )
        duplicate_response = self.client.request(
            "POST",
            "/parking-applications",
            operation="duplicate_application_conflict",
            token=employee_tokens[int(employees[0]["id"])],
            json_body={
                "availability_id": availability_one_id,
                "note": "Disposable duplicate application conflict probe",
            },
            expected_conflict=True,
        )
        require_expected_conflict(duplicate_response)

        assigned_reservation = require_success(
            self.client.request(
                "POST",
                f"/parking-availabilities/{availability_one_id}/assign",
                operation="assign_availability",
                token=owner_token,
            ),
        )
        self.context.expected_audit_records += 1
        reservation_one_id = int(assigned_reservation["id"])
        self.context.reservation_ids.append(reservation_one_id)
        selected_user_id = int(assigned_reservation["reserved_for_user_id"])
        selected_employee_token = employee_tokens[selected_user_id]

        require_success(
            self.client.request(
                "GET",
                "/parking-reservations/my",
                operation="employee_reservation_read",
                token=selected_employee_token,
            ),
        )
        require_success(
            self.client.request(
                "GET",
                f"/parking-reservations/{reservation_one_id}",
                operation="reservation_detail_read",
                token=selected_employee_token,
            ),
        )

        require_success(
            self.client.request(
                "PATCH",
                f"/parking-reservations/{reservation_one_id}/cancel",
                operation="employee_reservation_cancel",
                token=selected_employee_token,
                json_body={"reason": "Disposable load validation cancellation"},
            ),
        )

        reassignment_employee = employees[self.config.concurrency]
        reassignment_application = require_success(
            self.client.request(
                "POST",
                "/parking-applications",
                operation="post_cancellation_application",
                token=employee_tokens[int(reassignment_employee["id"])],
                json_body={
                    "availability_id": availability_one_id,
                    "note": "Disposable reassignment candidate",
                },
            ),
        )
        self.context.application_ids.append(int(reassignment_application["id"]))
        reassigned_reservation = require_success(
            self.client.request(
                "POST",
                f"/parking-availabilities/{availability_one_id}/reassign",
                operation="reassign_availability",
                token=owner_token,
                json_body={"reason": "Disposable load validation reassignment"},
            ),
        )
        self.context.expected_audit_records += 1
        self.context.reservation_ids.append(int(reassigned_reservation["id"]))

        availability_two = self._create_availability(
            owner_token=owner_token,
            parking_spot_id=parking_spot_id,
            iteration=iteration,
            offset_days=8,
            operation="create_availability_for_override",
        )
        availability_two_id = int(availability_two["id"])
        self.context.availability_ids.append(availability_two_id)

        override_candidates = employees[self.config.concurrency + 1 : self.config.concurrency + 3]
        override_applications = [
            require_success(
                self.client.request(
                    "POST",
                    "/parking-applications",
                    operation="override_candidate_application",
                    token=employee_tokens[int(employee["id"])],
                    json_body={
                        "availability_id": availability_two_id,
                        "note": "Disposable override candidate",
                    },
                ),
            )
            for employee in override_candidates
        ]
        self.context.application_ids.extend(int(application["id"]) for application in override_applications)

        manual_override = require_success(
            self.client.request(
                "POST",
                f"/admin/parking-availabilities/{availability_two_id}/override-assign",
                operation="admin_manual_override",
                token=admin_token,
                json_body={
                    "application_id": int(override_applications[1]["id"]),
                    "reason": "Disposable load validation manual override",
                },
            ),
        )
        self.context.expected_audit_records += 1
        self.context.reservation_ids.append(int(manual_override["id"]))

        replacement_employee = employees[self.config.concurrency + 3]
        replacement = require_success(
            self.client.request(
                "POST",
                f"/admin/parking-availabilities/{availability_two_id}/replace-reservation",
                operation="admin_replacement_override",
                token=admin_token,
                json_body={
                    "applicant_id": int(replacement_employee["id"]),
                    "reason": "Disposable load validation replacement override",
                },
            ),
        )
        self.context.expected_audit_records += 1
        self.context.reservation_ids.append(int(replacement["id"]))
        if replacement.get("application_id") is not None:
            self.context.application_ids.append(int(replacement["application_id"]))

        self._admin_read_and_report_checks(
            admin_token=admin_token,
            availability_id=availability_two_id,
        )

    def _run_moderate_profile(self) -> None:
        rng = random.Random(self.config.seed)
        admin_token = self._login(
            identifier=self.config.admin_identifier,
            password=self.config.admin_password,
            operation="moderate_admin_login",
        )
        require_success(
            self.client.request(
                "GET",
                "/auth/me",
                operation="moderate_admin_auth_me",
                token=admin_token,
            ),
        )

        for iteration in range(self.config.iterations):
            self._ensure_within_global_timeout()
            self._run_moderate_iteration(
                iteration=iteration,
                admin_token=admin_token,
                rng=rng,
            )

    def _run_moderate_iteration(
        self,
        *,
        iteration: int,
        admin_token: str,
        rng: random.Random,
    ) -> None:
        prefix = f"{self.context.run_slug}_moderate_i{iteration}"
        disposable_password = f"LoadValidationModerate-{self.config.seed}-{iteration}-pw!"

        teams = [
            require_success(
                self.client.request(
                    "POST",
                    "/admin/teams",
                    operation="moderate_create_team",
                    token=admin_token,
                    json_body={
                        "name": f"{prefix}_team_{team_index}",
                        "description": "Disposable moderate load validation team",
                    },
                ),
            )
            for team_index in range(MODERATE_TEAMS)
        ]
        self.context.team_ids.extend(int(team["id"]) for team in teams)

        owners = [
            self._create_user(
                admin_token=admin_token,
                username=f"{prefix}_owner_{owner_index}",
                password=disposable_password,
                role="parking_owner",
                team_id=int(teams[owner_index % len(teams)]["id"]),
            )
            for owner_index in range(MODERATE_OWNERS)
        ]
        owner_tokens = {
            int(owner["id"]): self._login(
                identifier=owner["username"],
                password=disposable_password,
                operation="moderate_owner_login",
            )
            for owner in owners
        }

        employee_count = self.config.concurrency + 15
        employees = [
            self._create_user(
                admin_token=admin_token,
                username=f"{prefix}_employee_{employee_index}",
                password=disposable_password,
                role="employee",
                team_id=int(teams[employee_index % len(teams)]["id"]),
            )
            for employee_index in range(employee_count)
        ]
        employee_tokens = {
            int(employee["id"]): self._login(
                identifier=employee["username"],
                password=disposable_password,
                operation="moderate_employee_login",
            )
            for employee in employees
        }

        spots: list[dict[str, Any]] = []
        for owner_index, owner in enumerate(owners):
            owner_id = int(owner["id"])
            for spot_index in range(MODERATE_SPOTS_PER_OWNER):
                spot = require_success(
                    self.client.request(
                        "POST",
                        "/admin/parking-spots",
                        operation="moderate_create_parking_spot",
                        token=admin_token,
                        json_body={
                            "code": f"{prefix}_spot_{owner_index}_{spot_index}",
                            "location": "Disposable moderate load validation location",
                            "description": "Disposable moderate load validation spot",
                            "owner_id": owner_id,
                            "is_active": True,
                        },
                    ),
                )
                self.context.parking_spot_ids.append(int(spot["id"]))
                spots.append(spot)

        availabilities: list[dict[str, Any]] = []
        for availability_index in range(MODERATE_AVAILABILITIES_PER_ITERATION):
            spot = spots[availability_index % len(spots)]
            owner_id = int(spot["owner_id"])
            availability = self._create_availability(
                owner_token=owner_tokens[owner_id],
                parking_spot_id=int(spot["id"]),
                iteration=iteration,
                offset_days=20 + (availability_index // len(spots)),
                operation="moderate_create_availability",
            )
            self.context.availability_ids.append(int(availability["id"]))
            availabilities.append(availability)

        availability_applications: dict[int, list[dict[str, Any]]] = {}
        self._apply_moderate_applications(
            availabilities=availabilities,
            employees=employees,
            employee_tokens=employee_tokens,
            rng=rng,
            availability_applications=availability_applications,
        )

        first_availability_id = int(availabilities[0]["id"])
        first_applicant_id = int(availability_applications[first_availability_id][0]["applicant_id"])
        require_expected_conflict(
            self.client.request(
                "POST",
                "/parking-applications",
                operation="moderate_duplicate_application_conflict",
                token=employee_tokens[first_applicant_id],
                json_body={
                    "availability_id": first_availability_id,
                    "note": "Disposable moderate duplicate application conflict probe",
                },
                expected_conflict=True,
            ),
        )

        self._run_moderate_read_mix(
            admin_token=admin_token,
            owner_tokens=owner_tokens,
            employee_tokens=employee_tokens,
            availability_id=first_availability_id,
        )

        owner_tokens_by_availability = {
            int(availability["id"]): owner_tokens[int(availability["owner_id"])]
            for availability in availabilities
        }

        assigned_reservation = require_success(
            self.client.request(
                "POST",
                f"/parking-availabilities/{first_availability_id}/assign",
                operation="moderate_assign_availability",
                token=owner_tokens_by_availability[first_availability_id],
            ),
        )
        self.context.expected_audit_records += 1
        first_reservation_id = int(assigned_reservation["id"])
        self.context.reservation_ids.append(first_reservation_id)
        selected_user_id = int(assigned_reservation["reserved_for_user_id"])
        require_success(
            self.client.request(
                "PATCH",
                f"/parking-reservations/{first_reservation_id}/cancel",
                operation="moderate_employee_reservation_cancel",
                token=employee_tokens[selected_user_id],
                json_body={"reason": "Disposable moderate cancellation"},
            ),
        )

        reassignment_employee = self._unused_employee_for_availability(
            employees,
            availability_applications[first_availability_id],
        )
        reassignment_application = require_success(
            self.client.request(
                "POST",
                "/parking-applications",
                operation="moderate_post_cancellation_application",
                token=employee_tokens[int(reassignment_employee["id"])],
                json_body={
                    "availability_id": first_availability_id,
                    "note": "Disposable moderate reassignment candidate",
                },
            ),
        )
        self.context.application_ids.append(int(reassignment_application["id"]))
        availability_applications[first_availability_id].append(reassignment_application)
        reassigned_reservation = require_success(
            self.client.request(
                "POST",
                f"/parking-availabilities/{first_availability_id}/reassign",
                operation="moderate_reassign_availability",
                token=owner_tokens_by_availability[first_availability_id],
                json_body={"reason": "Disposable moderate reassignment"},
            ),
        )
        self.context.expected_audit_records += 1
        self.context.reservation_ids.append(int(reassigned_reservation["id"]))

        override_availability_id = int(availabilities[1]["id"])
        override_applications = availability_applications[override_availability_id]
        manual_override = require_success(
            self.client.request(
                "POST",
                f"/admin/parking-availabilities/{override_availability_id}/override-assign",
                operation="moderate_admin_manual_override",
                token=admin_token,
                json_body={
                    "application_id": int(override_applications[1]["id"]),
                    "reason": "Disposable moderate manual override",
                },
            ),
        )
        self.context.expected_audit_records += 1
        self.context.reservation_ids.append(int(manual_override["id"]))

        replacement_application_employee = self._unused_employee_for_availability(
            employees,
            availability_applications[override_availability_id],
        )
        replacement_application = self._create_pending_application_direct(
            availability_id=override_availability_id,
            applicant_id=int(replacement_application_employee["id"]),
            note="Disposable moderate application-id replacement candidate",
        )
        self.context.application_ids.append(int(replacement_application["id"]))
        availability_applications[override_availability_id].append(replacement_application)
        application_replacement = require_success(
            self.client.request(
                "POST",
                f"/admin/parking-availabilities/{override_availability_id}/replace-reservation",
                operation="moderate_admin_replacement_by_application",
                token=admin_token,
                json_body={
                    "application_id": int(replacement_application["id"]),
                    "reason": "Disposable moderate replacement by application",
                },
            ),
        )
        self.context.expected_audit_records += 1
        self.context.reservation_ids.append(int(application_replacement["id"]))

        replacement_applicant = self._unused_employee_for_availability(
            employees,
            availability_applications[override_availability_id],
        )
        applicant_replacement = require_success(
            self.client.request(
                "POST",
                f"/admin/parking-availabilities/{override_availability_id}/replace-reservation",
                operation="moderate_admin_replacement_by_applicant",
                token=admin_token,
                json_body={
                    "applicant_id": int(replacement_applicant["id"]),
                    "reason": "Disposable moderate replacement by applicant",
                },
            ),
        )
        self.context.expected_audit_records += 1
        self.context.reservation_ids.append(int(applicant_replacement["id"]))
        if applicant_replacement.get("application_id") is not None:
            self.context.application_ids.append(int(applicant_replacement["application_id"]))

        for availability in availabilities[2:5]:
            self._ensure_within_global_timeout()
            availability_id = int(availability["id"])
            reservation = require_success(
                self.client.request(
                    "POST",
                    f"/parking-availabilities/{availability_id}/assign",
                    operation="moderate_additional_assignment",
                    token=owner_tokens_by_availability[availability_id],
                ),
            )
            self.context.expected_audit_records += 1
            self.context.reservation_ids.append(int(reservation["id"]))

        self._run_moderate_read_mix(
            admin_token=admin_token,
            owner_tokens=owner_tokens,
            employee_tokens=employee_tokens,
            availability_id=override_availability_id,
        )

    def _apply_moderate_applications(
        self,
        *,
        availabilities: Sequence[Mapping[str, Any]],
        employees: Sequence[Mapping[str, Any]],
        employee_tokens: Mapping[int, str],
        rng: random.Random,
        availability_applications: dict[int, list[dict[str, Any]]],
    ) -> None:
        jobs: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
        for availability in availabilities:
            selected_employees = rng.sample(list(employees), MODERATE_APPLICANTS_PER_AVAILABILITY)
            for employee in selected_employees:
                jobs.append((availability, employee))

        def apply(job: tuple[Mapping[str, Any], Mapping[str, Any]]) -> tuple[int, ApiResponse]:
            availability, employee = job
            employee_id = int(employee["id"])
            availability_id = int(availability["id"])
            return (
                availability_id,
                self.client.request(
                    "POST",
                    "/parking-applications",
                    operation="moderate_concurrent_application_create",
                    token=employee_tokens[employee_id],
                    json_body={
                        "availability_id": availability_id,
                        "note": "Disposable moderate concurrent application",
                    },
                ),
            )

        with ThreadPoolExecutor(max_workers=self.config.concurrency) as executor:
            futures = [executor.submit(apply, job) for job in jobs]
            for future in as_completed(futures, timeout=self.config.global_timeout_seconds):
                availability_id, response = future.result()
                application = require_success(response)
                availability_applications.setdefault(availability_id, []).append(application)
                self.context.application_ids.append(int(application["id"]))

    def _run_moderate_read_mix(
        self,
        *,
        admin_token: str,
        owner_tokens: Mapping[int, str],
        employee_tokens: Mapping[int, str],
        availability_id: int,
    ) -> None:
        read_jobs: list[tuple[str, str, str, bool]] = [
            ("GET", "/auth/me", admin_token, False),
            ("GET", "/parking-availabilities", next(iter(employee_tokens.values())), False),
            ("GET", "/parking-applications/my", next(iter(employee_tokens.values())), False),
            ("GET", "/parking-reservations/my", next(iter(employee_tokens.values())), False),
            ("GET", "/parking-availabilities/my", next(iter(owner_tokens.values())), False),
            ("GET", f"/admin/parking-applications?availability_id={availability_id}", admin_token, False),
            ("GET", f"/admin/parking-reservations/history?availability_id={availability_id}", admin_token, False),
            ("GET", f"/admin/assignment-audit-logs?availability_id={availability_id}", admin_token, False),
            ("GET", "/admin/reports/summary", admin_token, False),
            ("GET", "/admin/reports/top-users", admin_token, False),
            ("GET", "/admin/reports/parking-spot-usage", admin_token, False),
            ("GET", "/admin/reports/reservations.csv", admin_token, True),
        ]
        for token in list(employee_tokens.values())[: min(12, len(employee_tokens))]:
            read_jobs.extend(
                [
                    ("GET", "/auth/me", token, False),
                    ("GET", "/parking-availabilities", token, False),
                    ("GET", "/parking-applications/my", token, False),
                    ("GET", "/parking-reservations/my", token, False),
                ],
            )

        def read(job: tuple[str, str, str, bool]) -> ApiResponse:
            method, path, token, accept_text = job
            return self.client.request(
                method,
                path,
                operation="moderate_read_mix",
                token=token,
                accept_text=accept_text,
            )

        with ThreadPoolExecutor(max_workers=self.config.concurrency) as executor:
            futures = [executor.submit(read, job) for job in read_jobs]
            for future in as_completed(futures, timeout=self.config.global_timeout_seconds):
                require_success(future.result())

    def _unused_employee_for_availability(
        self,
        employees: Sequence[Mapping[str, Any]],
        applications: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        used_applicant_ids = {int(application["applicant_id"]) for application in applications}
        for employee in employees:
            if int(employee["id"]) not in used_applicant_ids:
                return employee
        raise LoadValidationControlledFailure(
            "no unused employee available for moderate workload",
            classification=ResultClassification.VALIDATION_FAILURE.value,
        )

    def _create_pending_application_direct(
        self,
        *,
        availability_id: int,
        applicant_id: int,
        note: str,
    ) -> dict[str, Any]:
        """Create disposable internal setup data for app-id replacement validation."""
        try:
            with self.session_factory() as db:
                application = ParkingApplication(
                    availability_id=availability_id,
                    applicant_id=applicant_id,
                    status=ParkingApplicationStatus.PENDING,
                    note=note,
                )
                db.add(application)
                db.commit()
                db.refresh(application)
                return {
                    "id": application.id,
                    "availability_id": application.availability_id,
                    "applicant_id": application.applicant_id,
                    "status": application.status.value,
                }
        except Exception as exc:
            raise LoadValidationControlledFailure(
                "failed to create disposable replacement application setup",
                operation="moderate_replacement_candidate_setup",
                classification=ResultClassification.HARNESS_CLIENT_ERROR.value,
            ) from exc

    def _create_user(
        self,
        *,
        admin_token: str,
        username: str,
        password: str,
        role: str,
        team_id: int,
    ) -> dict[str, Any]:
        user = require_success(
            self.client.request(
                "POST",
                "/admin/users",
                operation=f"create_{role}_user",
                token=admin_token,
                json_body={
                    "email": f"{username}@example.com",
                    "username": username,
                    "first_name": "Load",
                    "last_name": "Validation",
                    "password": password,
                    "role": role,
                    "team_id": team_id,
                    "is_active": True,
                },
            ),
        )
        self.context.user_ids.append(int(user["id"]))
        return user

    def _login(self, *, identifier: str, password: str, operation: str) -> str:
        response = require_success(
            self.client.request(
                "POST",
                "/auth/login",
                operation=operation,
                json_body={"identifier": identifier, "password": password},
            ),
        )
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise LoadValidationControlledFailure(
                "login response did not contain an access token",
                operation=operation,
                classification=ResultClassification.VALIDATION_FAILURE.value,
            )
        return token

    def _create_availability(
        self,
        *,
        owner_token: str,
        parking_spot_id: int,
        iteration: int,
        offset_days: int,
        operation: str,
    ) -> dict[str, Any]:
        start_at = datetime.now(UTC).replace(microsecond=0) + timedelta(
            days=offset_days + (iteration * 3),
        )
        end_at = start_at + timedelta(hours=8)
        availability = require_success(
            self.client.request(
                "POST",
                "/parking-availabilities",
                operation=operation,
                token=owner_token,
                json_body={
                    "parking_spot_id": parking_spot_id,
                    "start_at": start_at.isoformat(),
                    "end_at": end_at.isoformat(),
                    "note": "Disposable load validation availability",
                },
            ),
        )
        return availability

    def _list_availabilities(self, *, owner_token: str, employee_token: str) -> None:
        require_success(
            self.client.request(
                "GET",
                "/parking-availabilities",
                operation="list_available_spots",
                token=employee_token,
            ),
        )
        require_success(
            self.client.request(
                "GET",
                "/parking-availabilities/my",
                operation="list_my_availabilities",
                token=owner_token,
            ),
        )

    def _apply_concurrently(
        self,
        *,
        availability_id: int,
        employees: Sequence[Mapping[str, Any]],
        employee_tokens: Mapping[int, str],
    ) -> None:
        def apply(employee: Mapping[str, Any]) -> ApiResponse:
            employee_id = int(employee["id"])
            return self.client.request(
                "POST",
                "/parking-applications",
                operation="concurrent_application_create",
                token=employee_tokens[employee_id],
                json_body={
                    "availability_id": availability_id,
                    "note": "Disposable concurrent application",
                },
            )

        with ThreadPoolExecutor(max_workers=self.config.concurrency) as executor:
            futures = [executor.submit(apply, employee) for employee in employees]
            for future in as_completed(futures, timeout=self.config.request_timeout_seconds * self.config.concurrency):
                response = future.result()
                application = require_success(response)
                self.context.application_ids.append(int(application["id"]))

    def _admin_read_and_report_checks(self, *, admin_token: str, availability_id: int) -> None:
        paths = [
            ("admin_application_read", f"/admin/parking-applications?availability_id={availability_id}", False),
            ("admin_reservation_history_read", f"/admin/parking-reservations/history?availability_id={availability_id}", False),
            ("admin_audit_log_read", f"/admin/assignment-audit-logs?availability_id={availability_id}", False),
            ("admin_report_summary", "/admin/reports/summary", False),
            ("admin_report_top_users", "/admin/reports/top-users", False),
            ("admin_report_parking_spot_usage", "/admin/reports/parking-spot-usage", False),
            ("admin_report_reservations_csv", "/admin/reports/reservations.csv", True),
            ("admin_report_applications_csv", "/admin/reports/applications.csv", True),
            ("admin_report_audit_logs_csv", "/admin/reports/audit-logs.csv", True),
        ]
        for operation, path, accept_text in paths:
            require_success(
                self.client.request(
                    "GET",
                    path,
                    operation=operation,
                    token=admin_token,
                    accept_text=accept_text,
                ),
            )

    def _check_invariants(self) -> list[dict[str, object]]:
        if not self.context.availability_ids:
            return [
                {
                    "name": "dataset_created",
                    "passed": False,
                    "details": "no tracked availability ids",
                },
            ]

        with self.session_factory() as db:
            checks = [
                self._check_active_reservation_uniqueness(db),
                self._check_selected_application_uniqueness(db),
                self._check_duplicate_applications(db),
                self._check_availability_reservation_state_agreement(db),
                self._check_reservation_application_coherence(db),
                self._check_expected_audit_records(db),
                self._check_orphan_references(db),
            ]
        return checks

    def _check_active_reservation_uniqueness(self, db: Session) -> dict[str, object]:
        rows = db.execute(
            select(ParkingReservation.availability_id, func.count(ParkingReservation.id))
            .where(ParkingReservation.availability_id.in_(self.context.availability_ids))
            .where(ParkingReservation.status == ParkingReservationStatus.ACTIVE)
            .group_by(ParkingReservation.availability_id)
            .having(func.count(ParkingReservation.id) > 1),
        ).all()
        return invariant_result("active_reservation_uniqueness", not rows, len(rows))

    def _check_selected_application_uniqueness(self, db: Session) -> dict[str, object]:
        rows = db.execute(
            select(ParkingApplication.availability_id, func.count(ParkingApplication.id))
            .where(ParkingApplication.availability_id.in_(self.context.availability_ids))
            .where(ParkingApplication.status == ParkingApplicationStatus.SELECTED)
            .group_by(ParkingApplication.availability_id)
            .having(func.count(ParkingApplication.id) > 1),
        ).all()
        return invariant_result("selected_application_uniqueness", not rows, len(rows))

    def _check_duplicate_applications(self, db: Session) -> dict[str, object]:
        rows = db.execute(
            select(
                ParkingApplication.availability_id,
                ParkingApplication.applicant_id,
                func.count(ParkingApplication.id),
            )
            .where(ParkingApplication.availability_id.in_(self.context.availability_ids))
            .group_by(ParkingApplication.availability_id, ParkingApplication.applicant_id)
            .having(func.count(ParkingApplication.id) > 1),
        ).all()
        return invariant_result("duplicate_application_uniqueness", not rows, len(rows))

    def _check_availability_reservation_state_agreement(self, db: Session) -> dict[str, object]:
        violations = 0
        availabilities = list(
            db.execute(
                select(ParkingAvailability).where(ParkingAvailability.id.in_(self.context.availability_ids)),
            ).scalars(),
        )
        active_counts = {
            availability_id: count
            for availability_id, count in db.execute(
                select(ParkingReservation.availability_id, func.count(ParkingReservation.id))
                .where(ParkingReservation.availability_id.in_(self.context.availability_ids))
                .where(ParkingReservation.status == ParkingReservationStatus.ACTIVE)
                .group_by(ParkingReservation.availability_id),
            ).all()
        }
        for availability in availabilities:
            active_count = active_counts.get(availability.id, 0)
            if availability.status is ParkingAvailabilityStatus.ASSIGNED and active_count != 1:
                violations += 1
            if active_count > 0 and availability.status is not ParkingAvailabilityStatus.ASSIGNED:
                violations += 1

        return invariant_result("availability_reservation_state_agreement", violations == 0, violations)

    def _check_reservation_application_coherence(self, db: Session) -> dict[str, object]:
        violations = 0
        reservations = list(
            db.execute(
                select(ParkingReservation).where(ParkingReservation.availability_id.in_(self.context.availability_ids)),
            ).scalars(),
        )
        application_ids = [reservation.application_id for reservation in reservations if reservation.application_id]
        applications = {
            application.id: application
            for application in db.execute(
                select(ParkingApplication).where(ParkingApplication.id.in_(application_ids or [-1])),
            ).scalars()
        }
        availabilities = {
            availability.id: availability
            for availability in db.execute(
                select(ParkingAvailability).where(ParkingAvailability.id.in_(self.context.availability_ids)),
            ).scalars()
        }
        for reservation in reservations:
            availability = availabilities.get(reservation.availability_id)
            application = applications.get(reservation.application_id)
            if availability is None or application is None:
                violations += 1
                continue
            if reservation.parking_spot_id != availability.parking_spot_id:
                violations += 1
            if reservation.reserved_for_user_id != application.applicant_id:
                violations += 1
            if reservation.status is ParkingReservationStatus.ACTIVE and application.status is not ParkingApplicationStatus.SELECTED:
                violations += 1
            if reservation.status is ParkingReservationStatus.CANCELLED and application.status is ParkingApplicationStatus.SELECTED:
                violations += 1

        return invariant_result("cancellation_replacement_history_coherence", violations == 0, violations)

    def _check_expected_audit_records(self, db: Session) -> dict[str, object]:
        count = db.execute(
            select(func.count(ParkingAssignmentAuditLog.id)).where(
                ParkingAssignmentAuditLog.availability_id.in_(self.context.availability_ids),
            ),
        ).scalar_one()
        return {
            "name": "expected_success_audit_records",
            "passed": count == self.context.expected_audit_records,
            "details": {
                "expected": self.context.expected_audit_records,
                "actual": count,
            },
        }

    def _check_orphan_references(self, db: Session) -> dict[str, object]:
        reservation_application_orphans = db.execute(
            select(func.count(ParkingReservation.id))
            .outerjoin(ParkingApplication, ParkingReservation.application_id == ParkingApplication.id)
            .where(ParkingReservation.availability_id.in_(self.context.availability_ids))
            .where(ParkingReservation.application_id.is_not(None))
            .where(ParkingApplication.id.is_(None)),
        ).scalar_one()
        application_availability_orphans = db.execute(
            select(func.count(ParkingApplication.id))
            .outerjoin(ParkingAvailability, ParkingApplication.availability_id == ParkingAvailability.id)
            .where(ParkingApplication.availability_id.in_(self.context.availability_ids))
            .where(ParkingAvailability.id.is_(None)),
        ).scalar_one()
        audit_reservation_orphans = db.execute(
            select(func.count(ParkingAssignmentAuditLog.id))
            .outerjoin(ParkingReservation, ParkingAssignmentAuditLog.reservation_id == ParkingReservation.id)
            .where(ParkingAssignmentAuditLog.availability_id.in_(self.context.availability_ids))
            .where(ParkingReservation.id.is_(None)),
        ).scalar_one()
        total = reservation_application_orphans + application_availability_orphans + audit_reservation_orphans
        return invariant_result("orphan_reference_absence", total == 0, total)

    def _cleanup_disposable_data(self) -> CleanupResult:
        deleted_counts: dict[str, int] = {}
        try:
            with self.session_factory() as db:
                if self.context.availability_ids:
                    deleted_counts["audit_logs"] = db.execute(
                        delete(ParkingAssignmentAuditLog).where(
                            ParkingAssignmentAuditLog.availability_id.in_(self.context.availability_ids),
                        ),
                    ).rowcount or 0
                    deleted_counts["reservations"] = db.execute(
                        delete(ParkingReservation).where(
                            ParkingReservation.availability_id.in_(self.context.availability_ids),
                        ),
                    ).rowcount or 0
                    deleted_counts["applications"] = db.execute(
                        delete(ParkingApplication).where(
                            ParkingApplication.availability_id.in_(self.context.availability_ids),
                        ),
                    ).rowcount or 0
                    deleted_counts["availabilities"] = db.execute(
                        delete(ParkingAvailability).where(ParkingAvailability.id.in_(self.context.availability_ids)),
                    ).rowcount or 0
                if self.context.parking_spot_ids:
                    deleted_counts["parking_spots"] = db.execute(
                        delete(ParkingSpot).where(ParkingSpot.id.in_(self.context.parking_spot_ids)),
                    ).rowcount or 0
                if self.context.user_ids:
                    deleted_counts["users"] = db.execute(
                        delete(User).where(User.id.in_(self.context.user_ids)),
                    ).rowcount or 0
                if self.context.team_ids:
                    deleted_counts["teams"] = db.execute(
                        delete(Team).where(Team.id.in_(self.context.team_ids)),
                    ).rowcount or 0
                db.commit()
        except Exception as exc:
            return CleanupResult(
                attempted=True,
                succeeded=False,
                deleted_counts=deleted_counts,
                issue=type(exc).__name__,
            )

        return CleanupResult(
            attempted=True,
            succeeded=True,
            deleted_counts=deleted_counts,
        )

    def _build_report(
        self,
        *,
        completion: CompletionClassification,
        partial: bool,
    ) -> dict[str, object]:
        records = self.recorder.snapshot()
        latencies = [record.latency_ms for record in records]
        duration_seconds = (
            0.0
            if self.started_at is None or self.ended_at is None
            else max(0.0, (self.ended_at - self.started_at).total_seconds())
        )
        classification_counts = Counter(record.classification.value for record in records)
        operation_counts = Counter(record.operation for record in records)
        dataset_sizes = {
            "teams": len(self.context.team_ids),
            "users": len(self.context.user_ids),
            "parking_spots": len(self.context.parking_spot_ids),
            "availabilities": len(self.context.availability_ids),
            "applications": len(self.context.application_ids),
            "reservations": len(set(self.context.reservation_ids)),
        }

        report = {
            "report_schema_version": 2,
            "profile": self.config.profile,
            "random_seed": self.config.seed,
            "started_at_utc": self.started_at.isoformat() if self.started_at else None,
            "ended_at_utc": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": round(duration_seconds, 3),
            "dataset_sizes": dataset_sizes,
            "concurrency": self.config.concurrency,
            "iterations": self.config.iterations,
            "request_timeout_seconds": self.config.request_timeout_seconds,
            "global_timeout_seconds": self.config.global_timeout_seconds,
            "target": target_report_metadata(
                self.config.target_base_url,
                allow_non_local_target=self.config.allow_non_local_target,
            ),
            "request_counts": {
                "total": len(records),
                "by_classification": dict(sorted(classification_counts.items())),
                "by_operation": dict(sorted(operation_counts.items())),
            },
            "latency_ms": latency_statistics(latencies),
            "throughput_requests_per_second": (
                round(len(records) / duration_seconds, 3)
                if duration_seconds > 0
                else 0.0
            ),
            "pool_configuration": pool_report_metadata(self.settings),
            "prometheus": {
                "backend": {
                    "baseline": self.backend_metrics_baseline,
                    "final": self.backend_metrics_final,
                    "delta": self.metric_deltas.get("backend"),
                },
                "scheduler": {
                    "baseline": self.scheduler_metrics_baseline,
                    "final": self.scheduler_metrics_final,
                    "delta": self.metric_deltas.get("scheduler"),
                },
            },
            "postgres_diagnostics": {
                "samples": self.postgres_diagnostic_samples,
                "summary": summarize_postgres_diagnostics(self.postgres_diagnostic_samples),
            },
            "pool_diagnostic": self.pool_diagnostic_result,
            "invariants": self.invariant_results,
            "cleanup": {
                "attempted": self.cleanup_result.attempted,
                "succeeded": self.cleanup_result.succeeded,
                "deleted_counts": self.cleanup_result.deleted_counts,
                "issue": self.cleanup_result.issue,
            },
            "partial": partial,
            "completion_classification": completion.value,
            "issues": self.issues,
        }
        return sanitize_report_value(report)


def invariant_result(name: str, passed: bool, violation_count: int) -> dict[str, object]:
    return {
        "name": name,
        "passed": passed,
        "details": {"violation_count": violation_count},
    }


def write_json_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_markdown_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    latency = report.get("latency_ms", {})
    request_counts = report.get("request_counts", {})
    pool_diagnostic = report.get("pool_diagnostic") or {}
    postgres_diagnostics = report.get("postgres_diagnostics") or {}
    postgres_summary = (
        postgres_diagnostics.get("summary", {})
        if isinstance(postgres_diagnostics, Mapping)
        else {}
    )
    content = "\n".join(
        [
            "# PostgreSQL Load Validation Report",
            "",
            f"- Profile: `{report.get('profile')}`",
            f"- Completion: `{report.get('completion_classification')}`",
            f"- Random seed: `{report.get('random_seed')}`",
            f"- Duration seconds: `{report.get('duration_seconds')}`",
            f"- Concurrency: `{report.get('concurrency')}`",
            f"- Iterations: `{report.get('iterations')}`",
            f"- Total requests: `{request_counts.get('total') if isinstance(request_counts, Mapping) else 0}`",
            (
                f"- Latency p50/p95/p99 ms: "
                f"`{latency.get('p50') if isinstance(latency, Mapping) else 0}` / "
                f"`{latency.get('p95') if isinstance(latency, Mapping) else 0}` / "
                f"`{latency.get('p99') if isinstance(latency, Mapping) else 0}`"
            ),
            (
                f"- Latency min/max/average ms: "
                f"`{latency.get('min') if isinstance(latency, Mapping) else 0}` / "
                f"`{latency.get('max') if isinstance(latency, Mapping) else 0}` / "
                f"`{latency.get('average') if isinstance(latency, Mapping) else 0}`"
            ),
            (
                f"- Pool diagnostic: "
                f"`{pool_diagnostic.get('classification') if isinstance(pool_diagnostic, Mapping) else 'not_run'}`"
            ),
            (
                f"- PostgreSQL diagnostic samples: "
                f"`{postgres_summary.get('samples_collected') if isinstance(postgres_summary, Mapping) else 0}`"
            ),
            "",
            "## Invariants",
            "",
            *[
                f"- `{item.get('name')}`: {'passed' if item.get('passed') else 'failed'}"
                for item in report.get("invariants", [])
                if isinstance(item, Mapping)
            ],
            "",
        ],
    )
    path.write_text(content, encoding="utf-8")


def run_load_validation(
    config: LoadValidationConfig,
    *,
    settings: Settings | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
) -> dict[str, object]:
    runner = LoadValidationRunner(
        config,
        settings=settings,
        session_factory=session_factory,
    )
    return runner.run()

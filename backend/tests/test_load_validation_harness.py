from pathlib import Path

import pytest

from app.commands import run_load_validation as command
from app.core.config import Settings
from app.load_validation.smoke import (
    CompletionClassification,
    LoadValidationConfig,
    LoadValidationConfigurationError,
    LoadValidationControlledFailure,
    LoadValidationRunner,
    ResultClassification,
    calculate_metric_deltas,
    classify_status,
    collect_postgres_diagnostics,
    generate_run_slug,
    latency_statistics,
    parse_prometheus_text,
    percentile,
    run_pool_saturation_diagnostic,
    sanitize_report_value,
    validate_config,
)


def valid_config(tmp_path: Path, **overrides: object) -> LoadValidationConfig:
    values: dict[str, object] = {
        "profile": "smoke",
        "target_base_url": "http://localhost:8000",
        "seed": 123,
        "concurrency": 5,
        "iterations": 1,
        "request_timeout_seconds": 1.0,
        "report_path": tmp_path / "report.json",
        "markdown_report_path": None,
        "cleanup": True,
        "allow_non_local_target": False,
        "admin_identifier": "admin",
        "admin_password": "admin-password",
    }
    values.update(overrides)
    return LoadValidationConfig(**values)


def test_cli_uses_environment_variable_names_for_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOAD_VALIDATION_ADMIN_IDENTIFIER", "local_admin")
    monkeypatch.setenv("LOAD_VALIDATION_ADMIN_PASSWORD", "local-password")
    args = command.build_parser().parse_args(
        [
            "--profile",
            "smoke",
            "--target-base-url",
            "http://localhost:8000",
            "--seed",
            "42",
            "--concurrency",
            "5",
            "--iterations",
            "1",
            "--request-timeout",
            "2",
            "--report-path",
            str(tmp_path / "report.json"),
            "--no-cleanup",
        ],
    )

    config = command.config_from_args(args)

    assert config.admin_identifier == "local_admin"
    assert config.admin_password == "local-password"
    assert config.cleanup is False
    assert config.seed == 42


def test_command_returns_success_only_for_ready_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOAD_VALIDATION_ADMIN_IDENTIFIER", "local_admin")
    monkeypatch.setenv("LOAD_VALIDATION_ADMIN_PASSWORD", "local-password")
    monkeypatch.setattr(
        command,
        "run_load_validation",
        lambda config: {"completion_classification": CompletionClassification.READY.value},
    )

    result = command.main(["--report-path", str(tmp_path / "report.json")])

    assert result == 0


def test_config_rejects_non_local_target_without_explicit_override(tmp_path: Path) -> None:
    config = valid_config(tmp_path, target_base_url="https://parking.example.com")

    with pytest.raises(LoadValidationConfigurationError, match="non-local"):
        validate_config(config)


def test_config_accepts_non_local_target_with_explicit_override(tmp_path: Path) -> None:
    validate_config(
        valid_config(
            tmp_path,
            target_base_url="https://staging.parking.example.com",
            allow_non_local_target=True,
        ),
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"profile": "moderate"},
        {"concurrency": 4},
        {"concurrency": 11},
        {"iterations": 0},
        {"iterations": 4},
        {"request_timeout_seconds": 0},
        {"request_timeout_seconds": 31},
        {"seed": -1},
        {"target_base_url": "postgresql://localhost/app"},
        {"target_base_url": "http://user:password@localhost:8000"},
        {"admin_identifier": ""},
        {"admin_password": ""},
    ],
)
def test_config_enforces_phase_3a_safety_limits(tmp_path: Path, overrides: dict[str, object]) -> None:
    with pytest.raises(LoadValidationConfigurationError):
        validate_config(valid_config(tmp_path, **overrides))


def test_run_slug_is_deterministic() -> None:
    assert generate_run_slug(123) == generate_run_slug(123)
    assert generate_run_slug(123) != generate_run_slug(124)


def test_percentile_calculation_uses_interpolation() -> None:
    values = [10.0, 20.0, 30.0, 40.0]

    assert percentile(values, 50) == 25.0
    assert percentile(values, 95) == 38.5
    assert percentile([], 95) == 0.0


def test_result_classification() -> None:
    assert classify_status(200) is ResultClassification.SUCCESS
    assert classify_status(201) is ResultClassification.SUCCESS
    assert classify_status(409, expected_conflict=True) is ResultClassification.EXPECTED_DOMAIN_CONFLICT
    assert classify_status(409) is ResultClassification.VALIDATION_FAILURE
    assert classify_status(422) is ResultClassification.VALIDATION_FAILURE
    assert classify_status(401) is ResultClassification.AUTHENTICATION_FAILURE
    assert classify_status(403) is ResultClassification.AUTHORIZATION_FAILURE
    assert classify_status(500) is ResultClassification.UNEXPECTED_SERVER_ERROR
    assert classify_status(None) is ResultClassification.HARNESS_CLIENT_ERROR


def test_moderate_profile_requires_confirmation(tmp_path: Path) -> None:
    with pytest.raises(LoadValidationConfigurationError, match="confirm"):
        validate_config(
            valid_config(
                tmp_path,
                profile="moderate",
                concurrency=25,
                iterations=1,
            ),
        )


def test_moderate_profile_accepts_confirmed_bounded_values(tmp_path: Path) -> None:
    validate_config(
        valid_config(
            tmp_path,
            profile="moderate",
            confirm_moderate=True,
            concurrency=25,
            iterations=1,
            global_timeout_seconds=120,
        ),
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"concurrency": 24},
        {"concurrency": 51},
        {"iterations": 0},
        {"iterations": 3},
        {"global_timeout_seconds": 29},
        {"global_timeout_seconds": 601},
    ],
)
def test_moderate_profile_enforces_safe_maximums(
    tmp_path: Path,
    overrides: dict[str, object],
) -> None:
    values = {
        "profile": "moderate",
        "confirm_moderate": True,
        "concurrency": 25,
        "iterations": 1,
    }
    values.update(overrides)

    with pytest.raises(LoadValidationConfigurationError):
        validate_config(valid_config(tmp_path, **values))


def test_cli_builds_confirmed_moderate_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOAD_VALIDATION_ADMIN_IDENTIFIER", "local_admin")
    monkeypatch.setenv("LOAD_VALIDATION_ADMIN_PASSWORD", "local-password")
    args = command.build_parser().parse_args(
        [
            "--profile",
            "moderate",
            "--confirm-moderate",
            "--concurrency",
            "25",
            "--iterations",
            "1",
            "--global-timeout",
            "120",
            "--scheduler-metrics-url",
            "http://assignment-scheduler:9101/metrics",
            "--report-path",
            str(tmp_path / "moderate.json"),
        ],
    )

    config = command.config_from_args(args)

    assert config.profile == "moderate"
    assert config.confirm_moderate is True
    assert config.concurrency == 25
    assert config.scheduler_metrics_url == "http://assignment-scheduler:9101/metrics"


def test_prometheus_parser_keeps_relevant_metrics_and_labels() -> None:
    parsed = parse_prometheus_text(
        """
        # HELP parking_http_requests_total test
        parking_http_requests_total{method="GET",route="/auth/me",status_code="200",status_class="2xx"} 3
        parking_http_requests_in_progress{method="GET"} 0
        unrelated_metric_total{tenant="dynamic"} 99
        """,
    )

    assert (
        'parking_http_requests_total{method=GET,route=/auth/me,status_class=2xx,status_code=200}'
        in parsed
    )
    assert "parking_http_requests_in_progress{method=GET}" in parsed
    assert all(sample["name"] != "unrelated_metric_total" for sample in parsed.values())


def test_metric_delta_calculation_handles_missing_baseline_samples() -> None:
    baseline = {
        "available": True,
        "samples": {
            "parking_auth_failures_total{reason=invalid_credentials}": {
                "name": "parking_auth_failures_total",
                "labels": {"reason": "invalid_credentials"},
                "value": 1.0,
            },
        },
    }
    final = {
        "available": True,
        "samples": {
            "parking_auth_failures_total{reason=invalid_credentials}": {
                "name": "parking_auth_failures_total",
                "labels": {"reason": "invalid_credentials"},
                "value": 4.0,
            },
            "parking_assignment_scheduler_assignments_produced_total": {
                "name": "parking_assignment_scheduler_assignments_produced_total",
                "labels": {},
                "value": 2.0,
            },
        },
    }

    delta = calculate_metric_deltas(baseline, final)

    assert delta["available"] is True
    assert delta["samples"]["parking_auth_failures_total{reason=invalid_credentials}"]["delta"] == 3.0
    assert delta["samples"]["parking_assignment_scheduler_assignments_produced_total"]["delta"] == 2.0


def test_metric_delta_reports_missing_metrics_cleanly() -> None:
    delta = calculate_metric_deltas(
        {"available": False, "error_type": "URLError"},
        {"available": True, "samples": {}},
    )

    assert delta == {"available": False, "error_type": "URLError", "samples": {}}


def test_latency_statistics_include_min_max_and_average() -> None:
    stats = latency_statistics([100.0, 200.0, 300.0])

    assert stats["p50"] == 200.0
    assert stats["min"] == 100.0
    assert stats["max"] == 300.0
    assert stats["average"] == 200.0


def test_pool_diagnostic_skips_non_postgresql_urls() -> None:
    result = run_pool_saturation_diagnostic("sqlite+pysqlite:///:memory:")

    assert result["classification"] == "skipped"
    assert result["available"] is False


def test_postgres_diagnostics_failure_is_sanitized() -> None:
    class FailingSession:
        def __enter__(self) -> "FailingSession":
            return self

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            return None

        def execute(self, statement: object) -> object:
            raise RuntimeError("sensitive query should not appear")

    result = collect_postgres_diagnostics(FailingSession)

    assert result["available"] is False
    assert result["error_type"] == "RuntimeError"
    assert "sensitive" not in str(result)


def test_report_sanitization_redacts_sensitive_values() -> None:
    report = {
        "email": "admin@example.com",
        "token": "Bearer abc.def.ghi",
        "database_url": "postgresql+psycopg://user:secret@db:5432/app",
        "nested": {
            "message": "Contact employee@example.com with Bearer secret-token",
            "safe_count": 3,
        },
    }

    sanitized = sanitize_report_value(report)
    rendered = str(sanitized)

    assert "admin@example.com" not in rendered
    assert "employee@example.com" not in rendered
    assert "abc.def.ghi" not in rendered
    assert "secret-token" not in rendered
    assert "user:secret@" not in rendered
    assert sanitized["nested"]["safe_count"] == 3


class FakeSession:
    def __init__(self) -> None:
        self.execute_calls = 0
        self.committed = False

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def execute(self, statement: object) -> object:
        self.execute_calls += 1

        class Result:
            rowcount = 1

        return Result()

    def commit(self) -> None:
        self.committed = True


def test_cleanup_deletes_only_tracked_disposable_ids(tmp_path: Path) -> None:
    fake_session = FakeSession()
    runner = LoadValidationRunner(
        valid_config(tmp_path),
        settings=Settings(_env_file=None),
        session_factory=lambda: fake_session,
    )
    runner.context.team_ids.append(1)
    runner.context.user_ids.append(2)
    runner.context.parking_spot_ids.append(3)
    runner.context.availability_ids.append(4)

    result = runner._cleanup_disposable_data()

    assert result.attempted is True
    assert result.succeeded is True
    assert fake_session.committed is True
    assert fake_session.execute_calls == 7
    assert result.deleted_counts["availabilities"] == 1
    assert result.deleted_counts["teams"] == 1


def test_partial_report_is_written_for_controlled_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = LoadValidationRunner(
        valid_config(tmp_path),
        settings=Settings(_env_file=None),
        session_factory=FakeSession,
    )

    def fail_smoke() -> None:
        raise LoadValidationControlledFailure(
            "failed",
            operation="test_operation",
            classification=ResultClassification.VALIDATION_FAILURE.value,
        )

    monkeypatch.setattr(runner, "_run_smoke_profile", fail_smoke)

    report = runner.run()

    assert report["completion_classification"] == CompletionClassification.BLOCKED.value
    assert report["partial"] is True
    assert report["issues"] == [
        {
            "code": "controlled_failure",
            "operation": "test_operation",
            "classification": ResultClassification.VALIDATION_FAILURE.value,
        },
    ]
    assert (tmp_path / "report.json").exists()


def test_interruption_is_reported_without_secret_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = LoadValidationRunner(
        valid_config(tmp_path),
        settings=Settings(_env_file=None),
        session_factory=FakeSession,
    )

    monkeypatch.setattr(
        runner,
        "_run_smoke_profile",
        lambda: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    report = runner.run()

    assert report["completion_classification"] == CompletionClassification.BLOCKED.value
    assert report["partial"] is True
    assert report["issues"] == [{"code": "interrupted"}]
    assert "admin-password" not in (tmp_path / "report.json").read_text(encoding="utf-8")

import re

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.core.metrics import render_prometheus_metrics
from app.main import create_app
from app.services.assignment_scheduler_runner import AssignmentSchedulerRunner
from app.services.parking_assignment_scheduler import ParkingAssignmentSchedulerSummary


def metric_value(metric_output: str, metric_name: str, labels: dict[str, str] | None = None) -> float:
    labels = labels or {}
    for line in metric_output.splitlines():
        if not line.startswith(metric_name):
            continue
        if labels:
            label_text = line.split("{", 1)[1].split("}", 1)[0] if "{" in line else ""
            if any(f'{key}="{value}"' not in label_text for key, value in labels.items()):
                continue
        return float(line.rsplit(" ", 1)[1])
    return 0.0


def add_test_routes(app: FastAPI) -> None:
    @app.get("/test/items/{item_id}")
    def read_item(item_id: str) -> dict[str, str]:
        return {"item_id": item_id}

    @app.get("/test/fail/{item_id}")
    def fail_item(item_id: str) -> None:
        raise RuntimeError(f"sensitive failure for {item_id}")


def test_metrics_endpoint_returns_prometheus_output_and_uses_route_templates() -> None:
    app = create_app(Settings(_env_file=None))
    add_test_routes(app)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/test/items/user-12345@example.com")
    metrics_response = client.get("/metrics")

    assert response.status_code == 200
    assert metrics_response.status_code == 200
    assert metrics_response.headers["content-type"].startswith("text/plain")
    output = metrics_response.text
    assert "parking_http_requests_total" in output
    assert "parking_http_request_duration_seconds_bucket" in output
    assert 'route="/test/items/{item_id}"' in output
    assert 'status_class="2xx"' in output
    assert "user-12345@example.com" not in output
    assert "item_id" not in output.replace("/test/items/{item_id}", "")
    assert re.search(r'parking_http_requests_in_progress\{method="GET"\} 0\.0', output)


def test_metrics_do_not_label_404_with_raw_paths() -> None:
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/missing/sensitive-user-12345")
    output = client.get("/metrics").text

    assert response.status_code == 404
    assert 'route="<unmatched>"' in output
    assert "sensitive-user-12345" not in output


def test_metrics_endpoint_itself_is_not_recorded() -> None:
    client = TestClient(create_app(Settings(_env_file=None)))

    client.get("/metrics")
    client.get("/metrics")
    output = client.get("/metrics").text

    assert 'route="/metrics"' not in output


def test_metrics_can_be_disabled() -> None:
    client = TestClient(create_app(Settings(_env_file=None, metrics_enabled=False)))

    response = client.get("/metrics")

    assert response.status_code == 404


def test_unhandled_exception_metric_uses_safe_labels() -> None:
    app = create_app(Settings(_env_file=None))
    add_test_routes(app)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/test/fail/user-12345@example.com")
    output = client.get("/metrics").text

    assert response.status_code == 500
    assert "parking_unhandled_exceptions_total" in output
    assert 'route="/test/fail/{item_id}"' in output
    assert "user-12345@example.com" not in output
    assert "sensitive failure" not in output


class FakeSession:
    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


class FakeLock:
    def __init__(self, acquired: bool = True) -> None:
        self.acquired = acquired

    def acquire(self) -> bool:
        return self.acquired

    def release(self) -> bool:
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


def summary(*, assigned: int = 1) -> ParkingAssignmentSchedulerSummary:
    return ParkingAssignmentSchedulerSummary(
        processed_count=1,
        assigned_count=assigned,
        skipped_count=0,
        failed_count=0,
        issues=(),
    )


def current_metrics_output() -> str:
    return render_prometheus_metrics().decode("utf-8")


def test_scheduler_success_metrics_increment() -> None:
    before = current_metrics_output()
    before_success = metric_value(
        before,
        "parking_assignment_scheduler_cycles_total",
        {"result": "success"},
    )
    before_assignments = metric_value(before, "parking_assignment_scheduler_assignments_produced_total")

    runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(),
        session_factory=FakeSession,
        assignment_batch_runner=lambda db, *, limit: summary(assigned=2),
        lock_factory=lambda db, lock_key: FakeLock(acquired=True),
        run_id_provider=lambda: "metric-success",
        monotonic_provider=iter([10.0, 10.5]).__next__,
    )

    result = runner.run_cycle()
    output = current_metrics_output()

    assert result.summary is not None
    assert metric_value(
        output,
        "parking_assignment_scheduler_cycles_total",
        {"result": "success"},
    ) == before_success + 1
    assert metric_value(output, "parking_assignment_scheduler_assignments_produced_total") == before_assignments + 2
    assert metric_value(output, "parking_assignment_scheduler_last_success_timestamp_seconds") > 0
    assert metric_value(output, "parking_assignment_scheduler_running_cycles") == 0


def test_scheduler_error_and_lock_skip_metrics_increment() -> None:
    before = current_metrics_output()
    before_error = metric_value(
        before,
        "parking_assignment_scheduler_cycles_total",
        {"result": "error"},
    )
    before_skip = metric_value(
        before,
        "parking_assignment_scheduler_cycles_total",
        {"result": "lock_skipped"},
    )

    error_runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(),
        session_factory=FakeSession,
        assignment_batch_runner=lambda db, *, limit: (_ for _ in ()).throw(RuntimeError("failed")),
        lock_factory=lambda db, lock_key: FakeLock(acquired=True),
    )
    skip_runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(),
        session_factory=FakeSession,
        assignment_batch_runner=lambda db, *, limit: summary(),
        lock_factory=lambda db, lock_key: FakeLock(acquired=False),
    )

    assert error_runner.run_cycle().error_type == "RuntimeError"
    assert skip_runner.run_cycle().lock_acquired is False
    output = current_metrics_output()

    assert metric_value(
        output,
        "parking_assignment_scheduler_cycles_total",
        {"result": "error"},
    ) == before_error + 1
    assert metric_value(
        output,
        "parking_assignment_scheduler_cycles_total",
        {"result": "lock_skipped"},
    ) == before_skip + 1
    assert metric_value(output, "parking_assignment_scheduler_running_cycles") == 0


def test_scheduler_metrics_failure_does_not_break_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import assignment_scheduler_runner

    def fail_metric() -> None:
        raise RuntimeError("metrics backend failed")

    monkeypatch.setattr(
        assignment_scheduler_runner.metrics,
        "mark_scheduler_cycle_started",
        fail_metric,
    )
    runner = AssignmentSchedulerRunner(
        settings=scheduler_settings(),
        session_factory=FakeSession,
        assignment_batch_runner=lambda db, *, limit: summary(),
        lock_factory=lambda db, lock_key: FakeLock(acquired=True),
    )

    result = runner.run_cycle()

    assert result.summary is not None

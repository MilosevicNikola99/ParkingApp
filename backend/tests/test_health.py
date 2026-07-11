from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import create_app


def test_health_endpoint_returns_application_status() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Parking Management API",
        "environment": "local",
    }


def test_liveness_endpoint_does_not_depend_on_database(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.routers import health as health_router

    monkeypatch.setattr(
        health_router,
        "run_database_ping_with_timeout",
        lambda timeout_seconds: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    client = TestClient(create_app())

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_endpoint_returns_ready_when_database_ping_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.routers import health as health_router

    observed_timeouts: list[float] = []

    def ping(timeout_seconds: float) -> None:
        observed_timeouts.append(timeout_seconds)

    monkeypatch.setattr(health_router, "run_database_ping_with_timeout", ping)
    app = create_app(Settings(_env_file=None, readiness_database_timeout_seconds=0.25))
    client = TestClient(app)

    response = client.get("/health/ready", headers={"X-Request-ID": "ready-request"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "ready-request"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.json() == {
        "status": "ready",
        "service": "Parking Management API",
        "environment": "local",
        "checks": {"database": {"status": "ok"}},
    }
    assert observed_timeouts == [0.25]


def test_readiness_endpoint_returns_503_without_sensitive_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.routers import health as health_router

    def fail_ping(timeout_seconds: float) -> None:
        raise RuntimeError("password=secret database_url=postgresql://unsafe")

    monkeypatch.setattr(health_router, "run_database_ping_with_timeout", fail_ping)
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.json() == {
        "status": "not_ready",
        "service": "Parking Management API",
        "environment": "local",
        "checks": {"database": {"status": "error"}},
    }
    assert "secret" not in response.text
    assert "database_url" not in response.text
    assert "postgresql://" not in response.text

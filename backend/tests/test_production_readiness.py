import logging
from collections.abc import Generator
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.core.logging import JsonLogFormatter, TextLogFormatter, configure_logging
from app.main import create_app


class LogRecordCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture()
def production_readiness_app() -> FastAPI:
    app = create_app()

    @app.get("/test/http-error")
    def raise_http_error() -> None:
        raise HTTPException(status_code=418, detail="Expected test error")

    @app.get("/test/unhandled-error")
    def raise_unhandled_error() -> None:
        raise RuntimeError("sensitive internal failure")

    @app.get("/test/validation/{value}")
    def validate_integer(value: int) -> dict[str, int]:
        return {"value": value}

    @app.post("/test/log-safety")
    def accept_sensitive_input(payload: dict[str, str]) -> dict[str, bool]:
        return {"accepted": bool(payload)}

    return app


@pytest.fixture()
def client(production_readiness_app: FastAPI) -> TestClient:
    return TestClient(production_readiness_app, raise_server_exceptions=False)


@pytest.fixture()
def http_log_records() -> Generator[list[logging.LogRecord], None, None]:
    http_logger = logging.getLogger("app.http")
    original_level = http_logger.level
    original_disabled = http_logger.disabled
    collector = LogRecordCollector()
    http_logger.setLevel(logging.INFO)
    http_logger.disabled = False
    http_logger.addHandler(collector)

    yield collector.records

    http_logger.removeHandler(collector)
    http_logger.setLevel(original_level)
    http_logger.disabled = original_disabled


def test_request_id_is_preserved_when_valid(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "client-request-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "client-request-123"


def test_request_id_is_generated_when_missing(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert UUID(response.headers["X-Request-ID"])


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "unsafe request id\r\n"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "unsafe request id\r\n"
    assert UUID(response.headers["X-Request-ID"])


def test_security_headers_are_present(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_configured_cors_origin_receives_expected_headers() -> None:
    app = create_app(
        Settings(
            cors_allowed_origins=["https://parking.example.com"],
            cors_allow_credentials=True,
        ),
    )
    client = TestClient(app)

    response = client.get("/health", headers={"Origin": "https://parking.example.com"})

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "https://parking.example.com"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    assert "X-Request-ID" in response.headers["Access-Control-Expose-Headers"]
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_allowed_cors_preflight_receives_expected_headers() -> None:
    app = create_app(
        Settings(
            cors_allowed_origins=["https://parking.example.com"],
            cors_allow_credentials=True,
        ),
    )
    client = TestClient(app)

    response = client.options(
        "/auth/me",
        headers={
            "Origin": "https://parking.example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization, X-Request-ID",
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "https://parking.example.com"
    assert response.headers["Access-Control-Allow-Credentials"] == "true"
    assert "GET" in response.headers["Access-Control-Allow-Methods"]
    assert "authorization" in response.headers["Access-Control-Allow-Headers"].lower()
    assert "x-request-id" in response.headers["Access-Control-Allow-Headers"].lower()
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_unconfigured_cors_origin_is_not_allowed() -> None:
    app = create_app(
        Settings(
            cors_allowed_origins=["https://parking.example.com"],
            cors_allow_credentials=True,
        ),
    )
    client = TestClient(app)

    response = client.get("/health", headers={"Origin": "https://untrusted.example.com"})
    preflight_response = client.options(
        "/auth/me",
        headers={
            "Origin": "https://untrusted.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers
    assert preflight_response.status_code == 400
    assert "Access-Control-Allow-Origin" not in preflight_response.headers
    assert preflight_response.headers["X-Request-ID"]


def test_cors_credentials_header_follows_configuration() -> None:
    app = create_app(
        Settings(
            cors_allowed_origins=["https://parking.example.com"],
            cors_allow_credentials=False,
        ),
    )
    client = TestClient(app)

    response = client.options(
        "/auth/me",
        headers={
            "Origin": "https://parking.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "https://parking.example.com"
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_unhandled_exception_returns_generic_500_with_request_id(client: TestClient) -> None:
    response = client.get("/test/unhandled-error", headers={"X-Request-ID": "failed-request-123"})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "failed-request-123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.json() == {
        "detail": "Internal server error",
        "request_id": "failed-request-123",
        "error_code": "internal_server_error",
    }
    assert "RuntimeError" not in response.text
    assert "sensitive internal failure" not in response.text


def test_http_exception_status_and_existing_body_are_preserved(client: TestClient) -> None:
    response = client.get("/test/http-error")

    assert response.status_code == 418
    assert response.json() == {"detail": "Expected test error"}
    assert response.headers["X-Request-ID"]


def test_validation_error_remains_clear_and_preserves_existing_body(client: TestClient) -> None:
    response = client.get("/test/validation/not-an-integer")

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert response.headers["X-Request-ID"]


def test_request_logging_excludes_headers_query_values_and_body(
    client: TestClient,
    http_log_records: list[logging.LogRecord],
) -> None:
    response = client.post(
        "/test/log-safety?token=sensitive-query-value",
        headers={
            "Authorization": "Bearer sensitive-access-token",
            "X-Request-ID": "safe-log-request",
        },
        json={"password": "sensitive-body-value"},
    )

    assert response.status_code == 200
    http_records = [record for record in http_log_records if record.name == "app.http"]
    assert len(http_records) == 1
    record = http_records[0]
    assert record.getMessage() == "http_request_completed"
    assert record.request_id == "safe-log-request"
    assert record.method == "POST"
    assert record.path == "/test/log-safety"
    assert record.status_code == 200
    assert record.duration_ms >= 0

    logged_text = " ".join(
        f"{record.getMessage()} {record.__dict__}" for record in http_records
    )
    assert "Authorization" not in logged_text
    assert "sensitive-access-token" not in logged_text
    assert "sensitive-query-value" not in logged_text
    assert "sensitive-body-value" not in logged_text
    assert "password" not in logged_text


def test_unmatched_path_value_is_not_logged(
    client: TestClient,
    http_log_records: list[logging.LogRecord],
) -> None:
    response = client.get("/not-found/sensitive-path-value")

    assert response.status_code == 404
    http_records = [record for record in http_log_records if record.name == "app.http"]
    assert len(http_records) == 1
    assert http_records[0].path == "<unmatched>"
    assert "sensitive-path-value" not in str(http_records[0].__dict__)


def test_unhandled_exception_log_includes_request_id(
    client: TestClient,
    http_log_records: list[logging.LogRecord],
) -> None:
    response = client.get("/test/unhandled-error", headers={"X-Request-ID": "error-log-request"})

    assert response.status_code == 500
    error_records = [
        record
        for record in http_log_records
        if record.name == "app.http" and record.getMessage() == "http_request_failed"
    ]
    assert len(error_records) == 1
    assert error_records[0].request_id == "error-log-request"
    assert error_records[0].status_code == 500
    assert error_records[0].error_code == "internal_server_error"


def test_json_formatter_omits_exception_message() -> None:
    try:
        raise RuntimeError("sensitive exception value")
    except RuntimeError as exception:
        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="safe_event",
            args=(),
            exc_info=(type(exception), exception, exception.__traceback__),
        )

    formatted = JsonLogFormatter().format(record)

    assert "RuntimeError" in formatted
    assert "exception_stack" in formatted
    assert "sensitive exception value" not in formatted


def test_logging_configuration_can_switch_between_json_and_text() -> None:
    root_logger = logging.getLogger()

    configure_logging(log_level="DEBUG", log_json=False)
    handler = next(
        handler
        for handler in root_logger.handlers
        if getattr(handler, "_parking_app_logging_handler", False)
    )

    assert root_logger.level == logging.DEBUG
    assert handler.level == logging.DEBUG
    assert isinstance(handler.formatter, TextLogFormatter)

    configure_logging(log_level="INFO", log_json=True)

    assert root_logger.level == logging.INFO
    assert handler.level == logging.INFO
    assert isinstance(handler.formatter, JsonLogFormatter)

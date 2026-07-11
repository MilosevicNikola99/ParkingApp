from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import datetime, timezone
import json
import logging
import traceback
from types import TracebackType
from typing import Any


request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)

_STRUCTURED_FIELDS = (
    "method",
    "path",
    "status_code",
    "duration_ms",
    "error_code",
    "run_id",
    "lock_key",
    "lock_acquired",
    "batch_limit",
    "interval_seconds",
    "processed_count",
    "assigned_count",
    "skipped_count",
    "failed_count",
    "issue_count",
    "error_type",
    "signal",
)
_HANDLER_MARKER = "_parking_app_logging_handler"


def get_request_id() -> str | None:
    return request_id_context.get()


def set_request_id(request_id: str) -> Token[str | None]:
    return request_id_context.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    request_id_context.reset(token)


def format_exception_stack(exception_traceback: TracebackType | None) -> list[dict[str, Any]]:
    if exception_traceback is None:
        return []

    return [
        {
            "file": frame.filename,
            "line": frame.lineno,
            "function": frame.name,
        }
        for frame in traceback.extract_tb(exception_traceback)
    ]


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or get_request_id()
        if request_id:
            payload["request_id"] = request_id

        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            exception_type, _, exception_traceback = record.exc_info
            payload["exception_type"] = exception_type.__name__ if exception_type else "Exception"
            payload["exception_stack"] = format_exception_stack(exception_traceback)

        return json.dumps(payload, ensure_ascii=True)


class TextLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        parts = [
            timestamp,
            record.levelname,
            record.name,
            record.getMessage(),
        ]
        request_id = getattr(record, "request_id", None) or get_request_id()
        if request_id:
            parts.append(f"request_id={request_id}")

        for field in _STRUCTURED_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                parts.append(f"{field}={value}")

        if record.exc_info:
            exception_type, _, exception_traceback = record.exc_info
            parts.append(f"exception_type={exception_type.__name__ if exception_type else 'Exception'}")
            parts.append(f"exception_stack={format_exception_stack(exception_traceback)}")

        return " ".join(parts)


def configure_logging(*, log_level: str = "INFO", log_json: bool = True) -> None:
    level = getattr(logging, log_level.upper())
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    handler = next(
        (
            existing_handler
            for existing_handler in root_logger.handlers
            if getattr(existing_handler, _HANDLER_MARKER, False)
        ),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler()
        setattr(handler, _HANDLER_MARKER, True)
        root_logger.addHandler(handler)

    handler.setLevel(level)
    handler.setFormatter(JsonLogFormatter() if log_json else TextLogFormatter())

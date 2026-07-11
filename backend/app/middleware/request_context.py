from __future__ import annotations

import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.logging import get_request_id, reset_request_id, set_request_id
from app.core import metrics


logger = logging.getLogger("app.http")

REQUEST_ID_HEADER = "X-Request-ID"
INTERNAL_ERROR_CODE = "internal_server_error"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def resolve_request_id(request: Request) -> str:
    incoming_request_id = request.headers.get(REQUEST_ID_HEADER)
    if incoming_request_id and _VALID_REQUEST_ID.fullmatch(incoming_request_id):
        return incoming_request_id
    return str(uuid4())


def apply_response_headers(response: Response, request_id: str) -> None:
    response.headers[REQUEST_ID_HEADER] = request_id
    for header_name, header_value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header_name, header_value)


def build_internal_error_response(request_id: str) -> JSONResponse:
    response = JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
            "error_code": INTERNAL_ERROR_CODE,
        },
    )
    apply_response_headers(response, request_id)
    return response


def request_log_fields(
    request: Request,
    *,
    request_id: str,
    status_code: int,
    duration_ms: float,
) -> dict[str, object]:
    route = request.scope.get("route")
    path = getattr(route, "path", "<unmatched>")
    return {
        "request_id": request_id,
        "method": request.method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
    }


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: object,
        *,
        metrics_enabled: bool = True,
        metrics_path: str = "/metrics",
    ) -> None:
        super().__init__(app)
        self.metrics_enabled = metrics_enabled
        self.metrics_path = metrics_path

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = resolve_request_id(request)
        request.state.request_id = request_id
        context_token = set_request_id(request_id)
        started_at = perf_counter()
        should_record_metrics = self.metrics_enabled and request.url.path != self.metrics_path
        if should_record_metrics:
            metrics.increment_http_in_progress(request.method)

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (perf_counter() - started_at) * 1000
            route = getattr(request.scope.get("route"), "path", "<unmatched>")
            if should_record_metrics:
                metrics.record_unhandled_exception(exception_type="Exception", route=route)
                metrics.record_http_request(
                    method=request.method,
                    route=route,
                    status_code=500,
                    duration_seconds=duration_ms / 1000,
                )
            logger.exception(
                "http_request_failed",
                extra={
                    **request_log_fields(
                        request,
                        request_id=request_id,
                        status_code=500,
                        duration_ms=duration_ms,
                    ),
                    "error_code": INTERNAL_ERROR_CODE,
                },
            )
            return build_internal_error_response(request_id)
        else:
            duration_ms = (perf_counter() - started_at) * 1000
            apply_response_headers(response, request_id)
            if should_record_metrics:
                metrics.record_http_request(
                    method=request.method,
                    route=getattr(request.scope.get("route"), "path", "<unmatched>"),
                    status_code=response.status_code,
                    duration_seconds=duration_ms / 1000,
                )
            logger.info(
                "http_request_completed",
                extra=request_log_fields(
                    request,
                    request_id=request_id,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                ),
            )
            return response
        finally:
            if should_record_metrics:
                metrics.decrement_http_in_progress(request.method)
            reset_request_id(context_token)


async def unhandled_exception_handler(request: Request, exception: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or get_request_id() or str(uuid4())
    metrics.record_unhandled_exception(
        exception_type=type(exception).__name__,
        route=getattr(request.scope.get("route"), "path", "<unmatched>"),
    )
    logger.error(
        "unhandled_exception",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": getattr(request.scope.get("route"), "path", "<unmatched>"),
            "status_code": 500,
            "error_code": INTERNAL_ERROR_CODE,
        },
        exc_info=(type(exception), exception, exception.__traceback__),
    )
    return build_internal_error_response(request_id)

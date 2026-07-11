from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from time import perf_counter

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app.core import metrics
from app.core.config import Settings, get_settings
from app.db.session import engine
from app.schemas.health import DependencyHealth, HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])
logger = logging.getLogger("app.health")


class DatabaseReadinessTimeoutError(RuntimeError):
    pass


@router.get("/health", response_model=HealthResponse)
def health_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return live_check(settings=settings)


@router.get("/health/live", response_model=HealthResponse)
def live_check(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.environment,
    )


def run_database_ping() -> None:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1")).scalar_one()
        if result != 1:
            raise RuntimeError("unexpected database readiness result")


def run_database_ping_with_timeout(timeout_seconds: float) -> None:
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="readiness-db")
    future = executor.submit(run_database_ping)
    try:
        future.result(timeout=timeout_seconds)
    except TimeoutError as exc:
        future.cancel()
        raise DatabaseReadinessTimeoutError("database readiness check timed out") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def build_readiness_response(
    *,
    settings: Settings,
    database_healthy: bool,
) -> ReadinessResponse:
    return ReadinessResponse(
        status="ready" if database_healthy else "not_ready",
        service=settings.app_name,
        environment=settings.environment,
        checks={
            "database": DependencyHealth(status="ok" if database_healthy else "error"),
        },
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
def readiness_check(settings: Settings = Depends(get_settings)) -> ReadinessResponse | JSONResponse:
    started_at = perf_counter()
    database_healthy = False
    try:
        run_database_ping_with_timeout(settings.readiness_database_timeout_seconds)
        database_healthy = True
    except Exception as exc:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.warning(
            "readiness_dependency_failed",
            extra={
                "dependency": "database",
                "duration_ms": duration_ms,
                "error_type": type(exc).__name__,
            },
        )
    finally:
        metrics.set_readiness_dependency_status(
            dependency="database",
            healthy=database_healthy,
        )

    readiness = build_readiness_response(
        settings=settings,
        database_healthy=database_healthy,
    )
    if database_healthy:
        return readiness

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=readiness.model_dump(),
    )


def prometheus_metrics() -> Response:
    return Response(
        content=metrics.render_prometheus_metrics(),
        media_type=metrics.CONTENT_TYPE_LATEST,
    )

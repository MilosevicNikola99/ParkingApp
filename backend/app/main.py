from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.middleware.request_context import RequestContextMiddleware, unhandled_exception_handler
from app.routers.health import prometheus_metrics
from app.routers.admin_assignment_audit_logs import router as admin_assignment_audit_logs_router
from app.routers.admin_parking_applications import router as admin_parking_applications_router
from app.routers.admin_parking_reservations import router as admin_parking_reservations_router
from app.routers.admin_parking_spots import router as admin_parking_spots_router
from app.routers.admin_reservation_overrides import router as admin_reservation_overrides_router
from app.routers.admin_reports import router as admin_reports_router
from app.routers.admin_teams import router as admin_teams_router
from app.routers.admin_users import router as admin_users_router
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
from app.routers.parking_applications import router as parking_applications_router
from app.routers.parking_availabilities import router as parking_availabilities_router
from app.routers.parking_reservations import router as parking_reservations_router
from app.routers.parking_spots import router as parking_spots_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(log_level=settings.log_level, log_json=settings.log_json)

    app = FastAPI(title=settings.app_name)
    app.dependency_overrides[get_settings] = lambda: settings
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(
        RequestContextMiddleware,
        metrics_enabled=settings.metrics_enabled,
        metrics_path=settings.metrics_path,
    )

    app.include_router(admin_assignment_audit_logs_router)
    app.include_router(admin_parking_applications_router)
    app.include_router(admin_parking_reservations_router)
    app.include_router(admin_parking_spots_router)
    app.include_router(admin_reservation_overrides_router)
    app.include_router(admin_reports_router)
    app.include_router(admin_users_router)
    app.include_router(admin_teams_router)
    app.include_router(auth_router)
    app.include_router(parking_availabilities_router)
    app.include_router(parking_applications_router)
    app.include_router(parking_reservations_router)
    app.include_router(parking_spots_router)
    app.include_router(health_router)
    if settings.metrics_enabled:
        app.add_api_route(
            settings.metrics_path,
            prometheus_metrics,
            methods=["GET"],
            include_in_schema=False,
        )

    return app


app = create_app()

from __future__ import annotations

import csv
from datetime import date, datetime
from io import StringIO
from typing import Annotated, Any, Iterable, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_admin
from app.schemas.admin_report import (
    AdminSummaryReport,
    ParkingSpotUsageReportItem,
    TopReservedUserReportItem,
)
from app.services.admin_reports import AdminReportService

router = APIRouter(
    prefix="/admin/reports",
    tags=["admin-reports"],
    dependencies=[Depends(require_admin)],
)


def get_admin_report_service(db: Annotated[Session, Depends(get_db)]) -> AdminReportService:
    return AdminReportService(db)


def validate_date_range(
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
) -> tuple[date | None, date | None]:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from must be before or equal to date_to",
        )
    return date_from, date_to


@router.get("/summary", response_model=AdminSummaryReport)
def get_summary_report(
    service: Annotated[AdminReportService, Depends(get_admin_report_service)],
    date_range: Annotated[tuple[date | None, date | None], Depends(validate_date_range)],
) -> AdminSummaryReport:
    date_from, date_to = date_range
    return service.get_summary(date_from=date_from, date_to=date_to)


@router.get("/top-users", response_model=list[TopReservedUserReportItem])
def get_top_reserved_users(
    service: Annotated[AdminReportService, Depends(get_admin_report_service)],
    date_range: Annotated[tuple[date | None, date | None], Depends(validate_date_range)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[TopReservedUserReportItem]:
    date_from, date_to = date_range
    return service.get_top_reserved_users(limit=limit, date_from=date_from, date_to=date_to)


@router.get("/parking-spot-usage", response_model=list[ParkingSpotUsageReportItem])
def get_parking_spot_usage(
    service: Annotated[AdminReportService, Depends(get_admin_report_service)],
    date_range: Annotated[tuple[date | None, date | None], Depends(validate_date_range)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[ParkingSpotUsageReportItem]:
    date_from, date_to = date_range
    return service.get_parking_spot_usage(limit=limit, date_from=date_from, date_to=date_to)


@router.get("/reservations.csv")
def export_reservations_csv(
    service: Annotated[AdminReportService, Depends(get_admin_report_service)],
    date_range: Annotated[tuple[date | None, date | None], Depends(validate_date_range)],
) -> Response:
    date_from, date_to = date_range
    reservations = service.list_reservations_for_export(date_from=date_from, date_to=date_to)
    return csv_response(
        "parking-reservations.csv",
        (
            "id",
            "availability_id",
            "application_id",
            "parking_spot_id",
            "reserved_for_user_id",
            "start_at",
            "end_at",
            "status",
            "created_at",
            "updated_at",
        ),
        (
            (
                reservation.id,
                reservation.availability_id,
                reservation.application_id,
                reservation.parking_spot_id,
                reservation.reserved_for_user_id,
                reservation.start_at,
                reservation.end_at,
                reservation.status,
                reservation.created_at,
                reservation.updated_at,
            )
            for reservation in reservations
        ),
    )


@router.get("/availabilities.csv")
def export_availabilities_csv(
    service: Annotated[AdminReportService, Depends(get_admin_report_service)],
    date_range: Annotated[tuple[date | None, date | None], Depends(validate_date_range)],
) -> Response:
    date_from, date_to = date_range
    availabilities = service.list_availabilities_for_export(date_from=date_from, date_to=date_to)
    return csv_response(
        "parking-availabilities.csv",
        (
            "id",
            "parking_spot_id",
            "owner_id",
            "start_at",
            "end_at",
            "status",
            "priority_until",
            "note",
            "created_at",
            "updated_at",
        ),
        (
            (
                availability.id,
                availability.parking_spot_id,
                availability.owner_id,
                availability.start_at,
                availability.end_at,
                availability.status,
                availability.priority_until,
                availability.note,
                availability.created_at,
                availability.updated_at,
            )
            for availability in availabilities
        ),
    )


@router.get("/applications.csv")
def export_applications_csv(
    service: Annotated[AdminReportService, Depends(get_admin_report_service)],
    date_range: Annotated[tuple[date | None, date | None], Depends(validate_date_range)],
) -> Response:
    date_from, date_to = date_range
    applications = service.list_applications_for_export(date_from=date_from, date_to=date_to)
    return csv_response(
        "parking-applications.csv",
        ("id", "availability_id", "applicant_id", "status", "note", "created_at", "updated_at"),
        (
            (
                application.id,
                application.availability_id,
                application.applicant_id,
                application.status,
                application.note,
                application.created_at,
                application.updated_at,
            )
            for application in applications
        ),
    )


@router.get("/audit-logs.csv")
def export_audit_logs_csv(
    service: Annotated[AdminReportService, Depends(get_admin_report_service)],
    date_range: Annotated[tuple[date | None, date | None], Depends(validate_date_range)],
) -> Response:
    date_from, date_to = date_range
    audit_logs = service.list_audit_logs_for_export(date_from=date_from, date_to=date_to)
    return csv_response(
        "assignment-audit-logs.csv",
        (
            "id",
            "availability_id",
            "reservation_id",
            "selected_application_id",
            "selected_user_id",
            "trigger_source",
            "ranking_policy",
            "created_at",
        ),
        (
            (
                audit_log.id,
                audit_log.availability_id,
                audit_log.reservation_id,
                audit_log.selected_application_id,
                audit_log.selected_user_id,
                audit_log.trigger_source,
                audit_log.ranking_policy,
                audit_log.created_at,
            )
            for audit_log in audit_logs
        ),
    )


def csv_response(
    filename: str,
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
) -> Response:
    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([csv_value(value) for value in row])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    normalized_value = getattr(value, "value", value)
    if isinstance(normalized_value, str) and normalized_value.startswith(("=", "+", "-", "@")):
        return f"'{normalized_value}"
    return normalized_value

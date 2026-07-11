from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import Select, String, cast, exists, func, select
from sqlalchemy.orm import Session

from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog, ParkingAssignmentTriggerSource
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.schemas.admin_report import (
    AdminSummaryReport,
    ApplicationSummaryReport,
    AuditTriggerSummaryItem,
    AvailabilitySummaryReport,
    ParkingSpotUsageReportItem,
    ReservationSummaryReport,
    TopReservedUserReportItem,
)


class AdminReportService:
    """Read-only operational reporting queries.

    Date filters apply to each record's created_at timestamp. date_from and
    date_to are inclusive UTC calendar dates.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_summary(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> AdminSummaryReport:
        reservation_counts = self._status_counts(
            ParkingReservation,
            ParkingReservation.status,
            ParkingReservation.created_at,
            date_from=date_from,
            date_to=date_to,
        )
        availability_counts = self._status_counts(
            ParkingAvailability,
            ParkingAvailability.status,
            ParkingAvailability.created_at,
            date_from=date_from,
            date_to=date_to,
        )
        application_counts = self._status_counts(
            ParkingApplication,
            ParkingApplication.status,
            ParkingApplication.created_at,
            date_from=date_from,
            date_to=date_to,
        )

        return AdminSummaryReport(
            reservation_summary=ReservationSummaryReport(
                total=sum(reservation_counts.values()),
                active=reservation_counts.get(ParkingReservationStatus.ACTIVE.value, 0),
                cancelled=reservation_counts.get(ParkingReservationStatus.CANCELLED.value, 0),
                completed=reservation_counts.get(ParkingReservationStatus.COMPLETED.value, 0),
            ),
            availability_summary=AvailabilitySummaryReport(
                total=sum(availability_counts.values()),
                open=availability_counts.get(ParkingAvailabilityStatus.OPEN.value, 0),
                assigned=availability_counts.get(ParkingAvailabilityStatus.ASSIGNED.value, 0),
                cancelled=availability_counts.get(ParkingAvailabilityStatus.CANCELLED.value, 0),
                expired=availability_counts.get(ParkingAvailabilityStatus.EXPIRED.value, 0),
                open_without_reservation=self._count_open_without_reservation(
                    date_from=date_from,
                    date_to=date_to,
                ),
            ),
            application_summary=ApplicationSummaryReport(
                total=sum(application_counts.values()),
                pending=application_counts.get(ParkingApplicationStatus.PENDING.value, 0),
                selected=application_counts.get(ParkingApplicationStatus.SELECTED.value, 0),
                rejected=application_counts.get(ParkingApplicationStatus.REJECTED.value, 0),
                cancelled=application_counts.get(ParkingApplicationStatus.CANCELLED.value, 0),
            ),
            audit_trigger_summary=self.get_audit_trigger_summary(
                date_from=date_from,
                date_to=date_to,
            ),
        )

    def get_top_reserved_users(
        self,
        *,
        limit: int = 10,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[TopReservedUserReportItem]:
        count_label = func.count(ParkingReservation.id).label("reservation_count")
        statement = (
            select(ParkingReservation.reserved_for_user_id, count_label)
            .where(
                ParkingReservation.status.in_(
                    (ParkingReservationStatus.ACTIVE, ParkingReservationStatus.COMPLETED),
                ),
            )
            .group_by(ParkingReservation.reserved_for_user_id)
            .order_by(count_label.desc(), ParkingReservation.reserved_for_user_id)
            .limit(limit)
        )
        statement = self._apply_date_filters(
            statement,
            ParkingReservation.created_at,
            date_from=date_from,
            date_to=date_to,
        )
        return [
            TopReservedUserReportItem(user_id=user_id, reservation_count=count)
            for user_id, count in self.db.execute(statement).all()
        ]

    def get_parking_spot_usage(
        self,
        *,
        limit: int = 10,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ParkingSpotUsageReportItem]:
        count_label = func.count(ParkingReservation.id).label("reservation_count")
        statement = (
            select(ParkingReservation.parking_spot_id, count_label)
            .where(
                ParkingReservation.status.in_(
                    (ParkingReservationStatus.ACTIVE, ParkingReservationStatus.COMPLETED),
                ),
            )
            .group_by(ParkingReservation.parking_spot_id)
            .order_by(count_label.desc(), ParkingReservation.parking_spot_id)
            .limit(limit)
        )
        statement = self._apply_date_filters(
            statement,
            ParkingReservation.created_at,
            date_from=date_from,
            date_to=date_to,
        )
        return [
            ParkingSpotUsageReportItem(parking_spot_id=parking_spot_id, reservation_count=count)
            for parking_spot_id, count in self.db.execute(statement).all()
        ]

    def get_audit_trigger_summary(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[AuditTriggerSummaryItem]:
        count_label = func.count(ParkingAssignmentAuditLog.id).label("trigger_count")
        statement = (
            select(ParkingAssignmentAuditLog.trigger_source, count_label)
            .group_by(ParkingAssignmentAuditLog.trigger_source)
            .order_by(
                count_label.desc(),
                cast(ParkingAssignmentAuditLog.trigger_source, String),
            )
        )
        statement = self._apply_date_filters(
            statement,
            ParkingAssignmentAuditLog.created_at,
            date_from=date_from,
            date_to=date_to,
        )
        return [
            AuditTriggerSummaryItem(trigger_source=trigger_source, count=count)
            for trigger_source, count in self.db.execute(statement).all()
        ]

    def list_reservations_for_export(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ParkingReservation]:
        return self._list_for_export(
            ParkingReservation,
            ParkingReservation.created_at,
            date_from=date_from,
            date_to=date_to,
        )

    def list_availabilities_for_export(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ParkingAvailability]:
        return self._list_for_export(
            ParkingAvailability,
            ParkingAvailability.created_at,
            date_from=date_from,
            date_to=date_to,
        )

    def list_applications_for_export(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ParkingApplication]:
        return self._list_for_export(
            ParkingApplication,
            ParkingApplication.created_at,
            date_from=date_from,
            date_to=date_to,
        )

    def list_audit_logs_for_export(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[ParkingAssignmentAuditLog]:
        return self._list_for_export(
            ParkingAssignmentAuditLog,
            ParkingAssignmentAuditLog.created_at,
            date_from=date_from,
            date_to=date_to,
        )

    def _count_open_without_reservation(
        self,
        *,
        date_from: date | None,
        date_to: date | None,
    ) -> int:
        reservation_exists = exists(
            select(ParkingReservation.id).where(
                ParkingReservation.availability_id == ParkingAvailability.id,
            ),
        )
        statement = (
            select(func.count(ParkingAvailability.id))
            .where(ParkingAvailability.status == ParkingAvailabilityStatus.OPEN)
            .where(~reservation_exists)
        )
        statement = self._apply_date_filters(
            statement,
            ParkingAvailability.created_at,
            date_from=date_from,
            date_to=date_to,
        )
        return int(self.db.execute(statement).scalar_one())

    def _status_counts(
        self,
        model: Any,
        status_column: Any,
        created_at_column: Any,
        *,
        date_from: date | None,
        date_to: date | None,
    ) -> dict[str, int]:
        statement = select(status_column, func.count(model.id)).group_by(status_column)
        statement = self._apply_date_filters(
            statement,
            created_at_column,
            date_from=date_from,
            date_to=date_to,
        )
        return {
            getattr(status_value, "value", status_value): count
            for status_value, count in self.db.execute(statement).all()
        }

    def _list_for_export(
        self,
        model: Any,
        created_at_column: Any,
        *,
        date_from: date | None,
        date_to: date | None,
    ) -> list[Any]:
        statement = select(model).order_by(created_at_column, model.id)
        statement = self._apply_date_filters(
            statement,
            created_at_column,
            date_from=date_from,
            date_to=date_to,
        )
        return list(self.db.execute(statement).scalars().all())

    def _apply_date_filters(
        self,
        statement: Select[Any],
        created_at_column: Any,
        *,
        date_from: date | None,
        date_to: date | None,
    ) -> Select[Any]:
        if date_from is not None:
            statement = statement.where(
                created_at_column >= datetime.combine(date_from, time.min, tzinfo=UTC),
            )
        if date_to is not None:
            statement = statement.where(
                created_at_column <= datetime.combine(date_to, time.max, tzinfo=UTC),
            )
        return statement

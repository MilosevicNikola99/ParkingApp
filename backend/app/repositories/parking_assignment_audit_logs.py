from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog, ParkingAssignmentTriggerSource


class ParkingAssignmentAuditLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        availability_id: int,
        reservation_id: int,
        selected_application_id: int,
        selected_user_id: int,
        rejected_application_ids: Sequence[int],
        ranking_policy: str,
        ranking_details: Sequence[dict[str, Any]],
        trigger_source: ParkingAssignmentTriggerSource,
    ) -> ParkingAssignmentAuditLog:
        audit_log = ParkingAssignmentAuditLog(
            availability_id=availability_id,
            reservation_id=reservation_id,
            selected_application_id=selected_application_id,
            selected_user_id=selected_user_id,
            rejected_application_ids=list(rejected_application_ids),
            ranking_policy=ranking_policy,
            ranking_details=list(ranking_details),
            trigger_source=trigger_source,
        )
        self.db.add(audit_log)
        self.db.flush()
        self.db.refresh(audit_log)
        return audit_log

    def get_by_id(self, audit_log_id: int) -> ParkingAssignmentAuditLog | None:
        statement = select(ParkingAssignmentAuditLog).where(ParkingAssignmentAuditLog.id == audit_log_id)
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_reservation_id(self, reservation_id: int) -> ParkingAssignmentAuditLog | None:
        statement = (
            select(ParkingAssignmentAuditLog)
            .where(ParkingAssignmentAuditLog.reservation_id == reservation_id)
            .order_by(
                ParkingAssignmentAuditLog.created_at.desc(),
                ParkingAssignmentAuditLog.id.desc(),
            )
            .limit(1)
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_availability_id(self, availability_id: int) -> ParkingAssignmentAuditLog | None:
        statement = (
            select(ParkingAssignmentAuditLog)
            .where(ParkingAssignmentAuditLog.availability_id == availability_id)
            .order_by(
                ParkingAssignmentAuditLog.created_at.desc(),
                ParkingAssignmentAuditLog.id.desc(),
            )
            .limit(1)
        )
        return self.db.execute(statement).scalar_one_or_none()

    def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        availability_id: int | None = None,
        reservation_id: int | None = None,
        selected_user_id: int | None = None,
        selected_application_id: int | None = None,
        trigger_source: ParkingAssignmentTriggerSource | None = None,
        ranking_policy: str | None = None,
    ) -> list[ParkingAssignmentAuditLog]:
        statement = select(ParkingAssignmentAuditLog)
        if availability_id is not None:
            statement = statement.where(ParkingAssignmentAuditLog.availability_id == availability_id)
        if reservation_id is not None:
            statement = statement.where(ParkingAssignmentAuditLog.reservation_id == reservation_id)
        if selected_user_id is not None:
            statement = statement.where(ParkingAssignmentAuditLog.selected_user_id == selected_user_id)
        if selected_application_id is not None:
            statement = statement.where(ParkingAssignmentAuditLog.selected_application_id == selected_application_id)
        if trigger_source is not None:
            statement = statement.where(ParkingAssignmentAuditLog.trigger_source == trigger_source)
        if ranking_policy is not None:
            statement = statement.where(ParkingAssignmentAuditLog.ranking_policy == ranking_policy)

        statement = (
            statement.order_by(
                ParkingAssignmentAuditLog.created_at.desc(),
                ParkingAssignmentAuditLog.id.desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(statement).scalars().all())

    def list_by_selected_user_id(
        self,
        selected_user_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ParkingAssignmentAuditLog]:
        return self.list(
            selected_user_id=selected_user_id,
            skip=skip,
            limit=limit,
        )

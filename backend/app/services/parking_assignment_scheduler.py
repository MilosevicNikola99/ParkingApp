from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.parking_assignment_audit_log import ParkingAssignmentTriggerSource
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.services.parking_reservation_assignment import (
    ParkingReservationAssignmentAvailabilityNotFoundError,
    ParkingReservationAssignmentAvailabilityNotOpenError,
    ParkingReservationAssignmentIntegrityError,
    ParkingReservationAssignmentNoPendingApplicationsError,
    ParkingReservationAssignmentReservationExistsError,
    ParkingReservationAssignmentService,
    ParkingReservationAssignmentServiceError,
)


@dataclass(frozen=True)
class ParkingAssignmentSchedulerIssue:
    availability_id: int
    code: str


@dataclass(frozen=True)
class ParkingAssignmentSchedulerSummary:
    processed_count: int
    assigned_count: int
    skipped_count: int
    failed_count: int
    issues: tuple[ParkingAssignmentSchedulerIssue, ...]


class ParkingAssignmentSchedulerService:
    """Run one deterministic batch of due parking assignments."""

    def __init__(
        self,
        db: Session,
        availability_repository: ParkingAvailabilityRepository,
        assignment_service: ParkingReservationAssignmentService,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self.availability_repository = availability_repository
        self.assignment_service = assignment_service
        self.now_provider = now_provider or (lambda: datetime.now(UTC))

    def assign_due_availabilities(
        self,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> ParkingAssignmentSchedulerSummary:
        if limit < 1:
            raise ValueError("limit must be at least 1")

        resolved_now = self._as_aware_utc(now or self.now_provider())
        due_availabilities = self.availability_repository.list_assignable(now=resolved_now, limit=limit)
        due_availability_ids = [availability.id for availability in due_availabilities]
        assigned_count = 0
        skipped_count = 0
        failed_count = 0
        issues: list[ParkingAssignmentSchedulerIssue] = []

        for availability_id in due_availability_ids:
            try:
                self.assignment_service.assign_availability(
                    availability_id,
                    trigger_source=ParkingAssignmentTriggerSource.SCHEDULED,
                )
                self.db.commit()
                assigned_count += 1
            except self._skipped_errors() as exc:
                self.db.rollback()
                skipped_count += 1
                issues.append(
                    ParkingAssignmentSchedulerIssue(
                        availability_id=availability_id,
                        code=self._issue_code(exc),
                    ),
                )
            except ParkingReservationAssignmentServiceError as exc:
                self.db.rollback()
                failed_count += 1
                issues.append(
                    ParkingAssignmentSchedulerIssue(
                        availability_id=availability_id,
                        code=self._issue_code(exc),
                    ),
                )
            except Exception:
                self.db.rollback()
                failed_count += 1
                issues.append(
                    ParkingAssignmentSchedulerIssue(
                        availability_id=availability_id,
                        code="unexpected_error",
                    ),
                )

        return ParkingAssignmentSchedulerSummary(
            processed_count=len(due_availability_ids),
            assigned_count=assigned_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            issues=tuple(issues),
        )

    def _skipped_errors(self) -> tuple[type[ParkingReservationAssignmentServiceError], ...]:
        return (
            ParkingReservationAssignmentAvailabilityNotFoundError,
            ParkingReservationAssignmentAvailabilityNotOpenError,
            ParkingReservationAssignmentNoPendingApplicationsError,
            ParkingReservationAssignmentReservationExistsError,
        )

    def _issue_code(self, error: ParkingReservationAssignmentServiceError) -> str:
        if isinstance(error, ParkingReservationAssignmentAvailabilityNotFoundError):
            return "availability_not_found"
        if isinstance(error, ParkingReservationAssignmentAvailabilityNotOpenError):
            return "availability_not_open"
        if isinstance(error, ParkingReservationAssignmentNoPendingApplicationsError):
            return "no_pending_applications"
        if isinstance(error, ParkingReservationAssignmentReservationExistsError):
            return "reservation_exists"
        if isinstance(error, ParkingReservationAssignmentIntegrityError):
            return "integrity_conflict"

        return "assignment_error"

    def _as_aware_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.services.parking_assignment_scheduler import (
    ParkingAssignmentSchedulerService,
    ParkingAssignmentSchedulerSummary,
)
from app.services.parking_reservation_assignment import ParkingReservationAssignmentService


def build_scheduler(db: Session) -> ParkingAssignmentSchedulerService:
    availability_repository = ParkingAvailabilityRepository(db)
    return ParkingAssignmentSchedulerService(
        db=db,
        availability_repository=availability_repository,
        assignment_service=ParkingReservationAssignmentService(
            availability_repository=availability_repository,
            application_repository=ParkingApplicationRepository(db),
            reservation_repository=ParkingReservationRepository(db),
        ),
    )


def run_assignment_batch(*, limit: int = 100) -> ParkingAssignmentSchedulerSummary:
    with SessionLocal() as db:
        return build_scheduler(db).assign_due_availabilities(limit=limit)


def format_summary(summary: ParkingAssignmentSchedulerSummary) -> str:
    return (
        f"processed={summary.processed_count} "
        f"assigned={summary.assigned_count} "
        f"skipped={summary.skipped_count} "
        f"failed={summary.failed_count}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assign due parking availabilities.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum due availabilities to process.")
    args = parser.parse_args(argv)

    try:
        summary = run_assignment_batch(limit=args.limit)
    except Exception as exc:
        print(f"fatal assignment command error: {type(exc).__name__}", file=sys.stderr)
        return 1

    print(format_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_admin
from app.models.parking_assignment_audit_log import ParkingAssignmentAuditLog, ParkingAssignmentTriggerSource
from app.models.user import User
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.schemas.parking_assignment_audit_log import ParkingAssignmentAuditLogRead

router = APIRouter(
    prefix="/admin/assignment-audit-logs",
    tags=["admin-assignment-audit-logs"],
)


def get_assignment_audit_log_repository(
    db: Annotated[Session, Depends(get_db)],
) -> ParkingAssignmentAuditLogRepository:
    return ParkingAssignmentAuditLogRepository(db)


def assignment_audit_log_not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment audit log not found")


@router.get("", response_model=list[ParkingAssignmentAuditLogRead])
def list_assignment_audit_logs(
    _current_admin: Annotated[User, Depends(require_admin)],
    repository: Annotated[ParkingAssignmentAuditLogRepository, Depends(get_assignment_audit_log_repository)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    availability_id: Annotated[int | None, Query(ge=1)] = None,
    reservation_id: Annotated[int | None, Query(ge=1)] = None,
    selected_user_id: Annotated[int | None, Query(ge=1)] = None,
    selected_application_id: Annotated[int | None, Query(ge=1)] = None,
    trigger_source: ParkingAssignmentTriggerSource | None = None,
    ranking_policy: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
) -> list[ParkingAssignmentAuditLog]:
    return repository.list(
        skip=skip,
        limit=limit,
        availability_id=availability_id,
        reservation_id=reservation_id,
        selected_user_id=selected_user_id,
        selected_application_id=selected_application_id,
        trigger_source=trigger_source,
        ranking_policy=ranking_policy,
    )


@router.get("/by-reservation/{reservation_id}", response_model=ParkingAssignmentAuditLogRead)
def get_assignment_audit_log_by_reservation(
    reservation_id: Annotated[int, Path(ge=1)],
    _current_admin: Annotated[User, Depends(require_admin)],
    repository: Annotated[ParkingAssignmentAuditLogRepository, Depends(get_assignment_audit_log_repository)],
) -> ParkingAssignmentAuditLog:
    audit_log = repository.get_by_reservation_id(reservation_id)
    if audit_log is None:
        raise assignment_audit_log_not_found_exception()

    return audit_log


@router.get("/{audit_log_id}", response_model=ParkingAssignmentAuditLogRead)
def get_assignment_audit_log(
    audit_log_id: Annotated[int, Path(ge=1)],
    _current_admin: Annotated[User, Depends(require_admin)],
    repository: Annotated[ParkingAssignmentAuditLogRepository, Depends(get_assignment_audit_log_repository)],
) -> ParkingAssignmentAuditLog:
    audit_log = repository.get_by_id(audit_log_id)
    if audit_log is None:
        raise assignment_audit_log_not_found_exception()

    return audit_log

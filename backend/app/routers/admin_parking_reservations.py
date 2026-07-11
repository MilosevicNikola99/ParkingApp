from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_admin
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.models.user import User
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.users import UserRepository
from app.schemas.parking_reservation import (
    AdminReservationCancellationRequest,
    ParkingReservationHistoryRead,
    ParkingReservationRead,
)
from app.services.parking_reservation_cancellation import (
    ParkingReservationCancellationAdminReasonRequiredError,
    ParkingReservationCancellationAuditPersistenceError,
    ParkingReservationCancellationIntegrityError,
    ParkingReservationCancellationNotActiveError,
    ParkingReservationCancellationNotFoundError,
    ParkingReservationCancellationPermissionError,
    ParkingReservationCancellationService,
    ParkingReservationCancellationServiceError,
)

router = APIRouter(prefix="/admin/parking-reservations", tags=["admin-parking-reservations"])


def get_parking_reservation_repository(
    db: Annotated[Session, Depends(get_db)],
) -> ParkingReservationRepository:
    return ParkingReservationRepository(db)


def get_parking_reservation_cancellation_service(
    db: Annotated[Session, Depends(get_db)],
) -> ParkingReservationCancellationService:
    return ParkingReservationCancellationService(
        reservation_repository=ParkingReservationRepository(db),
        availability_repository=ParkingAvailabilityRepository(db),
        application_repository=ParkingApplicationRepository(db),
        audit_log_repository=ParkingAssignmentAuditLogRepository(db),
        user_repository=UserRepository(db),
    )


def http_exception_for_cancellation_error(
    error: ParkingReservationCancellationServiceError,
) -> HTTPException:
    if isinstance(error, ParkingReservationCancellationNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking reservation not found")
    if isinstance(error, ParkingReservationCancellationPermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    if isinstance(error, ParkingReservationCancellationNotActiveError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking reservation is not active")
    if isinstance(error, ParkingReservationCancellationAdminReasonRequiredError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cancellation reason is required")
    if isinstance(
        error,
        (
            ParkingReservationCancellationIntegrityError,
            ParkingReservationCancellationAuditPersistenceError,
        ),
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking reservation cancellation conflict")

    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parking reservation cancellation is invalid")


@router.get("", response_model=list[ParkingReservationRead])
def list_parking_reservations(
    _current_admin: Annotated[User, Depends(require_admin)],
    repository: Annotated[ParkingReservationRepository, Depends(get_parking_reservation_repository)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    status_filter: Annotated[ParkingReservationStatus | None, Query(alias="status")] = None,
    reserved_for_user_id: Annotated[int | None, Query(ge=1)] = None,
    parking_spot_id: Annotated[int | None, Query(ge=1)] = None,
) -> list[ParkingReservation]:
    return repository.list(
        skip=skip,
        limit=limit,
        status=status_filter,
        reserved_for_user_id=reserved_for_user_id,
        parking_spot_id=parking_spot_id,
    )


@router.get("/history", response_model=list[ParkingReservationHistoryRead])
def list_parking_reservation_history(
    _current_admin: Annotated[User, Depends(require_admin)],
    repository: Annotated[ParkingReservationRepository, Depends(get_parking_reservation_repository)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    availability_id: Annotated[int | None, Query(ge=1)] = None,
    status_filter: Annotated[ParkingReservationStatus | None, Query(alias="status")] = None,
    current_active: Annotated[bool | None, Query()] = None,
    reserved_for_user_id: Annotated[int | None, Query(ge=1)] = None,
    parking_spot_id: Annotated[int | None, Query(ge=1)] = None,
) -> list[ParkingReservationHistoryRead]:
    reservations = repository.list_history(
        skip=skip,
        limit=limit,
        availability_id=availability_id,
        status=status_filter,
        current_active=current_active,
        reserved_for_user_id=reserved_for_user_id,
        parking_spot_id=parking_spot_id,
    )
    return [ParkingReservationHistoryRead.from_reservation(reservation) for reservation in reservations]


@router.patch("/{reservation_id}/cancel", response_model=ParkingReservationRead)
def cancel_parking_reservation_as_admin(
    reservation_id: Annotated[int, Path(ge=1)],
    cancellation_request: AdminReservationCancellationRequest,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ParkingReservationCancellationService, Depends(get_parking_reservation_cancellation_service)],
) -> ParkingReservation:
    try:
        result = service.cancel_as_admin(
            reservation_id=reservation_id,
            admin_user_id=current_admin.id,
            reason=cancellation_request.reason,
        )
        db.commit()
    except ParkingReservationCancellationServiceError as exc:
        db.rollback()
        raise http_exception_for_cancellation_error(exc) from exc
    except Exception:
        db.rollback()
        raise

    db.refresh(result.reservation)
    return result.reservation

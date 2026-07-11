from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus
from app.models.user import User, UserRole
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.users import UserRepository
from app.schemas.parking_reservation import ParkingReservationRead, ReservationCancellationRequest
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

router = APIRouter(prefix="/parking-reservations", tags=["parking-reservations"])


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


def reservation_not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking reservation not found")


def reservation_permission_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


def http_exception_for_cancellation_error(
    error: ParkingReservationCancellationServiceError,
) -> HTTPException:
    if isinstance(error, ParkingReservationCancellationNotFoundError):
        return reservation_not_found_exception()
    if isinstance(error, ParkingReservationCancellationPermissionError):
        return reservation_permission_exception()
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


def can_view_reservation(reservation: ParkingReservation, current_user: User) -> bool:
    if reservation.reserved_for_user_id == current_user.id:
        return True
    if current_user.role is UserRole.ADMIN:
        return True
    if reservation.availability is not None and reservation.availability.owner_id == current_user.id:
        return True

    return False


@router.get("/my", response_model=list[ParkingReservationRead])
def list_my_parking_reservations(
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[ParkingReservationRepository, Depends(get_parking_reservation_repository)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    status_filter: Annotated[ParkingReservationStatus | None, Query(alias="status")] = None,
) -> list[ParkingReservation]:
    return repository.list_by_reserved_for_user_id(
        current_user.id,
        skip=skip,
        limit=limit,
        status=status_filter,
    )


@router.get("/{reservation_id}", response_model=ParkingReservationRead)
def get_parking_reservation(
    reservation_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    repository: Annotated[ParkingReservationRepository, Depends(get_parking_reservation_repository)],
) -> ParkingReservation:
    reservation = repository.get_by_id(reservation_id)
    if reservation is None:
        raise reservation_not_found_exception()
    if not can_view_reservation(reservation, current_user):
        raise reservation_permission_exception()

    return reservation


@router.patch("/{reservation_id}/cancel", response_model=ParkingReservationRead)
def cancel_parking_reservation(
    reservation_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ParkingReservationCancellationService, Depends(get_parking_reservation_cancellation_service)],
    cancellation_request: ReservationCancellationRequest | None = None,
) -> ParkingReservation:
    try:
        result = service.cancel_for_user_or_owner(
            reservation_id=reservation_id,
            actor_user_id=current_user.id,
            reason=cancellation_request.reason if cancellation_request is not None else None,
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

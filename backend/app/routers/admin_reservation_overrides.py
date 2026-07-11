from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_admin
from app.models.parking_reservation import ParkingReservation
from app.models.user import User
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.users import UserRepository
from app.schemas.parking_reservation import AdminReservationOverrideRequest, ParkingReservationRead
from app.schemas.parking_reservation import AdminReservationReplacementRequest
from app.services.admin_reservation_override import (
    AdminReservationOverrideAdminInactiveError,
    AdminReservationOverrideAdminNotFoundError,
    AdminReservationOverrideApplicantInactiveError,
    AdminReservationOverrideApplicantAlreadyReservedError,
    AdminReservationOverrideApplicantNotFoundError,
    AdminReservationOverrideApplicationAlreadyReservedError,
    AdminReservationOverrideApplicationAvailabilityMismatchError,
    AdminReservationOverrideApplicationNotFoundError,
    AdminReservationOverrideApplicationNotPendingError,
    AdminReservationOverrideAuditPersistenceError,
    AdminReservationOverrideAvailabilityNotAssignedError,
    AdminReservationOverrideAvailabilityNotFoundError,
    AdminReservationOverrideAvailabilityNotOpenError,
    AdminReservationOverrideExistingReservationNotActiveError,
    AdminReservationOverrideExistingReservationNotFoundError,
    AdminReservationOverrideIntegrityError,
    AdminReservationOverridePermissionError,
    AdminReservationOverrideReasonRequiredError,
    AdminReservationOverrideReservationExistsError,
    AdminReservationOverrideService,
    AdminReservationOverrideServiceError,
)

router = APIRouter(prefix="/admin/parking-availabilities", tags=["admin-parking-reservation-overrides"])


def get_admin_reservation_override_service(
    db: Annotated[Session, Depends(get_db)],
) -> AdminReservationOverrideService:
    return AdminReservationOverrideService(
        availability_repository=ParkingAvailabilityRepository(db),
        application_repository=ParkingApplicationRepository(db),
        reservation_repository=ParkingReservationRepository(db),
        audit_log_repository=ParkingAssignmentAuditLogRepository(db),
        user_repository=UserRepository(db),
    )


def http_exception_for_override_error(error: AdminReservationOverrideServiceError) -> HTTPException:
    if isinstance(error, AdminReservationOverrideReasonRequiredError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Override reason is required")
    if isinstance(error, AdminReservationOverrideAvailabilityNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking availability not found")
    if isinstance(error, AdminReservationOverrideApplicationNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking application not found")
    if isinstance(error, AdminReservationOverrideApplicantNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking applicant not found")
    if isinstance(error, AdminReservationOverrideAvailabilityNotOpenError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking availability is not open")
    if isinstance(error, AdminReservationOverrideAvailabilityNotAssignedError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking availability is not assigned")
    if isinstance(error, AdminReservationOverrideApplicationAvailabilityMismatchError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Parking application does not belong to availability",
        )
    if isinstance(error, AdminReservationOverrideApplicationAlreadyReservedError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking application is already reserved")
    if isinstance(error, AdminReservationOverrideApplicantAlreadyReservedError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking applicant is already reserved")
    if isinstance(error, AdminReservationOverrideApplicationNotPendingError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking application is not pending")
    if isinstance(error, AdminReservationOverrideApplicantInactiveError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking applicant is inactive")
    if isinstance(error, AdminReservationOverrideReservationExistsError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking reservation already exists")
    if isinstance(error, AdminReservationOverrideExistingReservationNotFoundError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active parking reservation not found")
    if isinstance(error, AdminReservationOverrideExistingReservationNotActiveError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking reservation is not active")
    if isinstance(
        error,
        (
            AdminReservationOverrideIntegrityError,
            AdminReservationOverrideAuditPersistenceError,
        ),
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking reservation override conflict")
    if isinstance(
        error,
        (
            AdminReservationOverrideAdminNotFoundError,
            AdminReservationOverrideAdminInactiveError,
            AdminReservationOverridePermissionError,
        ),
    ):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parking reservation override is invalid")


@router.post(
    "/{availability_id}/override-assign",
    response_model=ParkingReservationRead,
    status_code=status.HTTP_201_CREATED,
)
def override_assign_parking_availability(
    availability_id: Annotated[int, Path(ge=1)],
    override_request: AdminReservationOverrideRequest,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AdminReservationOverrideService, Depends(get_admin_reservation_override_service)],
) -> ParkingReservation:
    try:
        result = service.override_assign_availability(
            availability_id=availability_id,
            application_id=override_request.application_id,
            admin_user_id=current_admin.id,
            reason=override_request.reason,
        )
        db.commit()
    except AdminReservationOverrideServiceError as exc:
        db.rollback()
        raise http_exception_for_override_error(exc) from exc
    except Exception:
        db.rollback()
        raise

    db.refresh(result.reservation)
    return result.reservation


@router.post(
    "/{availability_id}/replace-reservation",
    response_model=ParkingReservationRead,
    status_code=status.HTTP_200_OK,
)
def replace_parking_reservation(
    availability_id: Annotated[int, Path(ge=1)],
    replacement_request: AdminReservationReplacementRequest,
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AdminReservationOverrideService, Depends(get_admin_reservation_override_service)],
) -> ParkingReservation:
    try:
        result = service.replace_existing_reservation(
            availability_id=availability_id,
            application_id=replacement_request.application_id,
            applicant_id=replacement_request.applicant_id,
            admin_user_id=current_admin.id,
            reason=replacement_request.reason,
        )
        db.commit()
    except AdminReservationOverrideServiceError as exc:
        db.rollback()
        raise http_exception_for_override_error(exc) from exc
    except Exception:
        db.rollback()
        raise

    db.refresh(result.reservation)
    return result.reservation

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.parking_availability import ParkingAvailability
from app.models.parking_assignment_audit_log import ParkingAssignmentTriggerSource
from app.models.parking_reservation import ParkingReservation
from app.models.user import User, UserRole
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_assignment_audit_logs import ParkingAssignmentAuditLogRepository
from app.repositories.parking_reservations import ParkingReservationRepository
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.users import UserRepository
from app.schemas.parking_availability import ParkingAvailabilityCreate, ParkingAvailabilityRead
from app.schemas.parking_reservation import ParkingReassignmentRequest, ParkingReservationRead
from app.services.parking_availabilities import (
    InactiveParkingSpotError,
    ParkingAvailabilityNotFoundError,
    ParkingAvailabilityOverlapError,
    ParkingAvailabilityPermissionError,
    ParkingAvailabilityService,
    ParkingAvailabilityServiceError,
    ParkingAvailabilityStatusTransitionError,
    ParkingAvailabilityTimeError,
    ParkingSpotNotFoundError,
)
from app.services.parking_reservation_assignment import (
    ParkingReservationAssignmentAvailabilityNotFoundError,
    ParkingReservationAssignmentAvailabilityNotOpenError,
    ParkingReservationAssignmentAuditPersistenceError,
    ParkingReservationAssignmentIntegrityError,
    ParkingReservationAssignmentNoPendingApplicationsError,
    ParkingReservationAssignmentReservationExistsError,
    ParkingReservationAssignmentService,
    ParkingReservationAssignmentServiceError,
)
from app.services.parking_reassignment import (
    ParkingReassignmentActiveReservationExistsError,
    ParkingReassignmentAuditPersistenceError,
    ParkingReassignmentAvailabilityExpiredError,
    ParkingReassignmentAvailabilityNotFoundError,
    ParkingReassignmentAvailabilityNotOpenError,
    ParkingReassignmentCancelledReservationNotFoundError,
    ParkingReassignmentIntegrityError,
    ParkingReassignmentNoPendingApplicationsError,
    ParkingReassignmentPermissionError,
    ParkingReassignmentService,
    ParkingReassignmentServiceError,
)

router = APIRouter(prefix="/parking-availabilities", tags=["parking-availabilities"])


def get_parking_availability_service(
    db: Annotated[Session, Depends(get_db)],
) -> ParkingAvailabilityService:
    return ParkingAvailabilityService(
        availability_repository=ParkingAvailabilityRepository(db),
        parking_spot_repository=ParkingSpotRepository(db),
    )


def get_parking_reservation_assignment_service(
    db: Annotated[Session, Depends(get_db)],
) -> ParkingReservationAssignmentService:
    return ParkingReservationAssignmentService(
        availability_repository=ParkingAvailabilityRepository(db),
        application_repository=ParkingApplicationRepository(db),
        reservation_repository=ParkingReservationRepository(db),
    )


def get_parking_reassignment_service(
    db: Annotated[Session, Depends(get_db)],
) -> ParkingReassignmentService:
    return ParkingReassignmentService(
        availability_repository=ParkingAvailabilityRepository(db),
        application_repository=ParkingApplicationRepository(db),
        reservation_repository=ParkingReservationRepository(db),
        audit_log_repository=ParkingAssignmentAuditLogRepository(db),
        user_repository=UserRepository(db),
    )


def http_exception_for_service_error(error: ParkingAvailabilityServiceError) -> HTTPException:
    if isinstance(error, ParkingSpotNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking spot not found")
    if isinstance(error, ParkingAvailabilityNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking availability not found")
    if isinstance(error, InactiveParkingSpotError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking spot is inactive")
    if isinstance(error, ParkingAvailabilityPermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    if isinstance(error, ParkingAvailabilityOverlapError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Parking availability overlaps with an existing availability",
        )
    if isinstance(error, ParkingAvailabilityStatusTransitionError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Parking availability cannot be cancelled",
        )
    if isinstance(error, ParkingAvailabilityTimeError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error) or "Parking availability time range is invalid",
        )

    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parking availability request is invalid")


def http_exception_for_assignment_error(error: ParkingReservationAssignmentServiceError) -> HTTPException:
    if isinstance(error, ParkingReservationAssignmentAvailabilityNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking availability not found")
    if isinstance(error, ParkingReservationAssignmentAvailabilityNotOpenError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking availability is not open")
    if isinstance(error, ParkingReservationAssignmentNoPendingApplicationsError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No pending parking applications")
    if isinstance(error, ParkingReservationAssignmentReservationExistsError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking reservation already exists")
    if isinstance(error, ParkingReservationAssignmentIntegrityError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking reservation assignment conflict")
    if isinstance(error, ParkingReservationAssignmentAuditPersistenceError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking assignment audit persistence conflict")

    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parking reservation assignment is invalid")


def http_exception_for_reassignment_error(error: ParkingReassignmentServiceError) -> HTTPException:
    if isinstance(error, ParkingReassignmentAvailabilityNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking availability not found")
    if isinstance(error, ParkingReassignmentPermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    if isinstance(error, ParkingReassignmentAvailabilityNotOpenError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking availability is not open")
    if isinstance(error, ParkingReassignmentAvailabilityExpiredError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking availability has expired")
    if isinstance(error, ParkingReassignmentActiveReservationExistsError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Active parking reservation already exists")
    if isinstance(error, ParkingReassignmentCancelledReservationNotFoundError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cancelled parking reservation not found")
    if isinstance(error, ParkingReassignmentNoPendingApplicationsError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No pending parking applications")
    if isinstance(
        error,
        (
            ParkingReassignmentIntegrityError,
            ParkingReassignmentAuditPersistenceError,
        ),
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking reassignment conflict")

    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parking reassignment is invalid")


def ensure_can_assign_availability(availability: ParkingAvailability, current_user: User) -> None:
    if current_user.role is UserRole.ADMIN:
        return
    if availability.owner_id == current_user.id:
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")


@router.post("", response_model=ParkingAvailabilityRead, status_code=status.HTTP_201_CREATED)
def create_parking_availability(
    availability_create: ParkingAvailabilityCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ParkingAvailabilityService, Depends(get_parking_availability_service)],
) -> ParkingAvailability:
    try:
        availability = service.create_availability(availability_create, current_user)
        db.commit()
    except ParkingAvailabilityServiceError as exc:
        db.rollback()
        raise http_exception_for_service_error(exc) from exc

    db.refresh(availability)
    return availability


@router.post(
    "/{availability_id}/assign",
    response_model=ParkingReservationRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_parking_availability(
    availability_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[
        ParkingReservationAssignmentService,
        Depends(get_parking_reservation_assignment_service),
    ],
) -> ParkingReservation:
    availability = ParkingAvailabilityRepository(db).get_by_id(availability_id)
    if availability is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking availability not found")
    ensure_can_assign_availability(availability, current_user)

    try:
        trigger_source = (
            ParkingAssignmentTriggerSource.MANUAL_ADMIN
            if current_user.role is UserRole.ADMIN
            else ParkingAssignmentTriggerSource.MANUAL_OWNER
        )
        assignment = service.assign_availability(availability_id, trigger_source=trigger_source)
        db.commit()
    except ParkingReservationAssignmentServiceError as exc:
        db.rollback()
        raise http_exception_for_assignment_error(exc) from exc

    db.refresh(assignment.reservation)
    return assignment.reservation


@router.post(
    "/{availability_id}/reassign",
    response_model=ParkingReservationRead,
    status_code=status.HTTP_201_CREATED,
)
def reassign_parking_availability(
    availability_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ParkingReassignmentService, Depends(get_parking_reassignment_service)],
    reassignment_request: ParkingReassignmentRequest | None = None,
) -> ParkingReservation:
    try:
        trigger_source = (
            ParkingAssignmentTriggerSource.MANUAL_ADMIN
            if current_user.role is UserRole.ADMIN
            else ParkingAssignmentTriggerSource.MANUAL_OWNER
        )
        reassignment = service.reassign_open_availability(
            availability_id,
            trigger_source=trigger_source,
            actor_user_id=current_user.id,
            reason=reassignment_request.reason if reassignment_request is not None else None,
        )
        db.commit()
    except ParkingReassignmentServiceError as exc:
        db.rollback()
        raise http_exception_for_reassignment_error(exc) from exc
    except Exception:
        db.rollback()
        raise

    db.refresh(reassignment.reservation)
    return reassignment.reservation


@router.get("", response_model=list[ParkingAvailabilityRead])
def list_open_parking_availabilities(
    _current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ParkingAvailabilityService, Depends(get_parking_availability_service)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    parking_spot_id: Annotated[int | None, Query(ge=1)] = None,
    owner_id: Annotated[int | None, Query(ge=1)] = None,
) -> list[ParkingAvailability]:
    return service.list_open_availabilities(
        skip=skip,
        limit=limit,
        parking_spot_id=parking_spot_id,
        owner_id=owner_id,
    )


@router.get("/my", response_model=list[ParkingAvailabilityRead])
def list_my_parking_availabilities(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ParkingAvailabilityService, Depends(get_parking_availability_service)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[ParkingAvailability]:
    return service.list_my_availabilities(current_user, skip=skip, limit=limit)


@router.get("/{availability_id}", response_model=ParkingAvailabilityRead)
def get_parking_availability(
    availability_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ParkingAvailabilityService, Depends(get_parking_availability_service)],
) -> ParkingAvailability:
    try:
        return service.get_availability_for_user(availability_id, current_user)
    except ParkingAvailabilityServiceError as exc:
        raise http_exception_for_service_error(exc) from exc


@router.patch("/{availability_id}/cancel", response_model=ParkingAvailabilityRead)
def cancel_parking_availability(
    availability_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ParkingAvailabilityService, Depends(get_parking_availability_service)],
) -> ParkingAvailability:
    try:
        availability = service.cancel_availability(availability_id, current_user)
        db.commit()
    except ParkingAvailabilityServiceError as exc:
        db.rollback()
        raise http_exception_for_service_error(exc) from exc

    db.refresh(availability)
    return availability

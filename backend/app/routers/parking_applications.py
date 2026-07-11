from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.user import User
from app.repositories.parking_applications import ParkingApplicationRepository
from app.repositories.parking_availabilities import ParkingAvailabilityRepository
from app.schemas.parking_application import ParkingApplicationCreate, ParkingApplicationRead
from app.services.parking_applications import (
    ParkingApplicationAvailabilityExpiredError,
    ParkingApplicationAvailabilityNotFoundError,
    ParkingApplicationAvailabilityNotOpenError,
    ParkingApplicationDuplicateError,
    ParkingApplicationInactiveApplicantError,
    ParkingApplicationInactiveParkingSpotError,
    ParkingApplicationNotFoundError,
    ParkingApplicationOwnerCannotApplyError,
    ParkingApplicationPermissionError,
    ParkingApplicationService,
    ParkingApplicationServiceError,
    ParkingApplicationStatusTransitionError,
)

router = APIRouter(prefix="/parking-applications", tags=["parking-applications"])


def get_parking_application_service(
    db: Annotated[Session, Depends(get_db)],
) -> ParkingApplicationService:
    return ParkingApplicationService(
        application_repository=ParkingApplicationRepository(db),
        availability_repository=ParkingAvailabilityRepository(db),
    )


def http_exception_for_service_error(error: ParkingApplicationServiceError) -> HTTPException:
    if isinstance(error, ParkingApplicationAvailabilityNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking availability not found")
    if isinstance(error, ParkingApplicationNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking application not found")
    if isinstance(error, ParkingApplicationOwnerCannotApplyError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    if isinstance(error, ParkingApplicationPermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    if isinstance(error, ParkingApplicationInactiveApplicantError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    if isinstance(error, ParkingApplicationAvailabilityNotOpenError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking availability is not open")
    if isinstance(error, ParkingApplicationAvailabilityExpiredError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking availability has expired")
    if isinstance(error, ParkingApplicationInactiveParkingSpotError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking spot is inactive")
    if isinstance(error, ParkingApplicationDuplicateError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking application already exists")
    if isinstance(error, ParkingApplicationStatusTransitionError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking application cannot be cancelled")

    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parking application request is invalid")


def duplicate_application_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Parking application already exists")


@router.post("", response_model=ParkingApplicationRead, status_code=status.HTTP_201_CREATED)
def apply_for_parking_availability(
    application_create: ParkingApplicationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ParkingApplicationService, Depends(get_parking_application_service)],
) -> ParkingApplication:
    try:
        application = service.apply_for_availability(application_create, current_user)
        db.commit()
    except ParkingApplicationServiceError as exc:
        db.rollback()
        raise http_exception_for_service_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise duplicate_application_exception() from exc

    db.refresh(application)
    return application


@router.get("/my", response_model=list[ParkingApplicationRead])
def list_my_parking_applications(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ParkingApplicationService, Depends(get_parking_application_service)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    status_filter: Annotated[ParkingApplicationStatus | None, Query(alias="status")] = None,
) -> list[ParkingApplication]:
    return service.list_my_applications(
        current_user,
        skip=skip,
        limit=limit,
        status=status_filter,
    )


@router.get("/{application_id}", response_model=ParkingApplicationRead)
def get_parking_application(
    application_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ParkingApplicationService, Depends(get_parking_application_service)],
) -> ParkingApplication:
    try:
        return service.get_application_for_user(application_id, current_user)
    except ParkingApplicationServiceError as exc:
        raise http_exception_for_service_error(exc) from exc


@router.patch("/{application_id}/cancel", response_model=ParkingApplicationRead)
def cancel_my_parking_application(
    application_id: Annotated[int, Path(ge=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ParkingApplicationService, Depends(get_parking_application_service)],
) -> ParkingApplication:
    try:
        application = service.cancel_my_application(application_id, current_user)
        db.commit()
    except ParkingApplicationServiceError as exc:
        db.rollback()
        raise http_exception_for_service_error(exc) from exc

    db.refresh(application)
    return application

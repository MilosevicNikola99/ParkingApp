from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_admin
from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.user import User
from app.repositories.parking_applications import ParkingApplicationRepository
from app.schemas.parking_application import ParkingApplicationRead

router = APIRouter(prefix="/admin/parking-applications", tags=["admin-parking-applications"])


def get_parking_application_repository(
    db: Annotated[Session, Depends(get_db)],
) -> ParkingApplicationRepository:
    return ParkingApplicationRepository(db)


@router.get("", response_model=list[ParkingApplicationRead])
def list_parking_applications(
    _current_admin: Annotated[User, Depends(require_admin)],
    repository: Annotated[ParkingApplicationRepository, Depends(get_parking_application_repository)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    availability_id: Annotated[int | None, Query(ge=1)] = None,
    status_filter: Annotated[ParkingApplicationStatus | None, Query(alias="status")] = None,
) -> list[ParkingApplication]:
    return repository.list(
        skip=skip,
        limit=limit,
        availability_id=availability_id,
        status=status_filter,
    )

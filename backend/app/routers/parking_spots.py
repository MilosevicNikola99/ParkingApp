from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.parking_spot import ParkingSpot
from app.models.user import User
from app.repositories.parking_spots import ParkingSpotRepository
from app.schemas.parking_spot import ParkingSpotRead

router = APIRouter(prefix="/parking-spots", tags=["parking-spots"])


@router.get("/mine", response_model=list[ParkingSpotRead])
def list_my_active_parking_spots(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[ParkingSpot]:
    return ParkingSpotRepository(db).list_by_owner_id(
        current_user.id,
        skip=skip,
        limit=limit,
        is_active=True,
    )

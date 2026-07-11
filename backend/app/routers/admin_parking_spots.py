from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies import require_admin
from app.models.parking_spot import ParkingSpot
from app.models.user import User
from app.repositories.parking_spots import ParkingSpotRepository
from app.repositories.users import UserRepository
from app.schemas.parking_spot import ParkingSpotCreate, ParkingSpotRead, ParkingSpotUpdate

router = APIRouter(prefix="/admin/parking-spots", tags=["admin-parking-spots"])


def get_parking_spot_repository(db: Annotated[Session, Depends(get_db)]) -> ParkingSpotRepository:
    return ParkingSpotRepository(db)


def get_user_repository(db: Annotated[Session, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)


def parking_spot_not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parking spot not found")


def owner_not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Owner not found")


def inactive_owner_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner is inactive")


def duplicate_parking_spot_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Parking spot code already exists",
    )


def parking_spot_delete_conflict_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Parking spot cannot be deleted",
    )


def ensure_owner_can_be_assigned(repository: UserRepository, owner_id: int | None) -> None:
    if owner_id is None:
        return

    owner = repository.get_by_id(owner_id)
    if owner is None:
        raise owner_not_found_exception()
    if not owner.is_active:
        raise inactive_owner_exception()


def ensure_parking_spot_code_available(
    repository: ParkingSpotRepository,
    *,
    code: str,
    current_parking_spot_id: int | None = None,
) -> None:
    existing_parking_spot = repository.get_by_code(code)
    if existing_parking_spot is not None and existing_parking_spot.id != current_parking_spot_id:
        raise duplicate_parking_spot_exception()


@router.get("", response_model=list[ParkingSpotRead])
def list_parking_spots(
    _current_admin: Annotated[User, Depends(require_admin)],
    repository: Annotated[ParkingSpotRepository, Depends(get_parking_spot_repository)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    owner_id: Annotated[int | None, Query(ge=1)] = None,
    is_active: bool | None = None,
) -> list[ParkingSpot]:
    return repository.list(skip=skip, limit=limit, owner_id=owner_id, is_active=is_active)


@router.get("/{parking_spot_id}", response_model=ParkingSpotRead)
def get_parking_spot(
    parking_spot_id: int,
    _current_admin: Annotated[User, Depends(require_admin)],
    repository: Annotated[ParkingSpotRepository, Depends(get_parking_spot_repository)],
) -> ParkingSpot:
    parking_spot = repository.get_by_id(parking_spot_id)
    if parking_spot is None:
        raise parking_spot_not_found_exception()

    return parking_spot


@router.post("", response_model=ParkingSpotRead, status_code=status.HTTP_201_CREATED)
def create_parking_spot(
    parking_spot_create: ParkingSpotCreate,
    _current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    parking_spot_repository: Annotated[ParkingSpotRepository, Depends(get_parking_spot_repository)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> ParkingSpot:
    ensure_owner_can_be_assigned(user_repository, parking_spot_create.owner_id)
    ensure_parking_spot_code_available(parking_spot_repository, code=parking_spot_create.code)

    try:
        parking_spot = parking_spot_repository.create(
            code=parking_spot_create.code,
            location=parking_spot_create.location,
            description=parking_spot_create.description,
            owner_id=parking_spot_create.owner_id,
            is_active=parking_spot_create.is_active,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise duplicate_parking_spot_exception() from exc

    db.refresh(parking_spot)
    return parking_spot


@router.patch("/{parking_spot_id}", response_model=ParkingSpotRead)
def update_parking_spot(
    parking_spot_id: int,
    parking_spot_update: ParkingSpotUpdate,
    _current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    parking_spot_repository: Annotated[ParkingSpotRepository, Depends(get_parking_spot_repository)],
    user_repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> ParkingSpot:
    parking_spot = parking_spot_repository.get_by_id(parking_spot_id)
    if parking_spot is None:
        raise parking_spot_not_found_exception()

    updates = parking_spot_update.model_dump(exclude_unset=True)
    if "owner_id" in updates:
        ensure_owner_can_be_assigned(user_repository, updates["owner_id"])
    if "code" in updates:
        ensure_parking_spot_code_available(
            parking_spot_repository,
            code=updates["code"],
            current_parking_spot_id=parking_spot.id,
        )

    if not updates:
        return parking_spot

    try:
        parking_spot = parking_spot_repository.update(parking_spot, updates)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise duplicate_parking_spot_exception() from exc

    db.refresh(parking_spot)
    return parking_spot


@router.delete("/{parking_spot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parking_spot(
    parking_spot_id: int,
    _current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    repository: Annotated[ParkingSpotRepository, Depends(get_parking_spot_repository)],
) -> Response:
    parking_spot = repository.get_by_id(parking_spot_id)
    if parking_spot is None:
        raise parking_spot_not_found_exception()

    try:
        repository.delete(parking_spot)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise parking_spot_delete_conflict_exception() from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)

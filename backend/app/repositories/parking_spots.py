from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.parking_spot import ParkingSpot


class ParkingSpotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        code: str,
        location: str | None = None,
        description: str | None = None,
        owner_id: int | None = None,
        is_active: bool = True,
    ) -> ParkingSpot:
        parking_spot = ParkingSpot(
            code=code,
            location=location,
            description=description,
            owner_id=owner_id,
            is_active=is_active,
        )
        self.db.add(parking_spot)
        self.db.flush()
        self.db.refresh(parking_spot)
        return parking_spot

    def get_by_id(self, parking_spot_id: int) -> ParkingSpot | None:
        statement = (
            select(ParkingSpot)
            .where(ParkingSpot.id == parking_spot_id)
            .options(selectinload(ParkingSpot.owner))
            .execution_options(populate_existing=True)
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_code(self, code: str) -> ParkingSpot | None:
        statement = (
            select(ParkingSpot)
            .where(ParkingSpot.code == code)
            .options(selectinload(ParkingSpot.owner))
        )
        return self.db.execute(statement).scalar_one_or_none()

    def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        owner_id: int | None = None,
        is_active: bool | None = None,
    ) -> list[ParkingSpot]:
        statement = select(ParkingSpot)

        if owner_id is not None:
            statement = statement.where(ParkingSpot.owner_id == owner_id)
        if is_active is not None:
            statement = statement.where(ParkingSpot.is_active.is_(is_active))

        statement = (
            statement.order_by(ParkingSpot.id)
            .offset(skip)
            .limit(limit)
            .options(selectinload(ParkingSpot.owner))
        )
        return list(self.db.execute(statement).scalars().all())

    def list_by_owner_id(
        self,
        owner_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
    ) -> list[ParkingSpot]:
        return self.list(skip=skip, limit=limit, owner_id=owner_id, is_active=is_active)

    def update(self, parking_spot: ParkingSpot, updates: Mapping[str, Any]) -> ParkingSpot:
        allowed_fields = {"code", "location", "description", "owner_id", "is_active"}

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(parking_spot, field, value)

        self.db.flush()
        self.db.refresh(parking_spot)
        return parking_spot

    def delete(self, parking_spot: ParkingSpot) -> bool:
        self.db.delete(parking_spot)
        self.db.flush()
        return True

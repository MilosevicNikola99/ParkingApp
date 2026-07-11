from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from app.models.parking_application import ParkingApplication, ParkingApplicationStatus
from app.models.parking_availability import ParkingAvailability, ParkingAvailabilityStatus
from app.models.parking_reservation import ParkingReservation


class ParkingAvailabilityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        parking_spot_id: int,
        owner_id: int,
        start_at: datetime,
        end_at: datetime,
        status: ParkingAvailabilityStatus = ParkingAvailabilityStatus.OPEN,
        note: str | None = None,
        priority_until: datetime | None = None,
    ) -> ParkingAvailability:
        availability = ParkingAvailability(
            parking_spot_id=parking_spot_id,
            owner_id=owner_id,
            start_at=start_at,
            end_at=end_at,
            status=status,
            note=note,
            priority_until=priority_until,
        )
        self.db.add(availability)
        self.db.flush()
        self.db.refresh(availability)
        return availability

    def get_by_id(self, availability_id: int) -> ParkingAvailability | None:
        return self._get_by_id(availability_id)

    def get_by_id_for_update(self, availability_id: int) -> ParkingAvailability | None:
        return self._get_by_id(availability_id, for_update=True)

    def _get_by_id(
        self,
        availability_id: int,
        *,
        for_update: bool = False,
    ) -> ParkingAvailability | None:
        statement = (
            select(ParkingAvailability)
            .where(ParkingAvailability.id == availability_id)
            .options(
                selectinload(ParkingAvailability.parking_spot),
                selectinload(ParkingAvailability.owner),
            )
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update(of=ParkingAvailability)

        return self.db.execute(statement).scalar_one_or_none()

    def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        status: ParkingAvailabilityStatus | None = None,
        parking_spot_id: int | None = None,
        owner_id: int | None = None,
    ) -> list[ParkingAvailability]:
        statement = select(ParkingAvailability)

        if status is not None:
            statement = statement.where(ParkingAvailability.status == status)
        if parking_spot_id is not None:
            statement = statement.where(ParkingAvailability.parking_spot_id == parking_spot_id)
        if owner_id is not None:
            statement = statement.where(ParkingAvailability.owner_id == owner_id)

        statement = (
            statement.order_by(ParkingAvailability.start_at, ParkingAvailability.id)
            .offset(skip)
            .limit(limit)
            .options(
                selectinload(ParkingAvailability.parking_spot),
                selectinload(ParkingAvailability.owner),
            )
        )
        return list(self.db.execute(statement).scalars().all())

    def list_by_parking_spot_id(
        self,
        parking_spot_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ParkingAvailability]:
        statement = (
            select(ParkingAvailability)
            .where(ParkingAvailability.parking_spot_id == parking_spot_id)
            .order_by(ParkingAvailability.start_at, ParkingAvailability.id)
            .offset(skip)
            .limit(limit)
            .options(
                selectinload(ParkingAvailability.parking_spot),
                selectinload(ParkingAvailability.owner),
            )
        )
        return list(self.db.execute(statement).scalars().all())

    def list_by_owner_id(
        self,
        owner_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ParkingAvailability]:
        statement = (
            select(ParkingAvailability)
            .where(ParkingAvailability.owner_id == owner_id)
            .order_by(ParkingAvailability.start_at, ParkingAvailability.id)
            .offset(skip)
            .limit(limit)
            .options(
                selectinload(ParkingAvailability.parking_spot),
                selectinload(ParkingAvailability.owner),
            )
        )
        return list(self.db.execute(statement).scalars().all())

    def list_open(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        parking_spot_id: int | None = None,
        owner_id: int | None = None,
    ) -> list[ParkingAvailability]:
        return self.list(
            skip=skip,
            limit=limit,
            status=ParkingAvailabilityStatus.OPEN,
            parking_spot_id=parking_spot_id,
            owner_id=owner_id,
        )

    def list_assignable(
        self,
        *,
        now: datetime,
        limit: int = 100,
    ) -> list[ParkingAvailability]:
        pending_application_exists = exists(
            select(ParkingApplication.id)
            .where(ParkingApplication.availability_id == ParkingAvailability.id)
            .where(ParkingApplication.status == ParkingApplicationStatus.PENDING),
        )
        reservation_exists = exists(
            select(ParkingReservation.id).where(
                ParkingReservation.availability_id == ParkingAvailability.id,
            ),
        )
        statement = (
            select(ParkingAvailability)
            .where(ParkingAvailability.status == ParkingAvailabilityStatus.OPEN)
            .where(ParkingAvailability.priority_until.is_not(None))
            .where(ParkingAvailability.priority_until <= now)
            .where(ParkingAvailability.end_at > now)
            .where(pending_application_exists)
            .where(~reservation_exists)
            .order_by(ParkingAvailability.priority_until, ParkingAvailability.id)
            .limit(limit)
            .options(
                selectinload(ParkingAvailability.parking_spot),
                selectinload(ParkingAvailability.owner),
            )
        )
        return list(self.db.execute(statement).scalars().all())

    def list_overlapping_for_spot(
        self,
        *,
        parking_spot_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> list[ParkingAvailability]:
        statement = (
            select(ParkingAvailability)
            .where(ParkingAvailability.parking_spot_id == parking_spot_id)
            .where(ParkingAvailability.start_at < end_at)
            .where(ParkingAvailability.end_at > start_at)
            .order_by(ParkingAvailability.start_at, ParkingAvailability.id)
            .options(
                selectinload(ParkingAvailability.parking_spot),
                selectinload(ParkingAvailability.owner),
            )
        )
        return list(self.db.execute(statement).scalars().all())

    def list_blocking_overlaps_for_spot(
        self,
        *,
        parking_spot_id: int,
        start_at: datetime,
        end_at: datetime,
        blocking_statuses: Sequence[ParkingAvailabilityStatus] = (
            ParkingAvailabilityStatus.OPEN,
            ParkingAvailabilityStatus.ASSIGNED,
        ),
    ) -> list[ParkingAvailability]:
        statement = (
            select(ParkingAvailability)
            .where(ParkingAvailability.parking_spot_id == parking_spot_id)
            .where(ParkingAvailability.status.in_(blocking_statuses))
            .where(ParkingAvailability.start_at < end_at)
            .where(ParkingAvailability.end_at > start_at)
            .order_by(ParkingAvailability.start_at, ParkingAvailability.id)
            .options(
                selectinload(ParkingAvailability.parking_spot),
                selectinload(ParkingAvailability.owner),
            )
        )
        return list(self.db.execute(statement).scalars().all())

    def update(self, availability: ParkingAvailability, updates: Mapping[str, Any]) -> ParkingAvailability:
        allowed_fields = {"start_at", "end_at", "status", "note", "priority_until"}

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(availability, field, value)

        self.db.flush()
        self.db.refresh(availability)
        return availability

    def delete(self, availability: ParkingAvailability) -> bool:
        self.db.delete(availability)
        self.db.flush()
        return True

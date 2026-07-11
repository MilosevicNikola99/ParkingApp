from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.parking_reservation import ParkingReservation, ParkingReservationStatus


class ParkingReservationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        availability_id: int,
        parking_spot_id: int,
        reserved_for_user_id: int,
        start_at: datetime,
        end_at: datetime,
        application_id: int | None = None,
        status: ParkingReservationStatus = ParkingReservationStatus.ACTIVE,
    ) -> ParkingReservation:
        reservation = ParkingReservation(
            availability_id=availability_id,
            application_id=application_id,
            parking_spot_id=parking_spot_id,
            reserved_for_user_id=reserved_for_user_id,
            start_at=start_at,
            end_at=end_at,
            status=status,
        )
        self.db.add(reservation)
        self.db.flush()
        self.db.refresh(reservation)
        return reservation

    def get_by_id(self, reservation_id: int) -> ParkingReservation | None:
        return self._get_by_id(reservation_id)

    def get_by_id_for_update(self, reservation_id: int) -> ParkingReservation | None:
        return self._get_by_id(reservation_id, for_update=True)

    def _get_by_id(
        self,
        reservation_id: int,
        *,
        for_update: bool = False,
    ) -> ParkingReservation | None:
        statement = (
            select(ParkingReservation)
            .where(ParkingReservation.id == reservation_id)
            .options(*self._relationship_loaders())
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update(of=ParkingReservation)

        return self.db.execute(statement).scalar_one_or_none()

    def get_by_availability_id(self, availability_id: int) -> ParkingReservation | None:
        return self._get_latest_by_availability_id(availability_id)

    def get_by_availability_id_for_update(self, availability_id: int) -> ParkingReservation | None:
        return self._get_latest_by_availability_id(availability_id, for_update=True)

    def get_active_by_availability_id(self, availability_id: int) -> ParkingReservation | None:
        return self._get_latest_by_availability_id(
            availability_id,
            status=ParkingReservationStatus.ACTIVE,
        )

    def get_active_by_availability_id_for_update(self, availability_id: int) -> ParkingReservation | None:
        return self._get_latest_by_availability_id(
            availability_id,
            status=ParkingReservationStatus.ACTIVE,
            for_update=True,
        )

    def get_latest_cancelled_by_availability_id(self, availability_id: int) -> ParkingReservation | None:
        return self._get_latest_by_availability_id(
            availability_id,
            status=ParkingReservationStatus.CANCELLED,
        )

    def get_latest_cancelled_by_availability_id_for_update(
        self,
        availability_id: int,
    ) -> ParkingReservation | None:
        return self._get_latest_by_availability_id(
            availability_id,
            status=ParkingReservationStatus.CANCELLED,
            for_update=True,
        )

    def _get_latest_by_availability_id(
        self,
        availability_id: int,
        *,
        status: ParkingReservationStatus | None = None,
        for_update: bool = False,
    ) -> ParkingReservation | None:
        statement = select(ParkingReservation).where(ParkingReservation.availability_id == availability_id)
        if status is not None:
            statement = statement.where(ParkingReservation.status == status)

        statement = (
            statement.order_by(ParkingReservation.created_at.desc(), ParkingReservation.id.desc())
            .limit(1)
            .options(*self._relationship_loaders())
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update(of=ParkingReservation)

        return self.db.execute(statement).scalar_one_or_none()

    def get_by_application_id(self, application_id: int) -> ParkingReservation | None:
        statement = (
            select(ParkingReservation)
            .where(ParkingReservation.application_id == application_id)
            .options(*self._relationship_loaders())
        )
        return self.db.execute(statement).scalar_one_or_none()

    def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        status: ParkingReservationStatus | None = None,
        reserved_for_user_id: int | None = None,
        parking_spot_id: int | None = None,
    ) -> list[ParkingReservation]:
        statement = select(ParkingReservation)

        if status is not None:
            statement = statement.where(ParkingReservation.status == status)
        if reserved_for_user_id is not None:
            statement = statement.where(ParkingReservation.reserved_for_user_id == reserved_for_user_id)
        if parking_spot_id is not None:
            statement = statement.where(ParkingReservation.parking_spot_id == parking_spot_id)

        statement = (
            statement.order_by(ParkingReservation.start_at, ParkingReservation.id)
            .offset(skip)
            .limit(limit)
            .options(*self._relationship_loaders())
        )
        return list(self.db.execute(statement).scalars().all())

    def list_history(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        availability_id: int | None = None,
        status: ParkingReservationStatus | None = None,
        current_active: bool | None = None,
        reserved_for_user_id: int | None = None,
        parking_spot_id: int | None = None,
    ) -> list[ParkingReservation]:
        """List reservation lifecycle history newest first.

        An active reservation is the current reservation for its availability.
        Cancelled and completed reservations are historical records.
        """
        statement = select(ParkingReservation)

        if availability_id is not None:
            statement = statement.where(ParkingReservation.availability_id == availability_id)
        if status is not None:
            statement = statement.where(ParkingReservation.status == status)
        if current_active is True:
            statement = statement.where(ParkingReservation.status == ParkingReservationStatus.ACTIVE)
        elif current_active is False:
            statement = statement.where(ParkingReservation.status != ParkingReservationStatus.ACTIVE)
        if reserved_for_user_id is not None:
            statement = statement.where(ParkingReservation.reserved_for_user_id == reserved_for_user_id)
        if parking_spot_id is not None:
            statement = statement.where(ParkingReservation.parking_spot_id == parking_spot_id)

        statement = (
            statement.order_by(ParkingReservation.created_at.desc(), ParkingReservation.id.desc())
            .offset(skip)
            .limit(limit)
            .options(*self._relationship_loaders())
        )
        return list(self.db.execute(statement).scalars().all())

    def list_by_availability_id(
        self,
        availability_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        status: ParkingReservationStatus | None = None,
    ) -> list[ParkingReservation]:
        statement = select(ParkingReservation).where(ParkingReservation.availability_id == availability_id)
        if status is not None:
            statement = statement.where(ParkingReservation.status == status)

        statement = (
            statement.order_by(ParkingReservation.created_at.desc(), ParkingReservation.id.desc())
            .offset(skip)
            .limit(limit)
            .options(*self._relationship_loaders())
        )
        return list(self.db.execute(statement).scalars().all())

    def list_by_parking_spot_id(
        self,
        parking_spot_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        status: ParkingReservationStatus | None = None,
    ) -> list[ParkingReservation]:
        statement = select(ParkingReservation).where(ParkingReservation.parking_spot_id == parking_spot_id)

        if status is not None:
            statement = statement.where(ParkingReservation.status == status)

        statement = (
            statement.order_by(ParkingReservation.start_at, ParkingReservation.id)
            .offset(skip)
            .limit(limit)
            .options(*self._relationship_loaders())
        )
        return list(self.db.execute(statement).scalars().all())

    def list_by_reserved_for_user_id(
        self,
        reserved_for_user_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        status: ParkingReservationStatus | None = None,
    ) -> list[ParkingReservation]:
        statement = select(ParkingReservation).where(
            ParkingReservation.reserved_for_user_id == reserved_for_user_id,
        )

        if status is not None:
            statement = statement.where(ParkingReservation.status == status)

        statement = (
            statement.order_by(ParkingReservation.start_at, ParkingReservation.id)
            .offset(skip)
            .limit(limit)
            .options(*self._relationship_loaders())
        )
        return list(self.db.execute(statement).scalars().all())

    def list_active_by_user_id(
        self,
        reserved_for_user_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ParkingReservation]:
        return self.list_by_reserved_for_user_id(
            reserved_for_user_id,
            skip=skip,
            limit=limit,
            status=ParkingReservationStatus.ACTIVE,
        )

    def list_active_by_parking_spot_id(
        self,
        parking_spot_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ParkingReservation]:
        return self.list_by_parking_spot_id(
            parking_spot_id,
            skip=skip,
            limit=limit,
            status=ParkingReservationStatus.ACTIVE,
        )

    def count_recent_wins_by_user_ids(
        self,
        user_ids: Sequence[int],
        since: datetime,
    ) -> dict[int, int]:
        unique_user_ids = list(dict.fromkeys(user_ids))
        if not unique_user_ids:
            return {}

        statement = (
            select(
                ParkingReservation.reserved_for_user_id,
                func.count(ParkingReservation.id),
            )
            .where(ParkingReservation.reserved_for_user_id.in_(unique_user_ids))
            .where(
                ParkingReservation.status.in_(
                    (
                        ParkingReservationStatus.ACTIVE,
                        ParkingReservationStatus.COMPLETED,
                    ),
                ),
            )
            .where(ParkingReservation.start_at >= since)
            .group_by(ParkingReservation.reserved_for_user_id)
        )
        counts = {user_id: count for user_id, count in self.db.execute(statement).all()}
        return {user_id: counts.get(user_id, 0) for user_id in unique_user_ids}

    def update(self, reservation: ParkingReservation, updates: Mapping[str, Any]) -> ParkingReservation:
        allowed_fields = {"application_id", "reserved_for_user_id", "status"}

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(reservation, field, value)

        self.db.flush()
        self.db.refresh(reservation)
        return reservation

    def delete(self, reservation: ParkingReservation) -> bool:
        self.db.delete(reservation)
        self.db.flush()
        return True

    def _relationship_loaders(self) -> tuple[Any, ...]:
        return (
            selectinload(ParkingReservation.availability),
            selectinload(ParkingReservation.application),
            selectinload(ParkingReservation.parking_spot),
            selectinload(ParkingReservation.reserved_for_user),
        )

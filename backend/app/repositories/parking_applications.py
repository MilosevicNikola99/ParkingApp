from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.parking_application import ParkingApplication, ParkingApplicationStatus


class ParkingApplicationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        availability_id: int,
        applicant_id: int,
        status: ParkingApplicationStatus = ParkingApplicationStatus.PENDING,
        note: str | None = None,
    ) -> ParkingApplication:
        application = ParkingApplication(
            availability_id=availability_id,
            applicant_id=applicant_id,
            status=status,
            note=note,
        )
        self.db.add(application)
        self.db.flush()
        self.db.refresh(application)
        return application

    def get_by_id(self, application_id: int) -> ParkingApplication | None:
        return self._get_by_id(application_id)

    def get_by_id_for_update(self, application_id: int) -> ParkingApplication | None:
        return self._get_by_id(application_id, for_update=True)

    def _get_by_id(
        self,
        application_id: int,
        *,
        for_update: bool = False,
    ) -> ParkingApplication | None:
        statement = (
            select(ParkingApplication)
            .where(ParkingApplication.id == application_id)
            .options(
                selectinload(ParkingApplication.availability),
                selectinload(ParkingApplication.applicant),
            )
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update(of=ParkingApplication)

        return self.db.execute(statement).scalar_one_or_none()

    def get_by_availability_and_applicant(
        self,
        *,
        availability_id: int,
        applicant_id: int,
    ) -> ParkingApplication | None:
        return self._get_by_availability_and_applicant(
            availability_id=availability_id,
            applicant_id=applicant_id,
        )

    def get_by_availability_and_applicant_for_update(
        self,
        *,
        availability_id: int,
        applicant_id: int,
    ) -> ParkingApplication | None:
        return self._get_by_availability_and_applicant(
            availability_id=availability_id,
            applicant_id=applicant_id,
            for_update=True,
        )

    def _get_by_availability_and_applicant(
        self,
        *,
        availability_id: int,
        applicant_id: int,
        for_update: bool = False,
    ) -> ParkingApplication | None:
        statement = (
            select(ParkingApplication)
            .where(ParkingApplication.availability_id == availability_id)
            .where(ParkingApplication.applicant_id == applicant_id)
            .options(
                selectinload(ParkingApplication.availability),
                selectinload(ParkingApplication.applicant),
            )
        )
        if for_update:
            statement = statement.with_for_update(of=ParkingApplication)

        return self.db.execute(statement).scalar_one_or_none()

    def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        status: ParkingApplicationStatus | None = None,
        availability_id: int | None = None,
    ) -> list[ParkingApplication]:
        statement = select(ParkingApplication)

        if status is not None:
            statement = statement.where(ParkingApplication.status == status)
        if availability_id is not None:
            statement = statement.where(ParkingApplication.availability_id == availability_id)

        statement = (
            statement.order_by(ParkingApplication.id)
            .offset(skip)
            .limit(limit)
            .options(
                selectinload(ParkingApplication.availability),
                selectinload(ParkingApplication.applicant),
            )
        )
        return list(self.db.execute(statement).scalars().all())

    def list_by_availability_id(
        self,
        availability_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ParkingApplication]:
        statement = (
            select(ParkingApplication)
            .where(ParkingApplication.availability_id == availability_id)
            .order_by(ParkingApplication.id)
            .offset(skip)
            .limit(limit)
            .options(
                selectinload(ParkingApplication.availability),
                selectinload(ParkingApplication.applicant),
            )
        )
        return list(self.db.execute(statement).scalars().all())

    def list_by_applicant_id(
        self,
        applicant_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
        status: ParkingApplicationStatus | None = None,
    ) -> list[ParkingApplication]:
        statement = select(ParkingApplication).where(ParkingApplication.applicant_id == applicant_id)

        if status is not None:
            statement = statement.where(ParkingApplication.status == status)

        statement = (
            statement.order_by(ParkingApplication.id)
            .offset(skip)
            .limit(limit)
            .options(
                selectinload(ParkingApplication.availability),
                selectinload(ParkingApplication.applicant),
            )
        )
        return list(self.db.execute(statement).scalars().all())

    def list_pending_by_availability_id(
        self,
        availability_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ParkingApplication]:
        statement = (
            self._pending_by_availability_statement(availability_id)
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(statement).scalars().all())

    def list_pending_by_availability_id_for_update(
        self,
        availability_id: int,
    ) -> list[ParkingApplication]:
        statement = self._pending_by_availability_statement(availability_id).with_for_update(of=ParkingApplication)
        return list(self.db.execute(statement).scalars().all())

    def update(self, application: ParkingApplication, updates: Mapping[str, Any]) -> ParkingApplication:
        allowed_fields = {"status", "note"}

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(application, field, value)

        self.db.flush()
        self.db.refresh(application)
        return application

    def delete(self, application: ParkingApplication) -> bool:
        self.db.delete(application)
        self.db.flush()
        return True

    def _pending_by_availability_statement(self, availability_id: int) -> Any:
        return (
            select(ParkingApplication)
            .where(ParkingApplication.availability_id == availability_id)
            .where(ParkingApplication.status == ParkingApplicationStatus.PENDING)
            .order_by(ParkingApplication.created_at, ParkingApplication.id)
            .options(
                selectinload(ParkingApplication.availability),
                selectinload(ParkingApplication.applicant),
            )
        )

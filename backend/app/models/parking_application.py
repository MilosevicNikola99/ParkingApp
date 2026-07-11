from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SqlEnum, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.parking_availability import ParkingAvailability
    from app.models.parking_reservation import ParkingReservation
    from app.models.user import User


class ParkingApplicationStatus(str, Enum):
    PENDING = "pending"
    SELECTED = "selected"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class ParkingApplication(TimestampMixin, Base):
    __tablename__ = "parking_applications"
    __table_args__ = (
        UniqueConstraint(
            "availability_id",
            "applicant_id",
            name="uq_parking_applications_availability_id_applicant_id",
        ),
        Index("ix_parking_applications_availability_status", "availability_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    availability_id: Mapped[int] = mapped_column(
        ForeignKey("parking_availabilities.id"),
        nullable=False,
        index=True,
    )
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[ParkingApplicationStatus] = mapped_column(
        SqlEnum(
            ParkingApplicationStatus,
            name="parking_application_status",
            values_callable=lambda enum_type: [status.value for status in enum_type],
            validate_strings=True,
        ),
        nullable=False,
        default=ParkingApplicationStatus.PENDING,
        server_default=ParkingApplicationStatus.PENDING.value,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    availability: Mapped["ParkingAvailability"] = relationship(back_populates="applications")
    applicant: Mapped["User"] = relationship(back_populates="parking_applications")
    reservation: Mapped["ParkingReservation | None"] = relationship(
        back_populates="application",
        cascade="save-update, merge",
        uselist=False,
    )

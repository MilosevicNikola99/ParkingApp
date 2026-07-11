from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.parking_application import ParkingApplication
    from app.models.parking_reservation import ParkingReservation
    from app.models.parking_spot import ParkingSpot
    from app.models.user import User


class ParkingAvailabilityStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ParkingAvailability(TimestampMixin, Base):
    __tablename__ = "parking_availabilities"
    __table_args__ = (
        Index("ix_parking_availabilities_status_start_at", "status", "start_at"),
        Index("ix_parking_availabilities_spot_start_end", "parking_spot_id", "start_at", "end_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parking_spot_id: Mapped[int] = mapped_column(ForeignKey("parking_spots.id"), nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[ParkingAvailabilityStatus] = mapped_column(
        SqlEnum(
            ParkingAvailabilityStatus,
            name="parking_availability_status",
            values_callable=lambda enum_type: [status.value for status in enum_type],
            validate_strings=True,
        ),
        nullable=False,
        default=ParkingAvailabilityStatus.OPEN,
        server_default=ParkingAvailabilityStatus.OPEN.value,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    parking_spot: Mapped["ParkingSpot"] = relationship(back_populates="availabilities")
    owner: Mapped["User"] = relationship(back_populates="published_availabilities")
    applications: Mapped[list["ParkingApplication"]] = relationship(
        back_populates="availability",
        cascade="save-update, merge",
    )
    reservations: Mapped[list["ParkingReservation"]] = relationship(
        back_populates="availability",
        cascade="save-update, merge",
    )

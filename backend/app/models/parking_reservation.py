from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.parking_application import ParkingApplication
    from app.models.parking_availability import ParkingAvailability
    from app.models.parking_spot import ParkingSpot
    from app.models.user import User


class ParkingReservationStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class ParkingReservation(TimestampMixin, Base):
    __tablename__ = "parking_reservations"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_parking_reservations_application_id"),
        Index(
            "uq_parking_reservations_active_availability_id",
            "availability_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        Index("ix_parking_reservations_spot_start_end", "parking_spot_id", "start_at", "end_at"),
        Index("ix_parking_reservations_user_status", "reserved_for_user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    availability_id: Mapped[int] = mapped_column(
        ForeignKey("parking_availabilities.id"),
        nullable=False,
        index=True,
    )
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("parking_applications.id"),
        nullable=True,
        index=True,
    )
    parking_spot_id: Mapped[int] = mapped_column(ForeignKey("parking_spots.id"), nullable=False, index=True)
    reserved_for_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[ParkingReservationStatus] = mapped_column(
        SqlEnum(
            ParkingReservationStatus,
            name="parking_reservation_status",
            values_callable=lambda enum_type: [status.value for status in enum_type],
            validate_strings=True,
        ),
        nullable=False,
        default=ParkingReservationStatus.ACTIVE,
        server_default=ParkingReservationStatus.ACTIVE.value,
        index=True,
    )

    availability: Mapped["ParkingAvailability"] = relationship(back_populates="reservations")
    application: Mapped["ParkingApplication | None"] = relationship(back_populates="reservation")
    parking_spot: Mapped["ParkingSpot"] = relationship(back_populates="reservations")
    reserved_for_user: Mapped["User"] = relationship(back_populates="parking_reservations")

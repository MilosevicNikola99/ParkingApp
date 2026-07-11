from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.parking_availability import ParkingAvailability
    from app.models.parking_reservation import ParkingReservation
    from app.models.user import User


class ParkingSpot(TimestampMixin, Base):
    __tablename__ = "parking_spots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    owner: Mapped["User | None"] = relationship(back_populates="owned_parking_spots")
    availabilities: Mapped[list["ParkingAvailability"]] = relationship(
        back_populates="parking_spot",
        cascade="save-update, merge",
    )
    reservations: Mapped[list["ParkingReservation"]] = relationship(
        back_populates="parking_spot",
        cascade="save-update, merge",
    )

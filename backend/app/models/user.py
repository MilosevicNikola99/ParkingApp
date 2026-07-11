from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SqlEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.parking_availability import ParkingAvailability
    from app.models.parking_application import ParkingApplication
    from app.models.parking_reservation import ParkingReservation
    from app.models.parking_spot import ParkingSpot
    from app.models.team import Team


class UserRole(str, Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"
    PARKING_OWNER = "parking_owner"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_type: [role.value for role in enum_type],
            validate_strings=True,
        ),
        nullable=False,
        default=UserRole.EMPLOYEE,
        server_default=UserRole.EMPLOYEE.value,
    )
    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    team: Mapped["Team | None"] = relationship(back_populates="users")
    owned_parking_spots: Mapped[list["ParkingSpot"]] = relationship(
        back_populates="owner",
        cascade="save-update, merge",
    )
    published_availabilities: Mapped[list["ParkingAvailability"]] = relationship(
        back_populates="owner",
        cascade="save-update, merge",
    )
    parking_applications: Mapped[list["ParkingApplication"]] = relationship(
        back_populates="applicant",
        cascade="save-update, merge",
    )
    parking_reservations: Mapped[list["ParkingReservation"]] = relationship(
        back_populates="reserved_for_user",
        cascade="save-update, merge",
    )

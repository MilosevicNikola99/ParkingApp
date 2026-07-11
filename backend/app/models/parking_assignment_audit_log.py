from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ParkingAssignmentTriggerSource(str, Enum):
    SYSTEM = "system"
    MANUAL_OWNER = "manual_owner"
    MANUAL_ADMIN = "manual_admin"
    SCHEDULED = "scheduled"
    ADMIN_OVERRIDE = "admin_override"


class ParkingAssignmentAuditLog(Base):
    __tablename__ = "parking_assignment_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    availability_id: Mapped[int] = mapped_column(
        ForeignKey("parking_availabilities.id"),
        nullable=False,
        index=True,
    )
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("parking_reservations.id"),
        nullable=False,
        index=True,
    )
    selected_application_id: Mapped[int] = mapped_column(
        ForeignKey("parking_applications.id"),
        nullable=False,
        index=True,
    )
    selected_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    rejected_application_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    ranking_policy: Mapped[str] = mapped_column(String(100), nullable=False)
    ranking_details: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    trigger_source: Mapped[ParkingAssignmentTriggerSource] = mapped_column(
        SqlEnum(
            ParkingAssignmentTriggerSource,
            name="parking_assignment_trigger_source",
            values_callable=lambda enum_type: [source.value for source in enum_type],
            validate_strings=True,
        ),
        nullable=False,
        default=ParkingAssignmentTriggerSource.SYSTEM,
        server_default=ParkingAssignmentTriggerSource.SYSTEM.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

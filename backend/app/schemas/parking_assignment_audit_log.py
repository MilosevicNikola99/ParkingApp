from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.parking_assignment_audit_log import ParkingAssignmentTriggerSource


class ParkingAssignmentAuditLogCreate(BaseModel):
    availability_id: int = Field(ge=1)
    reservation_id: int = Field(ge=1)
    selected_application_id: int = Field(ge=1)
    selected_user_id: int = Field(ge=1)
    rejected_application_ids: list[int]
    ranking_policy: str = Field(min_length=1, max_length=100)
    ranking_details: list[dict[str, Any]]
    trigger_source: ParkingAssignmentTriggerSource

    model_config = ConfigDict(extra="forbid")


class ParkingAssignmentAuditLogRead(ParkingAssignmentAuditLogCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")

from pydantic import BaseModel, ConfigDict, Field

from app.models.parking_assignment_audit_log import ParkingAssignmentTriggerSource


class ReservationSummaryReport(BaseModel):
    total: int = Field(ge=0)
    active: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    completed: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class AvailabilitySummaryReport(BaseModel):
    total: int = Field(ge=0)
    open: int = Field(ge=0)
    assigned: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    expired: int = Field(ge=0)
    open_without_reservation: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class ApplicationSummaryReport(BaseModel):
    total: int = Field(ge=0)
    pending: int = Field(ge=0)
    selected: int = Field(ge=0)
    rejected: int = Field(ge=0)
    cancelled: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class AuditTriggerSummaryItem(BaseModel):
    trigger_source: ParkingAssignmentTriggerSource
    count: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class TopReservedUserReportItem(BaseModel):
    user_id: int = Field(ge=1)
    reservation_count: int = Field(ge=1)

    model_config = ConfigDict(extra="forbid")


class ParkingSpotUsageReportItem(BaseModel):
    parking_spot_id: int = Field(ge=1)
    reservation_count: int = Field(ge=1)

    model_config = ConfigDict(extra="forbid")


class AdminSummaryReport(BaseModel):
    reservation_summary: ReservationSummaryReport
    availability_summary: AvailabilitySummaryReport
    application_summary: ApplicationSummaryReport
    audit_trigger_summary: list[AuditTriggerSummaryItem]

    model_config = ConfigDict(extra="forbid")

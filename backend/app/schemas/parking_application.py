from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.parking_application import ParkingApplicationStatus


class ParkingApplicationBase(BaseModel):
    availability_id: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class ParkingApplicationCreate(ParkingApplicationBase):
    pass


class ParkingApplicationUpdate(BaseModel):
    status: ParkingApplicationStatus | None = None
    note: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("status")
    @classmethod
    def status_cannot_be_null(cls, value: ParkingApplicationStatus | None) -> ParkingApplicationStatus | None:
        if value is None:
            raise ValueError("field cannot be null")

        return value


class ParkingApplicationRead(BaseModel):
    id: int
    availability_id: int
    applicant_id: int
    status: ParkingApplicationStatus
    note: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.parking_availability import ParkingAvailabilityStatus
from app.schemas.display import ParkingSpotDisplay, UserDisplay


def is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


class ParkingAvailabilityBase(BaseModel):
    parking_spot_id: int = Field(ge=1)
    start_at: datetime
    end_at: datetime
    note: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("start_at", "end_at")
    @classmethod
    def datetimes_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if not is_timezone_aware(value):
            raise ValueError("datetime must be timezone-aware")

        return value

    @model_validator(mode="after")
    def end_at_must_be_after_start_at(self) -> "ParkingAvailabilityBase":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")

        return self


class ParkingAvailabilityCreate(ParkingAvailabilityBase):
    pass


class ParkingAvailabilityUpdate(BaseModel):
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: ParkingAvailabilityStatus | None = None
    note: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("start_at", "end_at")
    @classmethod
    def optional_datetimes_must_be_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            raise ValueError("field cannot be null")
        if not is_timezone_aware(value):
            raise ValueError("datetime must be timezone-aware")

        return value

    @field_validator("status")
    @classmethod
    def status_cannot_be_null(cls, value: ParkingAvailabilityStatus | None) -> ParkingAvailabilityStatus | None:
        if value is None:
            raise ValueError("field cannot be null")

        return value

    @model_validator(mode="after")
    def end_at_must_be_after_start_at_when_both_are_provided(self) -> "ParkingAvailabilityUpdate":
        if self.start_at is not None and self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")

        return self


class ParkingAvailabilityRead(BaseModel):
    id: int
    parking_spot_id: int
    owner_id: int
    start_at: datetime
    end_at: datetime
    status: ParkingAvailabilityStatus
    note: str | None
    priority_until: datetime | None
    created_at: datetime
    updated_at: datetime
    parking_spot: ParkingSpotDisplay | None = None
    owner: UserDisplay | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")

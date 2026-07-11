from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ParkingSpotBase(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    location: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    owner_id: int | None = Field(default=None, ge=1)
    is_active: bool = True

    model_config = ConfigDict(extra="forbid")


class ParkingSpotCreate(ParkingSpotBase):
    pass


class ParkingSpotUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=80)
    location: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    owner_id: int | None = Field(default=None, ge=1)
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("code", "is_active")
    @classmethod
    def non_nullable_fields_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field cannot be null")

        return value


class ParkingSpotRead(ParkingSpotBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")

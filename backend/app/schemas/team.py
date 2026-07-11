from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TeamBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def name_cannot_be_null(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("name cannot be null")

        return value


class TeamRead(TeamBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")

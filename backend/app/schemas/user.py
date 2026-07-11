from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    role: UserRole = UserRole.EMPLOYEE
    team_id: int | None = None
    is_active: bool = True

    model_config = ConfigDict(extra="forbid")


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    password: str | None = Field(default=None, min_length=8, max_length=72)
    role: UserRole | None = None
    team_id: int | None = None
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("email", "username", "first_name", "last_name", "password", "role", "is_active")
    @classmethod
    def non_nullable_update_fields_cannot_be_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field cannot be null")

        return value


class UserRead(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="forbid")

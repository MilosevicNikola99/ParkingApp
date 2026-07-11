from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    identifier: str = Field(
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("identifier", "email", "username"),
    )
    password: str = Field(min_length=1, max_length=72)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Token(BaseModel):
    access_token: str = Field(min_length=1)
    token_type: str = "bearer"

    model_config = ConfigDict(extra="forbid")


class TokenPayload(BaseModel):
    sub: str = Field(min_length=1)
    role: UserRole
    exp: datetime
    iat: datetime | None = None

    model_config = ConfigDict(extra="ignore")

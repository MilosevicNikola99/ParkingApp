from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.parking_reservation import ParkingReservationStatus
from app.schemas.display import ParkingSpotDisplay, UserDisplay


def is_timezone_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


class ParkingReservationBase(BaseModel):
    availability_id: int = Field(ge=1)
    application_id: int | None = Field(default=None, ge=1)
    parking_spot_id: int = Field(ge=1)
    reserved_for_user_id: int = Field(ge=1)
    start_at: datetime
    end_at: datetime
    status: ParkingReservationStatus = ParkingReservationStatus.ACTIVE

    model_config = ConfigDict(extra="forbid")

    @field_validator("start_at", "end_at")
    @classmethod
    def datetimes_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if not is_timezone_aware(value):
            raise ValueError("datetime must be timezone-aware")

        return value

    @model_validator(mode="after")
    def end_at_must_be_after_start_at(self) -> "ParkingReservationBase":
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")

        return self


class ParkingReservationCreate(ParkingReservationBase):
    pass


class ParkingReservationUpdate(BaseModel):
    status: ParkingReservationStatus | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("status")
    @classmethod
    def status_cannot_be_null(cls, value: ParkingReservationStatus | None) -> ParkingReservationStatus | None:
        if value is None:
            raise ValueError("field cannot be null")

        return value


class AdminReservationOverrideRequest(BaseModel):
    application_id: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("reason must not be blank")

        return normalized_value


class AdminReservationReplacementRequest(BaseModel):
    application_id: int | None = Field(default=None, ge=1)
    applicant_id: int | None = Field(default=None, ge=1)
    reason: str = Field(min_length=1, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("reason must not be blank")

        return normalized_value

    @model_validator(mode="after")
    def exactly_one_replacement_selector_is_required(self) -> "AdminReservationReplacementRequest":
        if (self.application_id is None) == (self.applicant_id is None):
            raise ValueError("provide exactly one of application_id or applicant_id")

        return self


class ReservationCancellationRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def normalize_optional_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None


class AdminReservationCancellationRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_blank(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("reason must not be blank")

        return normalized_value


class ParkingReassignmentRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def normalize_optional_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized_value = value.strip()
        return normalized_value or None


class ParkingReservationRead(BaseModel):
    id: int
    availability_id: int
    application_id: int | None
    parking_spot_id: int
    reserved_for_user_id: int
    start_at: datetime
    end_at: datetime
    status: ParkingReservationStatus
    created_at: datetime
    updated_at: datetime
    parking_spot: ParkingSpotDisplay | None = None
    reserved_for_user: UserDisplay | None = None

    model_config = ConfigDict(from_attributes=True, extra="forbid")


class ParkingReservationHistoryState(str, Enum):
    CURRENT_ACTIVE = "current_active"
    HISTORICAL = "historical"


class ParkingReservationHistoryRead(ParkingReservationRead):
    history_state: ParkingReservationHistoryState

    @classmethod
    def from_reservation(cls, reservation: object) -> "ParkingReservationHistoryRead":
        reservation_read = ParkingReservationRead.model_validate(reservation)
        history_state = (
            ParkingReservationHistoryState.CURRENT_ACTIVE
            if reservation_read.status is ParkingReservationStatus.ACTIVE
            else ParkingReservationHistoryState.HISTORICAL
        )
        return cls(**reservation_read.model_dump(), history_state=history_state)

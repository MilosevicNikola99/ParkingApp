from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class ParkingSpotDisplay(BaseModel):
    id: int
    code: str
    location: str | None

    model_config = ConfigDict(from_attributes=True)


class UserDisplay(BaseModel):
    id: int
    username: str
    email: EmailStr
    first_name: str
    last_name: str
    team_id: int | None

    model_config = ConfigDict(from_attributes=True)


class AvailabilityDisplay(BaseModel):
    id: int
    start_at: datetime
    end_at: datetime
    priority_until: datetime | None
    parking_spot: ParkingSpotDisplay | None = None

    model_config = ConfigDict(from_attributes=True)

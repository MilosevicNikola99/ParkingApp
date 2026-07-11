from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str

    model_config = ConfigDict(extra="forbid")


class DependencyHealth(BaseModel):
    status: str

    model_config = ConfigDict(extra="forbid")


class ReadinessResponse(BaseModel):
    status: str
    service: str
    environment: str
    checks: dict[str, DependencyHealth]

    model_config = ConfigDict(extra="forbid")

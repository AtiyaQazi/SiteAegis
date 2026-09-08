from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IncidentBase(BaseModel):
    event_id: int | None = None
    camera_id: int | None = None
    zone_id: int | None = None

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    incident_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    severity: str = Field(
        default="medium",
        max_length=20,
    )

    risk_score: int = Field(
        default=0,
        ge=0,
        le=100,
    )

    status: str = Field(
        default="open",
        max_length=30,
    )

    resolution_notes: str | None = None


class IncidentCreate(IncidentBase):
    pass


class IncidentUpdate(BaseModel):
    event_id: int | None = None
    camera_id: int | None = None
    zone_id: int | None = None

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    incident_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    severity: str | None = Field(
        default=None,
        max_length=20,
    )

    risk_score: int | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    status: str | None = Field(
        default=None,
        max_length=30,
    )

    resolution_notes: str | None = None


class IncidentResponse(IncidentBase):
    id: int
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
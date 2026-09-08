from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SafetyEventBase(BaseModel):
    camera_id: int | None = None
    zone_id: int | None = None

    event_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    severity: str = Field(
        default="low",
        max_length=20,
    )

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    detected_object: str | None = Field(
        default=None,
        max_length=100,
    )

    risk_score: int = Field(
        default=0,
        ge=0,
        le=100,
    )

    status: str = Field(
        default="active",
        max_length=30,
    )


class SafetyEventCreate(SafetyEventBase):
    pass


class SafetyEventUpdate(BaseModel):
    camera_id: int | None = None
    zone_id: int | None = None

    event_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    severity: str | None = Field(
        default=None,
        max_length=20,
    )

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    detected_object: str | None = Field(
        default=None,
        max_length=100,
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


class SafetyEventResponse(SafetyEventBase):
    id: int
    occurred_at: datetime
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
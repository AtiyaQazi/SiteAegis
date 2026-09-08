from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ZoneBase(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    location: str | None = Field(
        default=None,
        max_length=255,
    )

    risk_level: str = Field(
        default="low",
        max_length=20,
    )


class ZoneCreate(ZoneBase):
    pass


class ZoneUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    location: str | None = Field(
        default=None,
        max_length=255,
    )

    risk_level: str | None = Field(
        default=None,
        max_length=20,
    )


class ZoneResponse(ZoneBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )
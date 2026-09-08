from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SiteCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    url: str = Field(
        ...,
        min_length=4,
        max_length=2048,
    )

    monitoring_interval_minutes: int = Field(
        default=60,
        ge=5,
        le=10080,
    )


class SiteUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    monitoring_enabled: Optional[bool] = None

    monitoring_interval_minutes: Optional[int] = Field(
        default=None,
        ge=5,
        le=10080,
    )


class SiteResponse(BaseModel):
    site_id: str
    name: str
    url: str
    hostname: str

    monitoring_enabled: bool
    monitoring_interval_minutes: int

    last_scan_id: Optional[str] = None
    last_status: Optional[str] = None
    last_risk_score: Optional[int] = None
    last_risk_level: Optional[str] = None

    created_at: datetime
    updated_at: datetime
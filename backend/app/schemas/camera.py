from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CameraBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    description: str | None = None
    source_type: str = Field(default="upload", max_length=30)
    source_url: str | None = Field(default=None, max_length=2048)
    is_active: bool = True


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    description: str | None = None
    source_type: str | None = Field(default=None, max_length=30)
    source_url: str | None = Field(default=None, max_length=2048)
    is_active: bool | None = None
    status: str | None = Field(default=None, max_length=30)


class CameraResponse(CameraBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
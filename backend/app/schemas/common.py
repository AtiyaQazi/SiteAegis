from pydantic import BaseModel, Field
from typing import Optional


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str


class SiteRequest(BaseModel):
    url: str = Field(..., min_length=4, max_length=2048)


class ScanResponse(BaseModel):
    scan_id: str
    url: str
    status: str
    message: Optional[str] = None
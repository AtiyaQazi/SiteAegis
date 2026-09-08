from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class MonitoringEventResponse(BaseModel):
    event_id: str
    site_id: str
    scan_id: str

    event_type: str
    severity: str

    title: str
    description: str

    previous_value: Optional[Any] = None
    current_value: Optional[Any] = None

    created_at: datetime
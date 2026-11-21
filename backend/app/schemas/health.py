from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unreachable"]
    environment: Literal["development", "production"]
    # UTC time on the API server when the check ran.
    checked_at: datetime

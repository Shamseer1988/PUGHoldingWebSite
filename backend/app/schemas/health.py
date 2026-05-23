"""Schemas used by the health-check endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Standard payload returned by the health-check endpoints."""

    status: str = Field(..., examples=["ok"])
    service: str = Field(..., examples=["PUG Holding API"])
    version: str = Field(..., examples=["0.1.0"])
    environment: str = Field(..., examples=["development"])
    database: str = Field(..., examples=["connected", "disconnected"])
    timestamp: datetime

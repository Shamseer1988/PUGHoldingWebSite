"""Pydantic schemas for scheduled report digests (Feature F4)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.hr_ats import (
    SCHEDULED_REPORT_FREQUENCIES,
    SCHEDULED_REPORT_STATUSES,
)


VALID_FREQUENCIES = set(SCHEDULED_REPORT_FREQUENCIES)


class ScheduledReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=2000)
    report_type: str = Field(min_length=1, max_length=64)
    frequency: str = "daily"
    recipients: list[EmailStr] = Field(min_length=1)
    params: Optional[dict] = None
    is_active: bool = True

    @field_validator("frequency")
    @classmethod
    def _freq(cls, v: str) -> str:
        if v not in VALID_FREQUENCIES:
            raise ValueError(
                f"frequency must be one of {sorted(VALID_FREQUENCIES)}"
            )
        return v


class ScheduledReportUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=2000)
    report_type: Optional[str] = Field(default=None, max_length=64)
    frequency: Optional[str] = None
    recipients: Optional[list[EmailStr]] = None
    params: Optional[dict] = None
    is_active: Optional[bool] = None


class ScheduledReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: Optional[int]
    owner_email: Optional[str] = None
    name: str
    description: Optional[str]
    report_type: str
    frequency: str
    recipients: list[str]
    params: Optional[dict]
    is_active: bool
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]
    last_error: Optional[str]
    last_row_count: Optional[int]
    created_at: datetime
    updated_at: datetime


class ScheduledReportRunResult(BaseModel):
    scheduled_report_id: int
    name: str
    recipients: list[str]
    delivered_count: int
    row_count: int
    error: Optional[str] = None

"""Pydantic schemas for interview scorecard templates (Feature F2)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ScorecardDimension(BaseModel):
    """One rubric row inside a scorecard template."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_]+$")
    label: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    max_score: int = Field(ge=1, le=10)
    # Weight in percent. The endpoint validates that all weights sum
    # to 100 across a single template.
    weight: int = Field(ge=0, le=100)


class ScorecardTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=2000)
    scope: str = Field(default="global")
    job_opening_id: Optional[int] = None
    dimensions: List[ScorecardDimension] = Field(default_factory=list)
    is_active: bool = True
    is_default: bool = False

    @field_validator("scope")
    @classmethod
    def _scope_in_set(cls, v: str) -> str:
        if v not in ("global", "job"):
            raise ValueError("scope must be 'global' or 'job'")
        return v


class ScorecardTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=2000)
    scope: Optional[str] = None
    job_opening_id: Optional[int] = None
    dimensions: Optional[List[ScorecardDimension]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class ScorecardTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    scope: str
    job_opening_id: Optional[int]
    job_title: Optional[str] = None
    dimensions: List[ScorecardDimension]
    is_active: bool
    is_default: bool
    created_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class ScorecardEntry(BaseModel):
    """One filled-in dimension when an interviewer submits the form."""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=10)
    notes: Optional[str] = Field(default=None, max_length=2000)


class ScorecardSubmission(BaseModel):
    """Submitting a scorecard against an interview feedback row."""

    model_config = ConfigDict(extra="forbid")

    template_id: int
    # Keys must match the template's dimension keys; the service layer
    # enforces this.
    scores: dict[str, ScorecardEntry]

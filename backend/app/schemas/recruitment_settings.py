"""Schemas for the Super Admin recruitment-workflow settings endpoint."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class RecruitmentSettingsRead(BaseModel):
    """Current recruitment-workflow configuration."""

    job_approval_required: bool


class RecruitmentSettingsUpdate(BaseModel):
    """Partial update — only the fields the Super Admin changed."""

    job_approval_required: Optional[bool] = None

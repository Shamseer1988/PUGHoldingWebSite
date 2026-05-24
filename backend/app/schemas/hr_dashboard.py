"""Pydantic schemas for the HR ATS dashboard (Phase 8)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


class StatItem(BaseModel):
    key: str
    label: str
    value: int


class FunnelStage(BaseModel):
    status: str
    label: str
    count: int


class MonthlyCount(BaseModel):
    month: str  # YYYY-MM
    count: int


class NamedCount(BaseModel):
    name: str
    count: int


class InterviewSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_name: str
    job_title: Optional[str] = None
    round_name: str
    scheduled_at: datetime
    interviewer_name: Optional[str] = None
    mode: str


class OfferSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_name: str
    job_title: Optional[str] = None
    salary_offered: Optional[int] = None
    status: str
    sent_at: Optional[datetime] = None


class DashboardSummary(BaseModel):
    stats: List[StatItem]
    pipeline_funnel: List[FunnelStage]
    applications_per_month: List[MonthlyCount]
    candidates_by_job: List[NamedCount]
    candidates_by_department: List[NamedCount]
    pending_interviews: List[InterviewSummary]
    pending_offers: List[OfferSummary]


class AuditEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    scope: Optional[str] = None
    actor_id: Optional[int] = None
    actor_email: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None

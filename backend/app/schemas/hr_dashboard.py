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


# ---------------------------------------------------------------------------
# Phase C-3 — Recruitment analytics
# ---------------------------------------------------------------------------


class DailyCount(BaseModel):
    """Per-day bucket used by the daily applications time-series."""

    date: str  # ISO YYYY-MM-DD
    count: int


class SourceMetric(BaseModel):
    """Funnel performance per intake source.

    ``shortlisted``, ``offers_issued`` and ``joined`` are cumulative
    (an application that reached "joined" also counts as
    "shortlisted" + "offered") so percentage drop-offs read
    naturally as ``joined / total``.
    """

    source: str
    total: int
    shortlisted: int
    offers_issued: int
    joined: int


class TimeToHireBySource(BaseModel):
    """Average days from application to ``joined``, scoped to a source."""

    source: str
    avg_days: Optional[float] = None
    sample_size: int


class TimeToHireSummary(BaseModel):
    overall_avg_days: Optional[float] = None
    sample_size: int
    by_source: List[TimeToHireBySource]


class RecruitmentAnalytics(BaseModel):
    """Single payload powering the ``/hr/analytics`` page.

    Everything is bounded by ``window_days`` — the page picker lets
    operators look at the last 30 / 60 / 90 days without rebuilding
    the page. The funnel + source breakdown are also windowed so the
    numbers line up with the daily chart.
    """

    window_days: int
    daily_applications: List[DailyCount]
    funnel_conversion: List[FunnelStage]
    source_breakdown: List[SourceMetric]
    time_to_hire: TimeToHireSummary

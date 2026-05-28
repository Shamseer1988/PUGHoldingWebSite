"""HR ATS dashboard endpoints (Phase 8).

Read-only aggregations over the Phase 7 HR tables. The actual job /
candidate / interview / offer CRUD endpoints land in Phases 9-15.

All routes require an HR-scoped bearer token.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_hr_admin, require_permission
from app.auth.permissions import (
    PERM_HR_AUDIT_READ,
    PERM_HR_DASHBOARD_VIEW,
)
from app.core.database import get_db
from app.models.auth import AuditLog, User
from app.models.hr_ats import (
    AI_HIGHLY_RECOMMENDED,
    AI_RECOMMENDED,
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_PENDING,
    INTERVIEW_COMPLETED,
    INTERVIEW_SCHEDULED,
    JOB_STATUS_OPEN,
    OFFER_DRAFT,
    OFFER_PENDING_APPROVAL,
    OFFER_SENT,
    PUBLISH_STATUS_PUBLISHED,
    SOURCE_BULK_UPLOAD,
    SOURCE_MANUAL_UPLOAD,
    SOURCE_PUBLIC_FORM,
    STATUS_AI_REVIEWED,
    STATUS_CV_RECEIVED,
    STATUS_FINAL_INTERVIEW,
    STATUS_FIRST_INTERVIEW,
    STATUS_HR_REVIEW_PENDING,
    STATUS_JOINED,
    STATUS_OFFER_SENT,
    STATUS_REJECTED,
    STATUS_SELECTED,
    STATUS_SHORTLISTED,
    STATUS_TECHNICAL_INTERVIEW,
    Candidate,
    CandidateAIReview,
    CandidateJobApplication,
    Interview,
    InterviewFeedback,
    JobOpening,
    OfferTracking,
)
from app.schemas.hr_dashboard import (
    AuditEntryRead,
    DailyCount,
    DashboardSummary,
    FunnelStage,
    InterviewSummary,
    MonthlyCount,
    NamedCount,
    OfferSummary,
    RecruitmentAnalytics,
    SourceMetric,
    StatItem,
    TimeToHireBySource,
    TimeToHireSummary,
)


router = APIRouter(
    prefix="/hr",
    tags=["HR ATS"],
    dependencies=[Depends(require_hr_admin)],
)


# Stages shown in the pipeline funnel (ordered top-to-bottom).
FUNNEL_STAGES: List[tuple[str, str]] = [
    (STATUS_CV_RECEIVED, "CV received"),
    (STATUS_AI_REVIEWED, "AI reviewed"),
    (STATUS_HR_REVIEW_PENDING, "HR review pending"),
    (STATUS_SHORTLISTED, "Shortlisted"),
    (STATUS_FIRST_INTERVIEW, "First interview"),
    (STATUS_TECHNICAL_INTERVIEW, "Technical interview"),
    (STATUS_FINAL_INTERVIEW, "Final interview"),
    (STATUS_SELECTED, "Selected"),
    (STATUS_OFFER_SENT, "Offer sent"),
    (STATUS_JOINED, "Joined"),
]


@router.get("/dashboard", response_model=DashboardSummary)
def hr_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_DASHBOARD_VIEW)),
) -> DashboardSummary:
    now = datetime.now(timezone.utc)
    month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    def count(stmt) -> int:
        return db.execute(stmt).scalar_one() or 0

    total_candidates = count(
        select(func.count()).select_from(Candidate).where(
            Candidate.is_archived.is_(False)
        )
    )
    applications_total = count(
        select(func.count()).select_from(CandidateJobApplication)
    )
    applications_this_month = count(
        select(func.count())
        .select_from(CandidateJobApplication)
        .where(CandidateJobApplication.applied_at >= month_start)
    )
    ai_reviewed = count(select(func.count()).select_from(CandidateAIReview))
    highly_recommended = count(
        select(func.count())
        .select_from(CandidateAIReview)
        .where(
            CandidateAIReview.recommendation.in_(
                [AI_HIGHLY_RECOMMENDED, AI_RECOMMENDED]
            )
        )
    )
    open_jobs = count(
        select(func.count()).select_from(JobOpening).where(JobOpening.status == JOB_STATUS_OPEN)
    )
    # Phase 10 — master-plan dashboard counters.
    total_jobs = count(
        select(func.count())
        .select_from(JobOpening)
        .where(JobOpening.is_archived.is_(False))
    )
    pending_approval_jobs = count(
        select(func.count())
        .select_from(JobOpening)
        .where(
            JobOpening.approval_status == APPROVAL_STATUS_PENDING,
            JobOpening.is_archived.is_(False),
        )
    )
    live_jobs = count(
        select(func.count())
        .select_from(JobOpening)
        .where(
            JobOpening.status == JOB_STATUS_OPEN,
            JobOpening.approval_status == APPROVAL_STATUS_APPROVED,
            JobOpening.publish_status == PUBLISH_STATUS_PUBLISHED,
            JobOpening.is_archived.is_(False),
        )
    )

    # Status-based counts (use the application as the unit, since pipeline
    # state lives on the application).
    def status_count(status: str) -> int:
        return count(
            select(func.count())
            .select_from(CandidateJobApplication)
            .where(CandidateJobApplication.status == status)
        )

    pending_review = status_count(STATUS_HR_REVIEW_PENDING)
    shortlisted = status_count(STATUS_SHORTLISTED)
    rejected = status_count(STATUS_REJECTED)
    selected = status_count(STATUS_SELECTED)
    joined = status_count(STATUS_JOINED)

    pending_interviews_count = count(
        select(func.count())
        .select_from(Interview)
        .where(
            Interview.status == INTERVIEW_SCHEDULED,
            Interview.scheduled_at >= now,
        )
    )
    # Phase 10 master-plan additions:
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)
    interviews_today = count(
        select(func.count())
        .select_from(Interview)
        .where(
            Interview.scheduled_at >= today_start,
            Interview.scheduled_at < today_end,
            Interview.status == INTERVIEW_SCHEDULED,
        )
    )
    # Pending feedback = completed interviews with no feedback row yet.
    pending_feedback = count(
        select(func.count())
        .select_from(Interview)
        .outerjoin(InterviewFeedback, InterviewFeedback.interview_id == Interview.id)
        .where(
            Interview.status == INTERVIEW_COMPLETED,
            InterviewFeedback.id.is_(None),
        )
    )
    pending_offers_count = count(
        select(func.count())
        .select_from(OfferTracking)
        .where(OfferTracking.status.in_([OFFER_DRAFT, OFFER_SENT]))
    )
    offers_pending_approval = count(
        select(func.count())
        .select_from(OfferTracking)
        .where(OfferTracking.status == OFFER_PENDING_APPROVAL)
    )
    offers_issued = count(
        select(func.count())
        .select_from(OfferTracking)
        .where(OfferTracking.status == OFFER_SENT)
    )
    joining_pending = count(
        select(func.count())
        .select_from(OfferTracking)
        .where(
            OfferTracking.status == "accepted",
            OfferTracking.joining_status == "pending",
        )
    )
    joined_this_month = count(
        select(func.count())
        .select_from(OfferTracking)
        .where(OfferTracking.joined_at >= month_start)
    )

    stats = [
        # Phase 10 — the twelve master-plan cards, in display order.
        StatItem(key="total_jobs", label="Total jobs", value=total_jobs),
        StatItem(
            key="pending_approval_jobs",
            label="Pending approval jobs",
            value=pending_approval_jobs,
        ),
        StatItem(key="live_jobs", label="Live jobs", value=live_jobs),
        StatItem(key="total_candidates", label="Total candidates", value=total_candidates),
        StatItem(
            key="new_applications",
            label="New applications (this month)",
            value=applications_this_month,
        ),
        StatItem(key="shortlisted", label="Shortlisted", value=shortlisted),
        StatItem(
            key="interviews_today",
            label="Interviews today",
            value=interviews_today,
        ),
        StatItem(
            key="pending_feedback",
            label="Pending feedback",
            value=pending_feedback,
        ),
        StatItem(
            key="offers_pending_approval",
            label="Offers pending approval",
            value=offers_pending_approval,
        ),
        StatItem(key="offers_issued", label="Offers issued", value=offers_issued),
        StatItem(
            key="joining_pending",
            label="Joining pending",
            value=joining_pending,
        ),
        StatItem(
            key="joined_this_month",
            label="Joined this month",
            value=joined_this_month,
        ),
        # Legacy / supplementary stats retained so older dashboard
        # screens that switch on these keys keep working.
        StatItem(key="open_jobs", label="Open jobs", value=open_jobs),
        StatItem(key="applications_total", label="Applications", value=applications_total),
        StatItem(key="ai_reviewed", label="AI reviewed", value=ai_reviewed),
        StatItem(
            key="highly_recommended",
            label="AI recommended",
            value=highly_recommended,
        ),
        StatItem(
            key="hr_review_pending",
            label="HR review pending",
            value=pending_review,
        ),
        StatItem(key="rejected", label="Rejected", value=rejected),
        StatItem(key="selected", label="Selected", value=selected),
        StatItem(key="joined", label="Joined", value=joined),
        StatItem(
            key="pending_interviews",
            label="Pending interviews",
            value=pending_interviews_count,
        ),
        StatItem(
            key="pending_offers",
            label="Pending offers",
            value=pending_offers_count,
        ),
    ]

    # Pipeline funnel — counts per stage in canonical order.
    funnel_rows = dict(
        db.execute(
            select(CandidateJobApplication.status, func.count())
            .group_by(CandidateJobApplication.status)
        ).all()
    )
    funnel = [
        FunnelStage(status=status, label=label, count=int(funnel_rows.get(status, 0)))
        for status, label in FUNNEL_STAGES
    ]

    # Applications per month (last 6 months) — dialect-agnostic Python bucketing.
    applications_per_month = _bucket_by_month(db, CandidateJobApplication.applied_at)

    # Candidates by job opening (top 10).
    by_job_rows = db.execute(
        select(JobOpening.title, func.count(CandidateJobApplication.id))
        .join(
            CandidateJobApplication,
            CandidateJobApplication.job_opening_id == JobOpening.id,
        )
        .group_by(JobOpening.id, JobOpening.title)
        .order_by(desc(func.count(CandidateJobApplication.id)))
        .limit(10)
    ).all()
    by_job = [NamedCount(name=t, count=int(c)) for t, c in by_job_rows]

    # Candidates by department (derived through job_opening.department).
    by_dept_rows = db.execute(
        select(JobOpening.department, func.count(CandidateJobApplication.id))
        .join(
            CandidateJobApplication,
            CandidateJobApplication.job_opening_id == JobOpening.id,
        )
        .group_by(JobOpening.department)
        .order_by(desc(func.count(CandidateJobApplication.id)))
        .limit(10)
    ).all()
    by_department = [NamedCount(name=d, count=int(c)) for d, c in by_dept_rows]

    # Upcoming interviews (next 10 scheduled).
    pending_interviews = _list_pending_interviews(db, limit=10)
    pending_offers = _list_pending_offers(db, limit=10)

    return DashboardSummary(
        stats=stats,
        pipeline_funnel=funnel,
        applications_per_month=applications_per_month,
        candidates_by_job=by_job,
        candidates_by_department=by_department,
        pending_interviews=pending_interviews,
        pending_offers=pending_offers,
    )


# ---------------------------------------------------------------------------
# Phase C-3 — Recruitment analytics
# ---------------------------------------------------------------------------


_ANALYTICS_SOURCES = [
    SOURCE_PUBLIC_FORM,
    SOURCE_MANUAL_UPLOAD,
    SOURCE_BULK_UPLOAD,
]


@router.get("/analytics/recruitment", response_model=RecruitmentAnalytics)
def hr_recruitment_analytics(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_DASHBOARD_VIEW)),
    window_days: int = Query(default=90, ge=7, le=365),
) -> RecruitmentAnalytics:
    """Deeper recruitment metrics windowed over the trailing N days.

    Powers the ``/hr/analytics`` page. Distinct from ``/hr/dashboard``:
    the dashboard surfaces operational state ("what needs my
    attention right now?"), this endpoint surfaces velocity +
    conversion ("how is recruiting performing?"). The default
    window matches the standard HR review cadence.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)

    base_filter = CandidateJobApplication.applied_at >= window_start

    # ---- 1. Daily applications time-series.
    daily_applications = _bucket_by_day(
        db,
        CandidateJobApplication.applied_at,
        window_days=window_days,
        extra_where=base_filter,
    )

    # ---- 2. Funnel stage counts (windowed).
    funnel_rows = db.execute(
        select(CandidateJobApplication.status, func.count())
        .where(base_filter)
        .group_by(CandidateJobApplication.status)
    ).all()
    funnel_lookup: dict[str, int] = {status: count for status, count in funnel_rows}
    pipeline_funnel = [
        FunnelStage(status=status, label=label, count=funnel_lookup.get(status, 0))
        for status, label in FUNNEL_STAGES
    ]

    # ---- 3. Source breakdown (cumulative drop-offs).
    source_breakdown = _build_source_breakdown(db, window_start)

    # ---- 4. Time-to-hire (joined applications only).
    time_to_hire = _build_time_to_hire(db, window_start)

    return RecruitmentAnalytics(
        window_days=window_days,
        daily_applications=daily_applications,
        funnel_conversion=pipeline_funnel,
        source_breakdown=source_breakdown,
        time_to_hire=time_to_hire,
    )


def _bucket_by_day(
    db: Session,
    column,
    *,
    window_days: int,
    extra_where,
) -> List[DailyCount]:
    """Per-day bucket with zero-fill for dates with no activity.

    SQLite (test suite) lacks ``date_trunc``; Postgres has it. We
    bucket Python-side instead so the two engines share the code
    path the rest of ``hr_dashboard`` already follows.
    """
    rows = db.execute(select(column).where(extra_where)).all()
    buckets: dict[str, int] = {}
    for (ts,) in rows:
        if ts is None:
            continue
        key = ts.strftime("%Y-%m-%d")
        buckets[key] = buckets.get(key, 0) + 1

    # Zero-fill so the chart line doesn't visually collapse on quiet
    # days. Walk backwards from today.
    today = datetime.now(timezone.utc).date()
    output: list[DailyCount] = []
    for offset in range(window_days - 1, -1, -1):
        day = today - timedelta(days=offset)
        key = day.strftime("%Y-%m-%d")
        output.append(DailyCount(date=key, count=buckets.get(key, 0)))
    return output


# Statuses that count as "shortlisted or beyond" for the source-breakdown.
_SHORTLISTED_OR_BEYOND = {
    STATUS_SHORTLISTED,
    STATUS_FIRST_INTERVIEW,
    STATUS_TECHNICAL_INTERVIEW,
    STATUS_FINAL_INTERVIEW,
    STATUS_SELECTED,
    STATUS_OFFER_SENT,
    STATUS_JOINED,
}

_OFFERS_OR_BEYOND = {STATUS_OFFER_SENT, STATUS_SELECTED, STATUS_JOINED}


def _build_source_breakdown(
    db: Session, window_start: datetime
) -> List[SourceMetric]:
    """Cumulative drop-off per intake source.

    "Shortlisted" / "Offers issued" / "Joined" are cumulative
    counts — an application currently in ``joined`` is also counted
    in ``shortlisted`` and ``offers_issued`` — so the natural
    percentages a UI computes (``joined / total``, ``offers /
    total``) read as funnel conversion rates.
    """
    rows = db.execute(
        select(CandidateJobApplication.source, CandidateJobApplication.status)
        .where(CandidateJobApplication.applied_at >= window_start)
    ).all()

    # ``source`` may be NULL for legacy rows — bucket those under
    # ``unknown`` so they don't get silently dropped.
    buckets: dict[str, dict[str, int]] = {}
    for source, status in rows:
        key = source or "unknown"
        bucket = buckets.setdefault(
            key, {"total": 0, "shortlisted": 0, "offers_issued": 0, "joined": 0}
        )
        bucket["total"] += 1
        if status in _SHORTLISTED_OR_BEYOND:
            bucket["shortlisted"] += 1
        if status in _OFFERS_OR_BEYOND:
            bucket["offers_issued"] += 1
        if status == STATUS_JOINED:
            bucket["joined"] += 1

    # Emit the canonical sources in a predictable order first, then
    # any unexpected ones (e.g. ``unknown``, future enum values).
    ordering = list(_ANALYTICS_SOURCES) + [
        s for s in buckets if s not in _ANALYTICS_SOURCES
    ]
    return [
        SourceMetric(
            source=source,
            total=buckets.get(source, {}).get("total", 0),
            shortlisted=buckets.get(source, {}).get("shortlisted", 0),
            offers_issued=buckets.get(source, {}).get("offers_issued", 0),
            joined=buckets.get(source, {}).get("joined", 0),
        )
        for source in ordering
        if source in buckets or source in _ANALYTICS_SOURCES
    ]


def _build_time_to_hire(
    db: Session, window_start: datetime
) -> TimeToHireSummary:
    """Avg days from ``applied_at`` to ``OfferTracking.joined_at``.

    Only joined applications inside the window contribute. The
    application carries ``applied_at``; the joining timestamp lives
    on the offer row (``OfferTracking.joined_at``). We pull both via
    a join keyed on ``application_id``.
    """
    rows = db.execute(
        select(
            CandidateJobApplication.source,
            CandidateJobApplication.applied_at,
            OfferTracking.joined_at,
        )
        .join(
            OfferTracking,
            OfferTracking.application_id == CandidateJobApplication.id,
        )
        .where(
            CandidateJobApplication.applied_at >= window_start,
            CandidateJobApplication.status == STATUS_JOINED,
            OfferTracking.joined_at.is_not(None),
        )
    ).all()

    overall_total_days = 0.0
    overall_count = 0
    by_source: dict[str, list[float]] = {}
    for source, applied_at, joined_at in rows:
        if applied_at is None or joined_at is None:
            continue
        days = (joined_at - applied_at).total_seconds() / 86400.0
        # Negative durations would mean a data oddity (clock skew,
        # manual backdating) — skip rather than poison the average.
        if days < 0:
            continue
        overall_total_days += days
        overall_count += 1
        by_source.setdefault(source or "unknown", []).append(days)

    by_source_payload: list[TimeToHireBySource] = []
    ordering = list(_ANALYTICS_SOURCES) + [
        s for s in by_source if s not in _ANALYTICS_SOURCES
    ]
    seen = set()
    for source in ordering:
        if source in seen:
            continue
        seen.add(source)
        values = by_source.get(source, [])
        avg = (sum(values) / len(values)) if values else None
        by_source_payload.append(
            TimeToHireBySource(
                source=source,
                avg_days=round(avg, 1) if avg is not None else None,
                sample_size=len(values),
            )
        )

    overall_avg = (
        round(overall_total_days / overall_count, 1) if overall_count else None
    )
    return TimeToHireSummary(
        overall_avg_days=overall_avg,
        sample_size=overall_count,
        by_source=by_source_payload,
    )


@router.get("/audit-logs", response_model=List[AuditEntryRead])
def hr_audit_logs(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_AUDIT_READ)),
    limit: int = Query(default=50, ge=1, le=200),
    action_prefix: Optional[str] = Query(default=None),
) -> List[AuditEntryRead]:
    """HR-scoped audit log viewer (reads the shared audit_logs table)."""
    stmt = (
        select(AuditLog)
        .where(AuditLog.scope == "hr")
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    if action_prefix:
        stmt = stmt.where(AuditLog.action.like(f"{action_prefix}%"))
    rows = db.execute(stmt).scalars().all()
    return [
        AuditEntryRead(
            id=row.id,
            action=row.action,
            scope=row.scope,
            actor_id=row.actor_id,
            actor_email=row.actor_email,
            target_type=row.target_type,
            target_id=row.target_id,
            ip_address=row.ip_address,
            details=row.details,
            created_at=row.created_at,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bucket_by_month(db: Session, column) -> list[MonthlyCount]:
    """Aggregate rows by YYYY-MM. Python-side so SQLite tests and Postgres
    production share the same code path."""
    rows = db.execute(select(column)).all()
    buckets: dict[str, int] = {}
    for (ts,) in rows:
        if ts is None:
            continue
        key = ts.strftime("%Y-%m")
        buckets[key] = buckets.get(key, 0) + 1
    return [
        MonthlyCount(month=month, count=count)
        for month, count in sorted(buckets.items())
    ]


def _list_pending_interviews(db: Session, limit: int) -> List[InterviewSummary]:
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(Interview, CandidateJobApplication, Candidate, JobOpening, User)
        .join(
            CandidateJobApplication,
            Interview.application_id == CandidateJobApplication.id,
        )
        .join(Candidate, CandidateJobApplication.candidate_id == Candidate.id)
        .outerjoin(
            JobOpening, CandidateJobApplication.job_opening_id == JobOpening.id
        )
        .outerjoin(User, Interview.interviewer_id == User.id)
        .where(
            Interview.status == INTERVIEW_SCHEDULED,
            Interview.scheduled_at >= now,
        )
        .order_by(Interview.scheduled_at)
        .limit(limit)
    ).all()

    return [
        InterviewSummary(
            id=interview.id,
            candidate_name=candidate.full_name,
            job_title=job.title if job else None,
            round_name=interview.round_name,
            scheduled_at=interview.scheduled_at,
            interviewer_name=interviewer.full_name if interviewer else None,
            mode=interview.mode,
        )
        for interview, _app, candidate, job, interviewer in rows
    ]


def _list_pending_offers(db: Session, limit: int) -> List[OfferSummary]:
    rows = db.execute(
        select(OfferTracking, CandidateJobApplication, Candidate, JobOpening)
        .join(
            CandidateJobApplication,
            OfferTracking.application_id == CandidateJobApplication.id,
        )
        .join(Candidate, CandidateJobApplication.candidate_id == Candidate.id)
        .outerjoin(
            JobOpening, CandidateJobApplication.job_opening_id == JobOpening.id
        )
        .where(OfferTracking.status.in_([OFFER_DRAFT, OFFER_SENT]))
        .order_by(desc(OfferTracking.updated_at))
        .limit(limit)
    ).all()

    return [
        OfferSummary(
            id=offer.id,
            candidate_name=candidate.full_name,
            job_title=job.title if job else None,
            salary_offered=offer.salary_offered,
            status=offer.status,
            sent_at=offer.sent_at,
        )
        for offer, _app, candidate, job in rows
    ]

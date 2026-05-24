"""HR ATS dashboard endpoints (Phase 8).

Read-only aggregations over the Phase 7 HR tables. The actual job /
candidate / interview / offer CRUD endpoints land in Phases 9-15.

All routes require an HR-scoped bearer token.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_hr_admin
from app.core.database import get_db
from app.models.auth import AuditLog, User
from app.models.hr_ats import (
    AI_HIGHLY_RECOMMENDED,
    AI_RECOMMENDED,
    INTERVIEW_SCHEDULED,
    OFFER_DRAFT,
    OFFER_SENT,
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
    JobOpening,
    OfferTracking,
)
from app.schemas.hr_dashboard import (
    AuditEntryRead,
    DashboardSummary,
    FunnelStage,
    InterviewSummary,
    MonthlyCount,
    NamedCount,
    OfferSummary,
    StatItem,
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
def hr_dashboard(db: Session = Depends(get_db)) -> DashboardSummary:
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
        select(func.count()).select_from(JobOpening).where(JobOpening.status == "open")
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
    pending_offers_count = count(
        select(func.count())
        .select_from(OfferTracking)
        .where(OfferTracking.status.in_([OFFER_DRAFT, OFFER_SENT]))
    )

    stats = [
        StatItem(key="open_jobs", label="Open jobs", value=open_jobs),
        StatItem(key="total_candidates", label="Total candidates", value=total_candidates),
        StatItem(key="applications_total", label="Applications", value=applications_total),
        StatItem(
            key="applications_this_month",
            label="This month",
            value=applications_this_month,
        ),
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
        StatItem(key="shortlisted", label="Shortlisted", value=shortlisted),
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


@router.get("/audit-logs", response_model=List[AuditEntryRead])
def hr_audit_logs(
    db: Session = Depends(get_db),
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

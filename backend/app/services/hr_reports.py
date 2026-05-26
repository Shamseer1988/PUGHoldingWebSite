"""HR reports service (Phase 16).

Produces tabular `Report` results for seven canonical HR reports:

  - shortlist            : candidates currently shortlisted+
  - job_wise_summary     : per-job CV count + status breakdown
  - interview_status     : every scheduled / completed interview
  - selected_candidates  : candidates reaching the Selected / Offer /
                           Joined statuses
  - rejected_candidates  : status = rejected
  - salary_expectations  : expected_salary buckets across all
                           candidates
  - skill_availability   : skill-frequency rollup from
                           extracted_data.skills

Each function takes the same `CandidateFilters` so the user can scope
any report to "this job / this status / this period". Returns a
`Report` object that the export layer can dump as CSV / Excel / PDF
without knowing report-specific shape.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Sequence

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    STATUS_FINAL_INTERVIEW,
    STATUS_FIRST_INTERVIEW,
    STATUS_JOINED,
    STATUS_OFFER_SENT,
    STATUS_REJECTED,
    STATUS_SELECTED,
    STATUS_SHORTLISTED,
    STATUS_TECHNICAL_INTERVIEW,
    Candidate,
    CandidateJobApplication,
    Interview,
    JobOpening,
)
from app.services.candidate_search import (
    CandidateFilters,
    CandidateRow,
    search_candidates,
)
from app.services.candidate_workflow import (
    STATUS_LABELS as PIPELINE_STATUS_LABELS,
)
from app.services.interview_management import (
    INTERVIEW_MODE_LABELS,
    INTERVIEW_STATUS_LABELS,
)


# ---------------------------------------------------------------------------
# Public report shape
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Report:
    """A finalised tabular report."""

    type: str
    title: str
    description: str
    generated_at: datetime
    columns: List[str]
    rows: List[List[object]]
    summary: Dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Metadata helpers (used by the frontend report picker)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ReportType:
    key: str
    title: str
    description: str
    icon: str  # lucide icon name — frontend resolves


REPORT_TYPES: List[ReportType] = [
    ReportType(
        key="shortlist",
        title="Shortlist report",
        description=(
            "Candidates currently at Shortlisted or any interview stage,"
            " ready to move forward."
        ),
        icon="ListChecks",
    ),
    ReportType(
        key="job_wise_summary",
        title="Job-wise CV summary",
        description=(
            "Per-job CV count plus a status breakdown — useful for"
            " recruiter stand-ups."
        ),
        icon="Briefcase",
    ),
    ReportType(
        key="interview_status",
        title="Interview status report",
        description=(
            "Every interview with date, mode, interviewer, status, and"
            " latest recommendation."
        ),
        icon="CalendarClock",
    ),
    ReportType(
        key="selected_candidates",
        title="Selected candidates report",
        description=(
            "Candidates at Selected, Offer Sent or Joined — your"
            " conversion pipeline."
        ),
        icon="UserCheck",
    ),
    ReportType(
        key="rejected_candidates",
        title="Rejected candidates report",
        description="Rejections with reason and decision date.",
        icon="UserX",
    ),
    ReportType(
        key="salary_expectations",
        title="Salary expectations report",
        description="Expected-salary buckets across the active pipeline.",
        icon="BadgeDollarSign",
    ),
    ReportType(
        key="skill_availability",
        title="Skill availability report",
        description="How often each skill shows up across the pipeline.",
        icon="Sparkles",
    ),
]


ReportRunner = Callable[[Session, CandidateFilters], Report]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


def _status_label(status: str) -> str:
    return PIPELINE_STATUS_LABELS.get(status, status)


_SHORTLIST_STATUSES = {
    STATUS_SHORTLISTED,
    STATUS_FIRST_INTERVIEW,
    STATUS_TECHNICAL_INTERVIEW,
    STATUS_FINAL_INTERVIEW,
}
_SELECTED_STATUSES = {STATUS_SELECTED, STATUS_OFFER_SENT, STATUS_JOINED}


# ---------------------------------------------------------------------------
# Report runners
# ---------------------------------------------------------------------------


def shortlist_report(db: Session, filters: CandidateFilters) -> Report:
    rows: List[List[object]] = []
    for row in search_candidates(db, filters):
        candidate = row.candidate
        if row.latest_status not in _SHORTLIST_STATUSES:
            continue
        rows.append(
            [
                candidate.full_name,
                candidate.email or "",
                candidate.mobile or "",
                candidate.current_designation or "",
                candidate.current_company or "",
                candidate.total_experience_years or "",
                row.top_score if row.top_score is not None else "",
                _status_label(row.latest_status or ""),
                candidate.created_at.date().isoformat()
                if candidate.created_at
                else "",
            ]
        )
    return Report(
        type="shortlist",
        title="Shortlist report",
        description="Candidates currently shortlisted or in any interview stage.",
        generated_at=_now(),
        columns=[
            "Name",
            "Email",
            "Mobile",
            "Designation",
            "Current company",
            "Experience (yrs)",
            "Top score",
            "Latest status",
            "Applied",
        ],
        rows=rows,
        summary={"count": len(rows)},
    )


def job_wise_summary_report(db: Session, filters: CandidateFilters) -> Report:
    candidates = search_candidates(db, filters)
    cand_ids = [r.candidate.id for r in candidates]
    if not cand_ids:
        return _empty_report(
            "job_wise_summary",
            "Job-wise CV summary",
            "Per-job CV count + status breakdown.",
            ["Job", "Department", "Company", "Total CVs", "Shortlisted",
             "Interviewing", "Selected", "Rejected"],
        )

    app_rows = (
        db.execute(
            select(CandidateJobApplication, JobOpening)
            .outerjoin(
                JobOpening,
                JobOpening.id == CandidateJobApplication.job_opening_id,
            )
            .where(CandidateJobApplication.candidate_id.in_(cand_ids))
        )
        .all()
    )

    # Bucket per job.
    buckets: dict[int, dict] = {}
    unlinked = {
        "title": "(no job linked)",
        "department": "",
        "company": "",
        "total": 0,
        "shortlisted": 0,
        "interviewing": 0,
        "selected": 0,
        "rejected": 0,
    }
    for app, job in app_rows:
        if job is None:
            target = unlinked
        else:
            target = buckets.setdefault(
                job.id,
                {
                    "title": job.title,
                    "department": job.department,
                    "company": job.company,
                    "total": 0,
                    "shortlisted": 0,
                    "interviewing": 0,
                    "selected": 0,
                    "rejected": 0,
                },
            )
        target["total"] += 1
        if app.status == STATUS_SHORTLISTED:
            target["shortlisted"] += 1
        elif app.status in (
            STATUS_FIRST_INTERVIEW,
            STATUS_TECHNICAL_INTERVIEW,
            STATUS_FINAL_INTERVIEW,
        ):
            target["interviewing"] += 1
        elif app.status in _SELECTED_STATUSES:
            target["selected"] += 1
        elif app.status == STATUS_REJECTED:
            target["rejected"] += 1

    rows: List[List[object]] = []
    for bucket in list(buckets.values()) + ([unlinked] if unlinked["total"] else []):
        rows.append(
            [
                bucket["title"],
                bucket["department"],
                bucket["company"],
                bucket["total"],
                bucket["shortlisted"],
                bucket["interviewing"],
                bucket["selected"],
                bucket["rejected"],
            ]
        )
    rows.sort(key=lambda r: -int(r[3]))  # most CVs first
    return Report(
        type="job_wise_summary",
        title="Job-wise CV summary",
        description="Per-job CV count + status breakdown.",
        generated_at=_now(),
        columns=[
            "Job",
            "Department",
            "Company",
            "Total CVs",
            "Shortlisted",
            "Interviewing",
            "Selected",
            "Rejected",
        ],
        rows=rows,
        summary={
            "jobs": len(rows),
            "total_cvs": sum(int(r[3]) for r in rows),
        },
    )


def interview_status_report(db: Session, filters: CandidateFilters) -> Report:
    rows_data = search_candidates(db, filters)
    candidate_ids = [r.candidate.id for r in rows_data]
    if not candidate_ids:
        return _empty_report(
            "interview_status",
            "Interview status report",
            "Every interview with date, mode, interviewer, status.",
            [
                "Candidate",
                "Job",
                "Round",
                "Scheduled at",
                "Mode",
                "Interviewer",
                "Status",
                "Latest recommendation",
            ],
        )

    interviews = (
        db.execute(
            select(Interview, CandidateJobApplication, JobOpening, Candidate)
            .join(
                CandidateJobApplication,
                CandidateJobApplication.id == Interview.application_id,
            )
            .outerjoin(
                JobOpening,
                JobOpening.id == CandidateJobApplication.job_opening_id,
            )
            .join(Candidate, Candidate.id == CandidateJobApplication.candidate_id)
            .where(CandidateJobApplication.candidate_id.in_(candidate_ids))
            .order_by(desc(Interview.scheduled_at))
        )
        .all()
    )

    rows: List[List[object]] = []
    for iv, _app, job, candidate in interviews:
        latest_reco = iv.feedback[0].recommendation if iv.feedback else ""
        rows.append(
            [
                candidate.full_name,
                job.title if job else "",
                f"R{iv.round_number} — {iv.round_name}",
                iv.scheduled_at.isoformat() if iv.scheduled_at else "",
                INTERVIEW_MODE_LABELS.get(iv.mode, iv.mode),
                iv.interviewer_id or "",
                INTERVIEW_STATUS_LABELS.get(iv.status, iv.status),
                latest_reco,
            ]
        )
    return Report(
        type="interview_status",
        title="Interview status report",
        description="Every interview with date, mode, interviewer, status.",
        generated_at=_now(),
        columns=[
            "Candidate",
            "Job",
            "Round",
            "Scheduled at",
            "Mode",
            "Interviewer ID",
            "Status",
            "Latest recommendation",
        ],
        rows=rows,
        summary={"count": len(rows)},
    )


def selected_candidates_report(
    db: Session, filters: CandidateFilters
) -> Report:
    rows: List[List[object]] = []
    for row in search_candidates(db, filters):
        if row.latest_status not in _SELECTED_STATUSES:
            continue
        candidate = row.candidate
        rows.append(
            [
                candidate.full_name,
                candidate.email or "",
                candidate.mobile or "",
                candidate.current_designation or "",
                candidate.total_experience_years or "",
                candidate.expected_salary or "",
                candidate.notice_period or "",
                row.top_score if row.top_score is not None else "",
                _status_label(row.latest_status or ""),
            ]
        )
    return Report(
        type="selected_candidates",
        title="Selected candidates report",
        description="Candidates at Selected, Offer Sent, or Joined.",
        generated_at=_now(),
        columns=[
            "Name",
            "Email",
            "Mobile",
            "Designation",
            "Experience (yrs)",
            "Expected salary",
            "Notice period",
            "Top score",
            "Stage",
        ],
        rows=rows,
        summary={"count": len(rows)},
    )


def rejected_candidates_report(
    db: Session, filters: CandidateFilters
) -> Report:
    rows: List[List[object]] = []
    for row in search_candidates(db, filters):
        if row.latest_status != STATUS_REJECTED:
            continue
        candidate = row.candidate
        # Pick the rejected application's reason if any
        reason = ""
        for app_id in row.matched_application_ids:
            app = next(
                (a for a in candidate.applications if a.id == app_id), None
            )
            if app and app.status == STATUS_REJECTED and app.last_rejection_reason:
                reason = app.last_rejection_reason
                break
        rows.append(
            [
                candidate.full_name,
                candidate.email or "",
                candidate.mobile or "",
                candidate.current_designation or "",
                row.top_score if row.top_score is not None else "",
                reason,
                candidate.updated_at.date().isoformat()
                if candidate.updated_at
                else "",
            ]
        )
    return Report(
        type="rejected_candidates",
        title="Rejected candidates report",
        description="Rejections with reason and decision date.",
        generated_at=_now(),
        columns=[
            "Name",
            "Email",
            "Mobile",
            "Designation",
            "Top score",
            "Rejection reason",
            "Updated",
        ],
        rows=rows,
        summary={"count": len(rows)},
    )


_SALARY_BUCKETS = [
    (0, 2999, "Under 3,000"),
    (3000, 4999, "3,000 – 5,000"),
    (5000, 7999, "5,000 – 8,000"),
    (8000, 11999, "8,000 – 12,000"),
    (12000, 17999, "12,000 – 18,000"),
    (18000, 24999, "18,000 – 25,000"),
    (25000, 39999, "25,000 – 40,000"),
    (40000, 10_000_000, "40,000 +"),
]


def salary_expectations_report(
    db: Session, filters: CandidateFilters
) -> Report:
    counts: Dict[str, int] = {label: 0 for *_b, label in _SALARY_BUCKETS}
    unspecified = 0
    for row in search_candidates(db, filters):
        expected = row.candidate.expected_salary
        if expected is None:
            unspecified += 1
            continue
        for lo, hi, label in _SALARY_BUCKETS:
            if lo <= expected <= hi:
                counts[label] += 1
                break

    rows: List[List[object]] = [[label, count] for label, count in counts.items()]
    if unspecified:
        rows.append(["Not specified", unspecified])
    return Report(
        type="salary_expectations",
        title="Salary expectations report",
        description="Expected-salary buckets across the active pipeline.",
        generated_at=_now(),
        columns=["Salary range (monthly)", "Candidates"],
        rows=rows,
        summary={
            "total": sum(int(r[1]) for r in rows),
            "buckets": len([1 for r in rows if int(r[1]) > 0]),
        },
    )


def skill_availability_report(
    db: Session, filters: CandidateFilters
) -> Report:
    counter: Counter[str] = Counter()
    for row in search_candidates(db, filters):
        extracted = row.candidate.extracted_data
        if not extracted or not extracted.skills:
            continue
        for chunk in re.split(r"[,/;\n]+", extracted.skills):
            chunk = chunk.strip()
            if 2 <= len(chunk) <= 60:
                counter[chunk] += 1

    most = counter.most_common(60)
    return Report(
        type="skill_availability",
        title="Skill availability report",
        description="How often each skill shows up across the pipeline.",
        generated_at=_now(),
        columns=["Skill", "Candidates"],
        rows=[[skill, count] for skill, count in most],
        summary={"unique_skills": len(counter)},
    )


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Advanced reports (phase 8)
# ---------------------------------------------------------------------------


def _list_applications(db: Session) -> List[CandidateJobApplication]:
    return list(
        db.execute(
            select(CandidateJobApplication)
            .order_by(desc(CandidateJobApplication.applied_at))
        )
        .scalars()
    )


def all_received_cvs_report(db: Session, filters: CandidateFilters) -> Report:
    apps = _list_applications(db)
    rows = []
    for app in apps:
        c = app.candidate
        rows.append(
            [
                app.id,
                c.full_name if c else "",
                c.email if c else "",
                c.mobile if c else "",
                app.job_opening.title if app.job_opening else "",
                _status_label(app.status),
                app.source or "",
                app.applied_at,
            ]
        )
    return Report(
        type="all_received_cvs",
        title="All Received CVs",
        description="Every candidate application received, regardless of status.",
        generated_at=_now(),
        columns=["App #", "Candidate", "Email", "Mobile", "Job", "Status", "Source", "Applied At"],
        rows=rows,
        summary={"total": len(rows)},
    )


def auto_shortlist_report(db: Session, filters: CandidateFilters) -> Report:
    from app.models.hr_ats import (
        AUTO_REVIEW_SHORTLISTED,
        CandidateAutoReview,
    )

    rows = []
    reviews = list(
        db.execute(
            select(CandidateAutoReview).where(
                CandidateAutoReview.decision == AUTO_REVIEW_SHORTLISTED
            )
        ).scalars()
    )
    for review in reviews:
        app = db.get(CandidateJobApplication, review.application_id)
        if app is None:
            continue
        c = app.candidate
        rows.append(
            [
                review.application_id,
                c.full_name if c else "",
                c.email if c else "",
                app.job_opening.title if app.job_opening else "",
                review.score,
                ", ".join(review.matched_skills or []),
                review.reason_summary or "",
                review.reviewed_at,
            ]
        )
    return Report(
        type="auto_shortlist",
        title="Auto Shortlist Report",
        description="Candidates the auto-review engine recommended for shortlisting.",
        generated_at=_now(),
        columns=["App #", "Candidate", "Email", "Job", "Score", "Matched Skills", "Reason", "Reviewed At"],
        rows=rows,
        summary={"total": len(rows)},
    )


def auto_rejected_report(db: Session, filters: CandidateFilters) -> Report:
    from app.models.hr_ats import (
        AUTO_REVIEW_REJECTED,
        CandidateAutoReview,
    )

    rows = []
    reviews = list(
        db.execute(
            select(CandidateAutoReview).where(
                CandidateAutoReview.decision == AUTO_REVIEW_REJECTED
            )
        ).scalars()
    )
    for review in reviews:
        app = db.get(CandidateJobApplication, review.application_id)
        if app is None:
            continue
        c = app.candidate
        rows.append(
            [
                review.application_id,
                c.full_name if c else "",
                c.email if c else "",
                app.job_opening.title if app.job_opening else "",
                review.score,
                ", ".join(review.missing_skills or []),
                "; ".join(review.risk_flags or []),
                review.reason_summary or "",
                review.reviewed_at,
            ]
        )
    return Report(
        type="auto_rejected",
        title="Auto Rejected Report",
        description="Candidates the auto-review engine marked for auto-rejection.",
        generated_at=_now(),
        columns=["App #", "Candidate", "Email", "Job", "Score", "Missing Skills", "Risk Flags", "Reason", "Reviewed At"],
        rows=rows,
        summary={"total": len(rows)},
    )


def manual_review_pending_report(
    db: Session, filters: CandidateFilters
) -> Report:
    from app.models.hr_ats import (
        AUTO_REVIEW_HR_PENDING,
        CandidateAutoReview,
        STATUS_HR_REVIEW_PENDING,
    )

    rows = []
    apps = list(
        db.execute(
            select(CandidateJobApplication).where(
                CandidateJobApplication.status == STATUS_HR_REVIEW_PENDING
            )
        ).scalars()
    )
    for app in apps:
        c = app.candidate
        review = db.execute(
            select(CandidateAutoReview).where(
                CandidateAutoReview.application_id == app.id
            )
        ).scalar_one_or_none()
        rows.append(
            [
                app.id,
                c.full_name if c else "",
                c.email if c else "",
                app.job_opening.title if app.job_opening else "",
                review.score if review else None,
                review.reason_summary if review else "",
                app.applied_at,
            ]
        )
    return Report(
        type="manual_review_pending",
        title="Manual Review Pending",
        description="Applications waiting for an HR decision.",
        generated_at=_now(),
        columns=["App #", "Candidate", "Email", "Job", "Auto Score", "Auto Notes", "Applied At"],
        rows=rows,
        summary={"total": len(rows)},
    )


def duplicate_candidates_report(
    db: Session, filters: CandidateFilters
) -> Report:
    from sqlalchemy import func

    rows = []
    duplicates = db.execute(
        select(Candidate.email, func.count(Candidate.id).label("c"))
        .where(Candidate.email.is_not(None))
        .group_by(Candidate.email)
        .having(func.count(Candidate.id) > 1)
    ).all()
    for email, count in duplicates:
        names = (
            db.execute(
                select(Candidate.full_name).where(Candidate.email == email)
            )
            .scalars()
            .all()
        )
        rows.append([email, count, ", ".join(names)])
    return Report(
        type="duplicate_candidates",
        title="Duplicate Candidates",
        description="Email addresses linked to more than one candidate row.",
        generated_at=_now(),
        columns=["Email", "Copies", "Candidate Names"],
        rows=rows,
        summary={"duplicate_emails": len(rows)},
    )


def job_approval_pending_report(
    db: Session, filters: CandidateFilters
) -> Report:
    from app.models.hr_ats import APPROVAL_STATUS_PENDING

    rows = []
    jobs = list(
        db.execute(
            select(JobOpening).where(
                JobOpening.approval_status == APPROVAL_STATUS_PENDING
            )
        ).scalars()
    )
    for j in jobs:
        rows.append(
            [
                j.id,
                j.title,
                j.department,
                j.company,
                j.submitted_for_approval_at,
                j.submitted_for_approval_by_id,
            ]
        )
    return Report(
        type="job_approval_pending",
        title="Job Approval Pending",
        description="Jobs waiting on HR Manager approval.",
        generated_at=_now(),
        columns=["Job #", "Title", "Department", "Company", "Submitted At", "Submitted By"],
        rows=rows,
        summary={"total": len(rows)},
    )


def job_approval_history_report(
    db: Session, filters: CandidateFilters
) -> Report:
    from app.models.hr_ats import JobApprovalHistory

    rows = []
    entries = list(
        db.execute(
            select(JobApprovalHistory).order_by(
                desc(JobApprovalHistory.created_at)
            )
        ).scalars()
    )
    for entry in entries:
        job = db.get(JobOpening, entry.job_opening_id)
        rows.append(
            [
                entry.id,
                job.title if job else "(deleted)",
                entry.action,
                entry.old_approval_status,
                entry.new_approval_status,
                entry.actor_email,
                entry.remarks,
                entry.created_at,
            ]
        )
    return Report(
        type="job_approval_history",
        title="Job Approval History",
        description="Every approval-workflow action across all jobs.",
        generated_at=_now(),
        columns=["#", "Job", "Action", "From", "To", "Actor", "Remarks", "At"],
        rows=rows,
        summary={"events": len(rows)},
    )


def candidate_source_report(db: Session, filters: CandidateFilters) -> Report:
    from collections import Counter

    counter: Counter = Counter()
    for app in _list_applications(db):
        counter[app.source or "(unknown)"] += 1
    rows = [[src, count] for src, count in counter.most_common()]
    return Report(
        type="candidate_source",
        title="Candidate Source Report",
        description="How applications break down by intake source.",
        generated_at=_now(),
        columns=["Source", "Applications"],
        rows=rows,
        summary={"total_applications": sum(counter.values())},
    )


def interview_schedule_report(
    db: Session, filters: CandidateFilters
) -> Report:
    """Alias of interview_status with a friendlier title for the picker."""
    base = interview_status_report(db, filters)
    base.type = "interview_schedule"
    base.title = "Interview Schedule"
    base.description = "Upcoming and recent interview schedule."
    return base


def interview_feedback_report(
    db: Session, filters: CandidateFilters
) -> Report:
    from app.models.hr_ats import InterviewFeedback

    rows = []
    entries = list(
        db.execute(
            select(InterviewFeedback).order_by(desc(InterviewFeedback.created_at))
        ).scalars()
    )
    for fb in entries:
        interview = db.get(Interview, fb.interview_id)
        app = interview.application if interview else None
        c = app.candidate if app else None
        rows.append(
            [
                fb.id,
                c.full_name if c else "",
                app.job_opening.title if app and app.job_opening else "",
                fb.rating,
                fb.recommendation,
                fb.feedback or "",
                fb.created_at,
            ]
        )
    return Report(
        type="interview_feedback",
        title="Interview Feedback Report",
        description="Submitted interview feedback rows.",
        generated_at=_now(),
        columns=["#", "Candidate", "Job", "Rating", "Recommendation", "Feedback", "At"],
        rows=rows,
        summary={"total": len(rows)},
    )


def selected_vs_rejected_summary_report(
    db: Session, filters: CandidateFilters
) -> Report:
    from sqlalchemy import func

    counts = dict(
        db.execute(
            select(
                CandidateJobApplication.status,
                func.count(CandidateJobApplication.id),
            ).group_by(CandidateJobApplication.status)
        ).all()
    )
    rows = [
        ["Selected", counts.get("selected", 0)],
        ["Offer Sent", counts.get("offer_sent", 0)],
        ["Joined", counts.get("joined", 0)],
        ["Rejected", counts.get("rejected", 0)],
        ["Blacklisted", counts.get("blacklisted", 0)],
    ]
    return Report(
        type="selected_vs_rejected_summary",
        title="Selected vs Rejected Summary",
        description="Pipeline outcome counts at a glance.",
        generated_at=_now(),
        columns=["Outcome", "Candidates"],
        rows=rows,
        summary={
            "selected": counts.get("selected", 0),
            "rejected": counts.get("rejected", 0),
        },
    )


def cv_parsing_quality_report(
    db: Session, filters: CandidateFilters
) -> Report:
    from app.models.hr_ats import CandidateExtractedData

    candidates = list(db.execute(select(Candidate)).scalars())
    rows = []
    parsed_yes = 0
    for c in candidates:
        extracted = (
            db.execute(
                select(CandidateExtractedData).where(
                    CandidateExtractedData.candidate_id == c.id
                )
            ).scalar_one_or_none()
        )
        is_parsed = bool(extracted and extracted.full_text)
        if is_parsed:
            parsed_yes += 1
        missing_fields = []
        if not c.email:
            missing_fields.append("email")
        if not c.mobile:
            missing_fields.append("mobile")
        if c.total_experience_years is None:
            missing_fields.append("experience")
        if not c.expected_salary:
            missing_fields.append("salary")
        rows.append(
            [
                c.id,
                c.full_name,
                "Yes" if is_parsed else "No",
                extracted.parser_version if extracted else "",
                ", ".join(missing_fields) or "—",
            ]
        )
    return Report(
        type="cv_parsing_quality",
        title="CV Parsing Quality",
        description="Which CVs parsed cleanly and what fields still need HR's eyes.",
        generated_at=_now(),
        columns=["Cand #", "Candidate", "Parsed?", "Parser", "Missing Fields"],
        rows=rows,
        summary={"parsed_ok": parsed_yes, "total": len(candidates)},
    )


def missing_information_report(
    db: Session, filters: CandidateFilters
) -> Report:
    candidates = list(db.execute(select(Candidate)).scalars())
    rows = []
    for c in candidates:
        gaps = []
        if not c.email:
            gaps.append("email")
        if not c.mobile:
            gaps.append("mobile")
        if not c.nationality:
            gaps.append("nationality")
        if c.total_experience_years is None:
            gaps.append("experience")
        if not c.expected_salary:
            gaps.append("salary")
        if not c.notice_period:
            gaps.append("notice")
        if gaps:
            rows.append(
                [
                    c.id,
                    c.full_name,
                    c.email or "",
                    ", ".join(gaps),
                ]
            )
    return Report(
        type="missing_information",
        title="Missing Information",
        description="Candidates whose record is missing key onboarding fields.",
        generated_at=_now(),
        columns=["Cand #", "Candidate", "Email", "Missing Fields"],
        rows=rows,
        summary={"candidates_with_gaps": len(rows)},
    )


def salary_comparison_report(
    db: Session, filters: CandidateFilters
) -> Report:
    rows = []
    for app in _list_applications(db):
        c = app.candidate
        j = app.job_opening
        if not (c and j):
            continue
        rows.append(
            [
                c.full_name,
                j.title,
                c.expected_salary,
                j.salary_min,
                j.salary_max,
                _status_label(app.status),
            ]
        )
    return Report(
        type="salary_comparison",
        title="Salary Comparison",
        description="Each candidate's expected salary alongside the job's band.",
        generated_at=_now(),
        columns=["Candidate", "Job", "Expected", "Band Min", "Band Max", "Status"],
        rows=rows,
        summary={"applications": len(rows)},
    )


def visa_status_report(db: Session, filters: CandidateFilters) -> Report:
    from collections import Counter

    counter: Counter = Counter()
    candidates = list(db.execute(select(Candidate)).scalars())
    for c in candidates:
        counter[c.visa_status or "(unspecified)"] += 1
    rows = [[k, v] for k, v in counter.most_common()]
    return Report(
        type="visa_status",
        title="Visa Status Report",
        description="How candidates split across visa categories.",
        generated_at=_now(),
        columns=["Visa Status", "Candidates"],
        rows=rows,
        summary={"total_candidates": len(candidates)},
    )


def notice_period_report(db: Session, filters: CandidateFilters) -> Report:
    from collections import Counter

    counter: Counter = Counter()
    for c in db.execute(select(Candidate)).scalars():
        counter[c.notice_period or "(unspecified)"] += 1
    rows = [[k, v] for k, v in counter.most_common()]
    return Report(
        type="notice_period",
        title="Notice Period Report",
        description="Distribution of candidates by stated notice period.",
        generated_at=_now(),
        columns=["Notice Period", "Candidates"],
        rows=rows,
        summary={"buckets": len(rows)},
    )


def skills_gap_report(db: Session, filters: CandidateFilters) -> Report:
    """Match each open job's required_skills against the candidate pool
    to flag the skills the org is shortest on."""
    from collections import Counter
    from app.models.hr_ats import CandidateExtractedData

    pool: Counter = Counter()
    for ext in db.execute(select(CandidateExtractedData)).scalars():
        for skill in re.split(r"[,\n;]", ext.skills or ""):
            s = skill.strip().lower()
            if s:
                pool[s] += 1

    jobs = list(
        db.execute(
            select(JobOpening).where(JobOpening.status == "open")
        ).scalars()
    )
    rows = []
    for job in jobs:
        required = [
            s.strip().lower()
            for s in re.split(r"[,\n;]", job.required_skills or "")
            if s.strip()
        ]
        for skill in required:
            rows.append([job.title, skill, pool.get(skill, 0)])
    rows.sort(key=lambda r: r[2])
    return Report(
        type="skills_gap",
        title="Skills Gap Report",
        description="Open-job required skills with the number of candidates we have for each.",
        generated_at=_now(),
        columns=["Job", "Required Skill", "Candidates with skill"],
        rows=rows,
        summary={"shortages": sum(1 for r in rows if r[2] == 0)},
    )


_RUNNERS: Dict[str, ReportRunner] = {
    "shortlist": shortlist_report,
    "job_wise_summary": job_wise_summary_report,
    "interview_status": interview_status_report,
    "selected_candidates": selected_candidates_report,
    "rejected_candidates": rejected_candidates_report,
    "salary_expectations": salary_expectations_report,
    "skill_availability": skill_availability_report,
    # Advanced module — phase 8
    "all_received_cvs": all_received_cvs_report,
    "auto_shortlist": auto_shortlist_report,
    "auto_rejected": auto_rejected_report,
    "manual_review_pending": manual_review_pending_report,
    "duplicate_candidates": duplicate_candidates_report,
    "job_approval_pending": job_approval_pending_report,
    "job_approval_history": job_approval_history_report,
    "candidate_source": candidate_source_report,
    "interview_schedule": interview_schedule_report,
    "interview_feedback": interview_feedback_report,
    "selected_vs_rejected_summary": selected_vs_rejected_summary_report,
    "cv_parsing_quality": cv_parsing_quality_report,
    "missing_information": missing_information_report,
    "salary_comparison": salary_comparison_report,
    "visa_status": visa_status_report,
    "notice_period": notice_period_report,
    "skills_gap": skills_gap_report,
}


# Also register the new report types in REPORT_TYPES for the picker.
REPORT_TYPES.extend([
    ReportType(
        key="all_received_cvs",
        title="All Received CVs",
        description="Every candidate application received, regardless of status.",
        icon="FileText",
    ),
    ReportType(
        key="auto_shortlist",
        title="Auto Shortlist Report",
        description="Candidates the auto-review engine recommended for shortlisting.",
        icon="Sparkles",
    ),
    ReportType(
        key="auto_rejected",
        title="Auto Rejected Report",
        description="Candidates the auto-review engine marked for auto-rejection.",
        icon="ShieldX",
    ),
    ReportType(
        key="manual_review_pending",
        title="Manual Review Pending",
        description="Applications waiting for an HR decision.",
        icon="Hourglass",
    ),
    ReportType(
        key="duplicate_candidates",
        title="Duplicate Candidates",
        description="Email addresses linked to more than one candidate row.",
        icon="Copy",
    ),
    ReportType(
        key="job_approval_pending",
        title="Job Approval Pending",
        description="Jobs waiting on HR Manager approval.",
        icon="ClipboardList",
    ),
    ReportType(
        key="job_approval_history",
        title="Job Approval History",
        description="Every approval-workflow action across all jobs.",
        icon="History",
    ),
    ReportType(
        key="candidate_source",
        title="Candidate Source Report",
        description="How applications break down by intake source.",
        icon="PieChart",
    ),
    ReportType(
        key="interview_schedule",
        title="Interview Schedule Report",
        description="Upcoming and recent interview schedule.",
        icon="CalendarDays",
    ),
    ReportType(
        key="interview_feedback",
        title="Interview Feedback Report",
        description="Submitted interview feedback rows.",
        icon="MessageSquare",
    ),
    ReportType(
        key="selected_vs_rejected_summary",
        title="Selected vs Rejected Summary",
        description="Pipeline outcome counts at a glance.",
        icon="BarChart2",
    ),
    ReportType(
        key="cv_parsing_quality",
        title="CV Parsing Quality",
        description="Which CVs parsed cleanly and what fields still need HR's eyes.",
        icon="ScanText",
    ),
    ReportType(
        key="missing_information",
        title="Missing Information",
        description="Candidates whose record is missing key onboarding fields.",
        icon="AlertCircle",
    ),
    ReportType(
        key="salary_comparison",
        title="Salary Comparison",
        description="Each candidate's expected salary alongside the job's band.",
        icon="DollarSign",
    ),
    ReportType(
        key="visa_status",
        title="Visa Status Report",
        description="How candidates split across visa categories.",
        icon="Stamp",
    ),
    ReportType(
        key="notice_period",
        title="Notice Period Report",
        description="Distribution of candidates by stated notice period.",
        icon="Timer",
    ),
    ReportType(
        key="skills_gap",
        title="Skills Gap Report",
        description="Open-job required skills with the number of candidates we have for each.",
        icon="Brain",
    ),
])


def run_report(
    db: Session, report_type: str, filters: CandidateFilters
) -> Report:
    runner = _RUNNERS.get(report_type)
    if runner is None:
        raise ValueError(f"Unknown report type: {report_type}")
    return runner(db, filters)


def _empty_report(
    rtype: str, title: str, description: str, columns: Sequence[str]
) -> Report:
    return Report(
        type=rtype,
        title=title,
        description=description,
        generated_at=_now(),
        columns=list(columns),
        rows=[],
        summary={"count": 0},
    )

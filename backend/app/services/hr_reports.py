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


_RUNNERS: Dict[str, ReportRunner] = {
    "shortlist": shortlist_report,
    "job_wise_summary": job_wise_summary_report,
    "interview_status": interview_status_report,
    "selected_candidates": selected_candidates_report,
    "rejected_candidates": rejected_candidates_report,
    "salary_expectations": salary_expectations_report,
    "skill_availability": skill_availability_report,
}


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

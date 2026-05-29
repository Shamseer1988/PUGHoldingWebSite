"""Candidate search service (Phase 16).

Centralises the filter logic shared by:
  - GET /hr/candidates (list view filter panel)
  - GET /hr/reports/* (shortlist / job-wise / status / etc.)

Filters split into two passes:
  1. SQL pass (cheap): name/email/mobile keyword, nationality,
     current_location, experience range, salary range, visa keyword,
     notice keyword, uploaded date range, status, score range, job,
     department.
  2. Python pass (post-fetch): JSON fields on CandidateExtractedData —
     skills, languages, education — and any keyword that can't be
     expressed in a portable SQL `like`.

Returns the surviving candidates + per-candidate analytics
(top_score, latest_status, applied jobs) so the API and report
serializers can lift the same numbers without re-querying.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    Candidate,
    CandidateExtractedData,
    CandidateJobApplication,
    CandidateScore,
    JobOpening,
)


@dataclass(slots=True)
class CandidateFilters:
    """Bundle of every supported filter, all optional."""

    q: Optional[str] = None
    include_archived: bool = False

    nationality: Optional[str] = None
    location: Optional[str] = None

    experience_min: Optional[float] = None
    experience_max: Optional[float] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    visa: Optional[str] = None
    notice_period: Optional[str] = None

    education: Optional[str] = None
    language: Optional[str] = None
    skill: Optional[str] = None

    job_slug: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None

    score_min: Optional[int] = None
    score_max: Optional[int] = None

    uploaded_from: Optional[datetime] = None
    uploaded_to: Optional[datetime] = None

    limit: int = 200


@dataclass(slots=True)
class CandidateRow:
    """One row of the resolved search result."""

    candidate: Candidate
    top_score: Optional[int] = None
    latest_status: Optional[str] = None
    matched_application_ids: List[int] = field(default_factory=list)


def _is_postgres(db: Session) -> bool:
    """Detect Postgres vs SQLite at the engine level.

    The candidate FTS column + GIN index live only on Postgres (the
    migration is a no-op on SQLite). The search builder branches on
    this so the test suite — which runs in-memory SQLite — exercises
    the ``ILIKE``-on-``full_text`` fallback and prod takes the
    indexed ``tsvector`` path.
    """
    bind = db.get_bind()
    return bind.dialect.name == "postgresql"


def _apply_keyword_filter(stmt, db: Session, q: str):
    """Widen the free-text query to also match the CV body.

    The same observable behaviour on either dialect — a candidate
    whose extracted CV text contains the query term is found — with
    Postgres routing through a GIN-backed ``tsvector @@ tsquery``
    and SQLite falling back to ``ILIKE`` on the same column.
    """
    like = f"%{q.lower()}%"
    base_predicates = (
        (func.lower(Candidate.full_name).like(like))
        | (func.lower(Candidate.email).like(like))
        | (Candidate.mobile.like(f"%{q}%"))
    )

    if _is_postgres(db):
        # ``websearch_to_tsquery`` accepts the same syntax operators
        # most search UIs already use (``"phrase"``, ``-not``, ``OR``)
        # without raising on malformed input — kinder to interactive
        # filter panels than ``to_tsquery`` would be.
        fts_match = (
            func.to_tsvector(
                "simple", func.coalesce(CandidateExtractedData.full_text, "")
            )
            .op("@@")(func.websearch_to_tsquery("simple", q))
        )
        cv_subquery = (
            select(CandidateExtractedData.candidate_id)
            .where(fts_match)
            .scalar_subquery()
        )
    else:
        cv_subquery = (
            select(CandidateExtractedData.candidate_id)
            .where(
                func.lower(
                    func.coalesce(CandidateExtractedData.full_text, "")
                ).like(like)
            )
            .scalar_subquery()
        )

    return stmt.where(base_predicates | Candidate.id.in_(cv_subquery))


def search_candidates(
    db: Session, filters: CandidateFilters
) -> List[CandidateRow]:
    """Run the search and return enriched rows. Caller commits / serializes."""
    # --- SQL pass --------------------------------------------------------
    stmt = (
        select(Candidate)
        .order_by(desc(Candidate.created_at), desc(Candidate.id))
        .limit(max(1, filters.limit))
    )
    if not filters.include_archived:
        stmt = stmt.where(Candidate.is_archived.is_(False))
    if filters.q:
        stmt = _apply_keyword_filter(stmt, db, filters.q)
    if filters.nationality:
        stmt = stmt.where(
            func.lower(Candidate.nationality).like(
                f"%{filters.nationality.lower()}%"
            )
        )
    if filters.location:
        stmt = stmt.where(
            func.lower(Candidate.current_location).like(
                f"%{filters.location.lower()}%"
            )
        )
    if filters.experience_min is not None:
        stmt = stmt.where(
            Candidate.total_experience_years >= filters.experience_min
        )
    if filters.experience_max is not None:
        stmt = stmt.where(
            Candidate.total_experience_years <= filters.experience_max
        )
    if filters.salary_min is not None:
        stmt = stmt.where(Candidate.expected_salary >= filters.salary_min)
    if filters.salary_max is not None:
        stmt = stmt.where(Candidate.expected_salary <= filters.salary_max)
    if filters.visa:
        stmt = stmt.where(
            func.lower(Candidate.visa_status).like(f"%{filters.visa.lower()}%")
        )
    if filters.notice_period:
        stmt = stmt.where(
            func.lower(Candidate.notice_period).like(
                f"%{filters.notice_period.lower()}%"
            )
        )
    if filters.uploaded_from is not None:
        stmt = stmt.where(Candidate.created_at >= filters.uploaded_from)
    if filters.uploaded_to is not None:
        stmt = stmt.where(Candidate.created_at <= filters.uploaded_to)

    candidates = db.execute(stmt).scalars().all()
    if not candidates:
        return []

    cand_ids = [c.id for c in candidates]

    # --- Application-level analytics (top score, latest status,
    #     job/department + status filters) ---------------------------------
    app_rows = (
        db.execute(
            select(
                CandidateJobApplication,
                JobOpening,
            )
            .outerjoin(
                JobOpening,
                JobOpening.id == CandidateJobApplication.job_opening_id,
            )
            .where(CandidateJobApplication.candidate_id.in_(cand_ids))
        )
        .all()
    )

    score_rows = (
        db.execute(
            select(CandidateScore).where(
                CandidateScore.application_id.in_(
                    [a.id for a, _j in app_rows]
                )
            )
        )
        .scalars()
        .all()
    )
    score_by_app: dict[int, CandidateScore] = {
        s.application_id: s for s in score_rows
    }

    # Bucket per-candidate applications + carry the joined job opening.
    apps_by_candidate: dict[int, list[tuple[CandidateJobApplication, Optional[JobOpening]]]] = {}
    for app, job in app_rows:
        apps_by_candidate.setdefault(app.candidate_id, []).append((app, job))

    # Resolve which applications match the job / department / status /
    # score filters. A candidate is kept if at least one application
    # passes (so multi-job applicants aren't accidentally hidden).
    needs_app_filter = bool(
        filters.job_slug
        or filters.department
        or filters.status
        or filters.score_min is not None
        or filters.score_max is not None
    )

    rows: List[CandidateRow] = []
    for candidate in candidates:
        applications = apps_by_candidate.get(candidate.id, [])
        matched: list[int] = []
        if needs_app_filter:
            for app, job in applications:
                if filters.job_slug and (
                    not job or job.slug != filters.job_slug
                ):
                    continue
                if filters.department and (
                    not job
                    or filters.department.lower() not in (job.department or "").lower()
                ):
                    continue
                if filters.status and app.status != filters.status:
                    continue
                score = score_by_app.get(app.id)
                if filters.score_min is not None and (
                    score is None or score.total < filters.score_min
                ):
                    continue
                if filters.score_max is not None and (
                    score is None or score.total > filters.score_max
                ):
                    continue
                matched.append(app.id)
            if not matched:
                continue
        else:
            matched = [app.id for app, _ in applications]

        # Top score across the candidate's *matched* applications.
        scores = [
            score_by_app[aid].total
            for aid in matched
            if aid in score_by_app
        ]
        top_score = max(scores) if scores else None

        # Latest status = newest applied_at among matched apps.
        latest_status: Optional[str] = None
        latest_at = None
        for app, _ in applications:
            if app.id not in matched:
                continue
            if latest_at is None or app.applied_at > latest_at:
                latest_at = app.applied_at
                latest_status = app.status

        rows.append(
            CandidateRow(
                candidate=candidate,
                top_score=top_score,
                latest_status=latest_status,
                matched_application_ids=matched,
            )
        )

    # --- Python pass on JSON extracted_data ------------------------------
    if filters.skill or filters.language or filters.education:
        rows = [r for r in rows if _matches_extracted(r.candidate, filters)]

    return rows


def _matches_extracted(candidate: Candidate, f: CandidateFilters) -> bool:
    extracted: Optional[CandidateExtractedData] = candidate.extracted_data
    if f.skill:
        needle = f.skill.lower()
        haystack: list[str] = []
        if extracted and extracted.skills:
            haystack.append(extracted.skills.lower())
        if extracted and extracted.full_text:
            haystack.append(extracted.full_text.lower())
        if candidate.current_designation:
            haystack.append(candidate.current_designation.lower())
        if not any(needle in h for h in haystack):
            return False
    if f.language:
        needle = f.language.lower()
        if not extracted or not extracted.languages:
            return False
        if not any(needle in (l or "").lower() for l in extracted.languages):
            return False
    if f.education:
        needle = f.education.lower()
        chunks: list[str] = []
        if extracted and isinstance(extracted.education, list):
            for item in extracted.education:
                if isinstance(item, dict):
                    for k in ("raw", "degree", "institution"):
                        v = item.get(k)
                        if v:
                            chunks.append(str(v).lower())
        if not any(needle in c for c in chunks):
            return False
    return True


def collect_distinct_job_options(
    db: Session,
) -> list[tuple[str, str, Optional[str]]]:
    """Helper for the filter dropdown — returns (slug, title, department)."""
    rows = (
        db.execute(
            select(JobOpening.slug, JobOpening.title, JobOpening.department)
            .order_by(JobOpening.title)
        )
        .all()
    )
    return [(slug, title, department) for slug, title, department in rows]


def collect_distinct_departments(db: Session) -> list[str]:
    rows = (
        db.execute(select(JobOpening.department).distinct())
        .scalars()
        .all()
    )
    return sorted({d for d in rows if d})

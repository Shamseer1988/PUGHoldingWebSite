"""Auto-review / auto-shortlist engine (advanced module — phase 4).

Combines the existing rule-based score with a per-job
:class:`JobAutoReviewRule` to classify each application into one of:

* ``auto_shortlisted`` — score above threshold and no critical mismatch.
* ``hr_review_pending`` — medium-confidence; HR must look at it.
* ``auto_rejected`` — below reject threshold *and* the rule explicitly
  enables auto-reject (``auto_reject_enabled=True``). Without that flag
  every low-score candidate still lands in HR review so a human signs
  off on the rejection.
* ``duplicate`` — same candidate already has another application on the
  same job (the existing intake layer surfaces this; auto-review just
  mirrors the flag if the caller passes it).

The service is deterministic — no LLM call — so it's safe inside the
upload request. It also takes the existing AI review preview into
account when present.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    AI_HIGHLY_RECOMMENDED,
    AI_NEUTRAL,
    AI_NOT_RECOMMENDED,
    AI_RECOMMENDED,
    AUTO_REVIEW_HR_PENDING,
    AUTO_REVIEW_REJECTED,
    AUTO_REVIEW_SHORTLISTED,
    CandidateAutoReview,
    CandidateJobApplication,
    JobAutoReviewRule,
)


logger = logging.getLogger(__name__)


DEFAULT_SHORTLIST_THRESHOLD = 75
DEFAULT_REJECT_THRESHOLD = 40


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _split_tokens(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [
        token.strip().lower()
        for token in re.split(r"[,\n;]", value)
        if token.strip()
    ]


def _normalise_keywords(values: Optional[Iterable[str]]) -> List[str]:
    if not values:
        return []
    return [str(v).strip().lower() for v in values if str(v).strip()]


def _any_keyword_in(text: Optional[str], keywords: Sequence[str]) -> bool:
    if not text or not keywords:
        return False
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def _candidate_skills(application: CandidateJobApplication) -> List[str]:
    candidate = application.candidate
    extracted = candidate.extracted_data if candidate else None
    skills = _split_tokens(extracted.skills) if extracted else []
    return skills


def _job_required_skills(rule: JobAutoReviewRule, application: CandidateJobApplication) -> List[str]:
    if rule.required_skills:
        return _normalise_keywords(rule.required_skills)
    job = application.job_opening
    return _split_tokens(job.required_skills) if job else []


def _job_preferred_skills(rule: JobAutoReviewRule, application: CandidateJobApplication) -> List[str]:
    if rule.preferred_skills:
        return _normalise_keywords(rule.preferred_skills)
    job = application.job_opening
    return _split_tokens(job.preferred_skills) if job else []


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class AutoReviewOutcome:
    decision: str
    score: Optional[int] = None
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    reason_summary: Optional[str] = None
    recommendation_source: str = "rule_engine"
    rule_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


def get_or_create_rule(
    db: Session, *, job_opening_id: int, created_by_id: Optional[int] = None
) -> JobAutoReviewRule:
    """Fetch the per-job rule, creating an inactive default if missing."""
    rule = db.execute(
        select(JobAutoReviewRule).where(
            JobAutoReviewRule.job_opening_id == job_opening_id
        )
    ).scalar_one_or_none()
    if rule is None:
        rule = JobAutoReviewRule(
            job_opening_id=job_opening_id,
            is_active=False,
            created_by_id=created_by_id,
        )
        db.add(rule)
        db.flush()
    return rule


def _resolve_thresholds(rule: JobAutoReviewRule) -> Tuple[int, int]:
    shortlist = rule.auto_shortlist_threshold or rule.min_score or DEFAULT_SHORTLIST_THRESHOLD
    reject = rule.auto_reject_threshold or DEFAULT_REJECT_THRESHOLD
    if reject >= shortlist:
        # Keep shortlist > reject so the bands don't overlap.
        reject = max(0, shortlist - 1)
    return shortlist, reject


def _evaluate_skills(
    application: CandidateJobApplication, rule: JobAutoReviewRule
) -> Tuple[List[str], List[str]]:
    cand_skills = set(_candidate_skills(application))
    required = _job_required_skills(rule, application)
    matched = [skill for skill in required if skill in cand_skills]
    missing = [skill for skill in required if skill not in cand_skills]
    return matched, missing


def _hard_rule_flags(
    application: CandidateJobApplication, rule: JobAutoReviewRule
) -> List[str]:
    flags: List[str] = []
    candidate = application.candidate
    if candidate is None:
        flags.append("candidate_missing")
        return flags

    if rule.min_experience is not None and (
        candidate.total_experience_years is None
        or candidate.total_experience_years < float(rule.min_experience)
    ):
        flags.append(
            f"experience_below_min ({candidate.total_experience_years or 0} <"
            f" {rule.min_experience})"
        )

    if rule.max_expected_salary is not None and (
        candidate.expected_salary is not None
        and candidate.expected_salary > int(rule.max_expected_salary)
    ):
        flags.append(
            f"salary_above_max ({candidate.expected_salary} > "
            f"{rule.max_expected_salary})"
        )

    visa_keywords = _normalise_keywords(rule.visa_keywords)
    if visa_keywords and not _any_keyword_in(candidate.visa_status, visa_keywords):
        flags.append(f"visa_mismatch ({candidate.visa_status or '—'})")

    location_keywords = _normalise_keywords(rule.location_keywords)
    if location_keywords and not _any_keyword_in(
        candidate.current_location, location_keywords
    ):
        flags.append(
            f"location_mismatch ({candidate.current_location or '—'})"
        )

    nationality_keywords = _normalise_keywords(rule.nationality_keywords)
    if nationality_keywords and not _any_keyword_in(
        candidate.nationality, nationality_keywords
    ):
        flags.append(
            f"nationality_mismatch ({candidate.nationality or '—'})"
        )

    notice_keywords = _normalise_keywords(rule.notice_period_keywords)
    if notice_keywords and not _any_keyword_in(
        candidate.notice_period, notice_keywords
    ):
        flags.append(
            f"notice_period_mismatch ({candidate.notice_period or '—'})"
        )

    return flags


def _ai_bias(application: CandidateJobApplication) -> Optional[str]:
    """Read the existing AI review (if any) to tilt the decision."""
    ai_review = application.ai_review
    if ai_review is None:
        return None
    return ai_review.recommendation


def evaluate(
    application: CandidateJobApplication, rule: Optional[JobAutoReviewRule] = None
) -> AutoReviewOutcome:
    """Pure function: turn application + rule into an AutoReviewOutcome.

    Caller (typically :func:`run_auto_review`) persists the outcome.
    """
    score_obj = application.score
    score = score_obj.total if score_obj is not None else None

    if rule is None or not rule.is_active:
        # No active rule — still flag for HR review, never auto-reject.
        return AutoReviewOutcome(
            decision=AUTO_REVIEW_HR_PENDING,
            score=score,
            reason_summary="No active auto-review rule for this job.",
            recommendation_source="rule_engine",
            rule_id=rule.id if rule else None,
        )

    shortlist_threshold, reject_threshold = _resolve_thresholds(rule)
    matched, missing = _evaluate_skills(application, rule)
    risk_flags = _hard_rule_flags(application, rule)
    ai_rec = _ai_bias(application)

    score_for_decision = score if score is not None else 0

    # AI recommendation can nudge the band.
    if ai_rec == AI_HIGHLY_RECOMMENDED:
        score_for_decision = min(100, score_for_decision + 5)
    elif ai_rec == AI_RECOMMENDED:
        score_for_decision = min(100, score_for_decision + 2)
    elif ai_rec == AI_NOT_RECOMMENDED:
        score_for_decision = max(0, score_for_decision - 5)

    has_required_skills = not missing or len(matched) >= max(
        1, len(matched) + len(missing) - 1
    )
    has_critical_flag = bool(risk_flags)

    decision: str
    reason_bits: List[str] = []

    if (
        score_for_decision >= shortlist_threshold
        and not has_critical_flag
        and has_required_skills
    ):
        decision = AUTO_REVIEW_SHORTLISTED
        reason_bits.append(
            f"score {score_for_decision} ≥ shortlist threshold {shortlist_threshold}"
        )
        if matched:
            reason_bits.append(f"matched skills: {', '.join(matched)}")
    elif (
        score_for_decision < reject_threshold
        and rule.auto_reject_enabled
    ):
        decision = AUTO_REVIEW_REJECTED
        reason_bits.append(
            f"score {score_for_decision} < reject threshold {reject_threshold}"
        )
        if risk_flags:
            reason_bits.append(f"risk flags: {', '.join(risk_flags)}")
        if missing:
            reason_bits.append(f"missing required skills: {', '.join(missing)}")
    else:
        decision = AUTO_REVIEW_HR_PENDING
        if score_for_decision < shortlist_threshold:
            reason_bits.append(
                f"score {score_for_decision} below shortlist {shortlist_threshold}"
            )
        if missing:
            reason_bits.append(f"missing skills: {', '.join(missing)}")
        if risk_flags:
            reason_bits.append("flagged: " + "; ".join(risk_flags))
        if not reason_bits:
            reason_bits.append("Held for HR review.")

    return AutoReviewOutcome(
        decision=decision,
        score=score,
        matched_skills=matched,
        missing_skills=missing,
        risk_flags=risk_flags,
        reason_summary="; ".join(reason_bits)[:1000],
        recommendation_source=(
            "rule_engine+ai" if ai_rec else "rule_engine"
        ),
        rule_id=rule.id,
    )


def run_auto_review(
    db: Session,
    *,
    application: CandidateJobApplication,
    rule: Optional[JobAutoReviewRule] = None,
    reviewed_by_system: bool = True,
) -> CandidateAutoReview:
    """Evaluate + upsert the CandidateAutoReview row. Caller commits."""
    if rule is None and application.job_opening_id is not None:
        rule = db.execute(
            select(JobAutoReviewRule).where(
                JobAutoReviewRule.job_opening_id == application.job_opening_id
            )
        ).scalar_one_or_none()

    outcome = evaluate(application, rule)

    existing = db.execute(
        select(CandidateAutoReview).where(
            CandidateAutoReview.application_id == application.id
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = CandidateAutoReview(
            application_id=application.id,
            rule_id=outcome.rule_id,
            score=outcome.score,
            decision=outcome.decision,
            matched_skills=outcome.matched_skills or None,
            missing_skills=outcome.missing_skills or None,
            risk_flags=outcome.risk_flags or None,
            reason_summary=outcome.reason_summary,
            recommendation_source=outcome.recommendation_source,
            reviewed_by_system=reviewed_by_system,
        )
        db.add(existing)
    else:
        existing.rule_id = outcome.rule_id
        existing.score = outcome.score
        existing.decision = outcome.decision
        existing.matched_skills = outcome.matched_skills or None
        existing.missing_skills = outcome.missing_skills or None
        existing.risk_flags = outcome.risk_flags or None
        existing.reason_summary = outcome.reason_summary
        existing.recommendation_source = outcome.recommendation_source
        existing.reviewed_by_system = reviewed_by_system
    db.flush()
    return existing


def run_auto_review_for_job(
    db: Session,
    *,
    job_opening_id: int,
) -> List[CandidateAutoReview]:
    """Bulk-run auto-review for every application on a job."""
    rule = db.execute(
        select(JobAutoReviewRule).where(
            JobAutoReviewRule.job_opening_id == job_opening_id
        )
    ).scalar_one_or_none()
    apps = list(
        db.execute(
            select(CandidateJobApplication).where(
                CandidateJobApplication.job_opening_id == job_opening_id
            )
        ).scalars()
    )
    return [run_auto_review(db, application=app, rule=rule) for app in apps]


def summarise_job(
    db: Session, *, job_opening_id: int
) -> dict:
    """Return aggregate counts of auto-review decisions for one job."""
    apps = list(
        db.execute(
            select(CandidateJobApplication).where(
                CandidateJobApplication.job_opening_id == job_opening_id
            )
        ).scalars()
    )
    summary = {
        "job_opening_id": job_opening_id,
        "total_applications": len(apps),
        "auto_shortlisted": 0,
        "hr_review_pending": 0,
        "auto_rejected": 0,
        "duplicates": 0,
        "not_reviewed": 0,
    }
    for app in apps:
        review = db.execute(
            select(CandidateAutoReview).where(
                CandidateAutoReview.application_id == app.id
            )
        ).scalar_one_or_none()
        if review is None:
            summary["not_reviewed"] += 1
            continue
        if review.decision == AUTO_REVIEW_SHORTLISTED:
            summary["auto_shortlisted"] += 1
        elif review.decision == AUTO_REVIEW_HR_PENDING:
            summary["hr_review_pending"] += 1
        elif review.decision == AUTO_REVIEW_REJECTED:
            summary["auto_rejected"] += 1
        elif review.decision == "duplicate":
            summary["duplicates"] += 1
    return summary

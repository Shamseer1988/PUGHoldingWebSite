"""Candidate scoring engine (Phase 12).

Rule-based score out of 100 comparing a candidate to a specific job
opening. The breakdown follows the master spec exactly:

    Relevant experience       /25
    Required skills           /20
    Education                 /10
    Industry / company        /10
    GCC / Qatar experience    /10
    Salary fit                /10
    Notice period             /5
    Visa status               /5
    Language match            /5
                              ----
    Total                     /100

The score is **deterministic** — no LLM, no network — so it is safe to
run inside the upload request. Each component returns a short human
explanation that is persisted in
``CandidateScoreBreakdown.notes[<component>]`` so HR can see *why* a
candidate received the score they did.

Manual overrides bypass the engine entirely but keep the last computed
breakdown for transparency.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Set

from sqlalchemy.orm import Session

from app.models.hr_ats import (
    Candidate,
    CandidateExtractedData,
    CandidateJobApplication,
    CandidateScore,
    CandidateScoreBreakdown,
    JobOpening,
)


logger = logging.getLogger(__name__)


SCORER_VERSION = "phase12.rules.1"

# Max points per component (mirrors the master spec).
MAX_POINTS: Dict[str, int] = {
    "relevant_experience": 25,
    "required_skills": 20,
    "education": 10,
    "industry_experience": 10,
    "gcc_qatar_experience": 10,
    "salary_fit": 10,
    "notice_period": 5,
    "visa_status": 5,
    "language_match": 5,
}
TOTAL_MAX = sum(MAX_POINTS.values())  # 100

# Locations that count as "in Qatar" / "in the GCC" for the regional
# experience component.
QATAR_TOKENS = ("qatar", "doha", "lusail", "al rayyan", "al wakrah", "mesaieed")
GCC_TOKENS = (
    "qatar", "doha", "uae", "dubai", "abu dhabi", "sharjah",
    "saudi", "ksa", "riyadh", "jeddah", "dammam", "khobar",
    "bahrain", "manama", "kuwait", "muscat", "oman", "salalah",
    "gcc", "gulf",
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ComponentScore:
    points: int
    max_points: int
    note: str


@dataclass(slots=True)
class ScoredResult:
    total: int
    breakdown: Dict[str, ComponentScore] = field(default_factory=dict)
    scorer_version: str = SCORER_VERSION

    def notes(self) -> Dict[str, str]:
        return {key: comp.note for key, comp in self.breakdown.items()}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_score(
    *,
    candidate: Candidate,
    job: Optional[JobOpening],
) -> ScoredResult:
    """Compute the per-component score for a candidate against a job.

    When ``job`` is ``None`` (application not tied to a job opening),
    we return an all-zero breakdown — there is nothing to score against.
    """
    if job is None:
        zero = {key: ComponentScore(0, maxp, "No job opening linked to score against.")
                for key, maxp in MAX_POINTS.items()}
        return ScoredResult(total=0, breakdown=zero)

    extracted = candidate.extracted_data
    breakdown: Dict[str, ComponentScore] = {
        "relevant_experience": _score_relevant_experience(candidate, job),
        "required_skills": _score_required_skills(candidate, job, extracted),
        "education": _score_education(candidate, job, extracted),
        "industry_experience": _score_industry_experience(candidate, job, extracted),
        "gcc_qatar_experience": _score_gcc_qatar_experience(candidate, job),
        "salary_fit": _score_salary_fit(candidate, job),
        "notice_period": _score_notice_period(candidate, job),
        "visa_status": _score_visa_status(candidate, job),
        "language_match": _score_language_match(candidate, job, extracted),
    }
    total = sum(c.points for c in breakdown.values())
    return ScoredResult(total=total, breakdown=breakdown)


def upsert_score(
    db: Session,
    *,
    application: CandidateJobApplication,
    result: ScoredResult,
    preserve_manual_override: bool = True,
) -> CandidateScore:
    """Persist a scored result against an application.

    Manual overrides are preserved by default — the latest auto-score
    is still saved in the breakdown for transparency, but the headline
    ``total`` and override flag stay untouched.
    """
    score = application.score
    if score is None:
        score = CandidateScore(application_id=application.id, total=0)
        db.add(score)
        db.flush()

    # Save the new breakdown either way.
    breakdown = score.breakdown
    if breakdown is None:
        breakdown = CandidateScoreBreakdown(score_id=score.id)
        db.add(breakdown)

    breakdown.relevant_experience = result.breakdown["relevant_experience"].points
    breakdown.required_skills = result.breakdown["required_skills"].points
    breakdown.education = result.breakdown["education"].points
    breakdown.industry_experience = result.breakdown["industry_experience"].points
    breakdown.gcc_qatar_experience = result.breakdown["gcc_qatar_experience"].points
    breakdown.salary_fit = result.breakdown["salary_fit"].points
    breakdown.notice_period = result.breakdown["notice_period"].points
    breakdown.visa_status = result.breakdown["visa_status"].points
    breakdown.language_match = result.breakdown["language_match"].points
    breakdown.notes = result.notes()

    if not (preserve_manual_override and score.is_manual_override):
        score.total = result.total

    db.flush()
    return score


def apply_manual_override(
    db: Session,
    *,
    score: CandidateScore,
    new_total: int,
    reason: str,
    overridden_by_id: int,
) -> CandidateScore:
    """Apply a manual override with a mandatory reason."""
    from datetime import datetime, timezone

    if not reason or not reason.strip():
        raise ValueError("A reason is mandatory when overriding a score.")
    if not (0 <= new_total <= TOTAL_MAX):
        raise ValueError(f"Score must be between 0 and {TOTAL_MAX}.")

    score.total = int(new_total)
    score.is_manual_override = True
    score.override_reason = reason.strip()
    score.overridden_by_id = overridden_by_id
    score.overridden_at = datetime.now(timezone.utc)
    db.flush()
    return score


def clear_manual_override(
    db: Session,
    *,
    score: CandidateScore,
    auto_total: Optional[int] = None,
) -> CandidateScore:
    """Drop the manual override and (optionally) restore the auto-score."""
    score.is_manual_override = False
    score.override_reason = None
    score.overridden_by_id = None
    score.overridden_at = None
    if auto_total is not None:
        score.total = int(auto_total)
    db.flush()
    return score


# ---------------------------------------------------------------------------
# Component scorers
# ---------------------------------------------------------------------------


def _score_relevant_experience(
    candidate: Candidate, job: JobOpening
) -> ComponentScore:
    max_pts = MAX_POINTS["relevant_experience"]
    years = candidate.total_experience_years
    if years is None:
        return ComponentScore(
            0, max_pts, "No total experience recorded on the candidate."
        )

    min_y = job.min_experience or 0
    max_y = job.max_experience or 0
    has_cap = max_y > 0

    if years >= min_y and (not has_cap or years <= max_y):
        return ComponentScore(
            max_pts,
            max_pts,
            f"{years:g} years matches the {min_y}–{max_y or '∞'} year range.",
        )

    if years < min_y:
        if min_y <= 0:
            return ComponentScore(max_pts, max_pts, f"{years:g} years available.")
        ratio = max(0.0, years / min_y)
        pts = round(ratio * max_pts)
        return ComponentScore(
            pts,
            max_pts,
            f"{years:g} years is below the {min_y}-year minimum (scaled).",
        )

    # Over the cap — still award most points (overqualified, not disqualified).
    overshoot = years - max_y
    if overshoot <= 2:
        return ComponentScore(
            max_pts - 3,
            max_pts,
            f"{years:g} years slightly exceeds the {max_y}-year cap.",
        )
    if overshoot <= 5:
        return ComponentScore(
            max_pts - 8,
            max_pts,
            f"{years:g} years is well above the {max_y}-year cap.",
        )
    return ComponentScore(
        max_pts - 13,
        max_pts,
        f"{years:g} years is far above the {max_y}-year cap (possibly overqualified).",
    )


def _score_required_skills(
    candidate: Candidate,
    job: JobOpening,
    extracted: Optional[CandidateExtractedData],
) -> ComponentScore:
    max_pts = MAX_POINTS["required_skills"]
    required = _tokenize_skills(job.required_skills)
    preferred = _tokenize_skills(job.preferred_skills)
    if not required and not preferred:
        return ComponentScore(
            max_pts // 2,
            max_pts,
            "Job did not list required skills — neutral score.",
        )

    candidate_skills = _candidate_skill_tokens(candidate, extracted)
    if not candidate_skills:
        return ComponentScore(
            0, max_pts, "Candidate has no recorded skills to match against."
        )

    matched_required = required & candidate_skills
    matched_preferred = preferred & candidate_skills

    if required:
        ratio = len(matched_required) / len(required)
        base = ratio * (max_pts * 0.85)  # required carries 85% of the weight
    else:
        base = max_pts * 0.85  # nothing strictly required → assume met
    if preferred:
        ratio_pref = len(matched_preferred) / len(preferred)
        base += ratio_pref * (max_pts * 0.15)

    pts = int(round(min(base, max_pts)))
    note_parts = []
    if required:
        note_parts.append(
            f"{len(matched_required)}/{len(required)} required skills matched"
        )
    if preferred:
        note_parts.append(
            f"{len(matched_preferred)}/{len(preferred)} preferred matched"
        )
    return ComponentScore(pts, max_pts, "; ".join(note_parts) + ".")


def _score_education(
    candidate: Candidate,
    job: JobOpening,
    extracted: Optional[CandidateExtractedData],
) -> ComponentScore:
    max_pts = MAX_POINTS["education"]
    required = (job.required_education or "").strip()
    if not required:
        return ComponentScore(
            max_pts - 2,
            max_pts,
            "Job did not specify a required qualification — assumed met.",
        )

    haystack = _education_haystack(candidate, extracted).lower()
    if not haystack:
        return ComponentScore(0, max_pts, "No education recorded on the candidate.")

    req_tokens = [t for t in re.split(r"[^a-z0-9]+", required.lower()) if len(t) > 2]
    if not req_tokens:
        return ComponentScore(max_pts // 2, max_pts, "Couldn't parse the required qualification.")

    hits = sum(1 for tok in req_tokens if tok in haystack)
    ratio = hits / len(req_tokens)
    if ratio >= 0.7:
        return ComponentScore(max_pts, max_pts, f"Matches required qualification ({required}).")
    if ratio >= 0.4:
        return ComponentScore(max_pts // 2, max_pts, f"Partially matches {required}.")
    return ComponentScore(0, max_pts, f"Education does not match {required}.")


def _score_industry_experience(
    candidate: Candidate,
    job: JobOpening,
    extracted: Optional[CandidateExtractedData],
) -> ComponentScore:
    max_pts = MAX_POINTS["industry_experience"]
    job_company = (job.company or "").strip().lower()
    department = (job.department or "").strip().lower()
    division = (job.division or "").strip().lower()

    prev_company_names: List[str] = []
    if extracted and isinstance(extracted.previous_companies, list):
        for item in extracted.previous_companies:
            if isinstance(item, dict) and item.get("name"):
                prev_company_names.append(str(item["name"]).lower())
    if candidate.current_company:
        prev_company_names.append(candidate.current_company.lower())

    if job_company:
        for name in prev_company_names:
            if job_company and (job_company in name or name in job_company):
                return ComponentScore(
                    max_pts, max_pts, f"Worked at {job.company} previously."
                )

    # Industry / department keyword overlap on past roles.
    haystacks: List[str] = []
    if candidate.current_designation:
        haystacks.append(candidate.current_designation.lower())
    if extracted and isinstance(extracted.previous_companies, list):
        for item in extracted.previous_companies:
            if isinstance(item, dict):
                if item.get("title"):
                    haystacks.append(str(item["title"]).lower())
                if item.get("name"):
                    haystacks.append(str(item["name"]).lower())

    needle_tokens = [
        t for t in re.split(r"[^a-z0-9]+", " ".join([department, division]))
        if len(t) > 3
    ]
    if not needle_tokens or not haystacks:
        return ComponentScore(
            max_pts // 2,
            max_pts,
            "Insufficient industry data — neutral score.",
        )

    hay = " ".join(haystacks)
    hits = sum(1 for tok in needle_tokens if tok in hay)
    if hits >= 2:
        return ComponentScore(
            7,
            max_pts,
            f"Past roles overlap with {job.department}.",
        )
    if hits == 1:
        return ComponentScore(
            4,
            max_pts,
            f"Some prior overlap with {job.department}.",
        )
    return ComponentScore(0, max_pts, "No clear industry overlap detected.")


def _score_gcc_qatar_experience(
    candidate: Candidate, job: JobOpening
) -> ComponentScore:
    max_pts = MAX_POINTS["gcc_qatar_experience"]
    loc = (job.location or "").lower()
    in_qatar = any(tok in loc for tok in QATAR_TOKENS)
    in_gcc = any(tok in loc for tok in GCC_TOKENS)

    qatar_y = candidate.qatar_experience_years or 0
    gcc_y = candidate.gcc_experience_years or 0

    if in_qatar:
        return _bucket_years(
            qatar_y or gcc_y / 2,
            max_pts,
            label="Qatar experience",
        )
    if in_gcc:
        return _bucket_years(gcc_y, max_pts, label="GCC experience")

    # Not a Gulf role.
    return ComponentScore(
        max_pts // 2 + 1,
        max_pts,
        "Role is outside the GCC — regional experience neutral.",
    )


def _bucket_years(years: float, max_pts: int, *, label: str) -> ComponentScore:
    if years >= 5:
        return ComponentScore(max_pts, max_pts, f"{years:g} years of {label}.")
    if years >= 3:
        return ComponentScore(
            int(round(max_pts * 0.8)), max_pts, f"{years:g} years of {label}."
        )
    if years >= 1:
        return ComponentScore(
            int(round(max_pts * 0.6)), max_pts, f"{years:g} years of {label}."
        )
    if years > 0:
        return ComponentScore(
            int(round(max_pts * 0.3)), max_pts, f"Under a year of {label}."
        )
    return ComponentScore(0, max_pts, f"No {label} recorded.")


def _score_salary_fit(
    candidate: Candidate, job: JobOpening
) -> ComponentScore:
    max_pts = MAX_POINTS["salary_fit"]
    expected = candidate.expected_salary
    s_min = job.salary_min
    s_max = job.salary_max

    if expected is None and s_min is None and s_max is None:
        return ComponentScore(
            max_pts // 2,
            max_pts,
            "Neither candidate nor job specified a salary — neutral.",
        )
    if expected is None:
        return ComponentScore(
            max_pts // 2,
            max_pts,
            "Candidate did not state an expected salary.",
        )
    if s_min is None and s_max is None:
        return ComponentScore(
            max_pts // 2,
            max_pts,
            "Job has no salary band published.",
        )

    lo = s_min or 0
    hi = s_max or (lo * 2 if lo else expected)

    if lo <= expected <= hi:
        return ComponentScore(
            max_pts,
            max_pts,
            f"Expected {expected:,} sits inside the {lo:,}–{hi:,} band.",
        )
    if expected < lo:
        return ComponentScore(
            max_pts - 2,
            max_pts,
            f"Expected {expected:,} is under the {lo:,} floor — budget friendly.",
        )
    # Over the cap.
    overshoot = (expected - hi) / hi if hi else 1.0
    if overshoot <= 0.10:
        return ComponentScore(
            max_pts - 4,
            max_pts,
            f"Expected {expected:,} is {overshoot * 100:.0f}% over the {hi:,} cap.",
        )
    if overshoot <= 0.25:
        return ComponentScore(
            max_pts - 7,
            max_pts,
            f"Expected {expected:,} is {overshoot * 100:.0f}% over the {hi:,} cap.",
        )
    return ComponentScore(
        0, max_pts, f"Expected {expected:,} is well above the {hi:,} cap."
    )


def _score_notice_period(
    candidate: Candidate, job: JobOpening
) -> ComponentScore:
    max_pts = MAX_POINTS["notice_period"]
    candidate_months = _notice_to_months(candidate.notice_period)
    preferred = job.notice_period_preference or ""
    preferred_months = _notice_to_months(preferred)

    if candidate_months is None:
        return ComponentScore(
            max_pts // 2, max_pts, "Candidate notice period not specified."
        )
    if not preferred:
        # No job preference — anything ≤ 2 months is fine.
        if candidate_months <= 1:
            return ComponentScore(max_pts, max_pts, "Available within a month.")
        if candidate_months <= 2:
            return ComponentScore(
                max_pts - 1,
                max_pts,
                f"Two-month notice; no preference set.",
            )
        return ComponentScore(
            max_pts - 3,
            max_pts,
            f"{candidate_months}-month notice; no preference set.",
        )
    if preferred_months is None:
        return ComponentScore(max_pts // 2, max_pts, "Couldn't parse the job preference.")

    diff = candidate_months - preferred_months
    if diff <= 0:
        return ComponentScore(max_pts, max_pts, "Meets or beats notice preference.")
    if diff == 1:
        return ComponentScore(max_pts - 2, max_pts, "Notice is one month longer than preferred.")
    if diff == 2:
        return ComponentScore(max_pts - 3, max_pts, "Notice is two months longer than preferred.")
    return ComponentScore(0, max_pts, f"Notice is {diff} months longer than preferred.")


def _score_visa_status(
    candidate: Candidate, job: JobOpening
) -> ComponentScore:
    max_pts = MAX_POINTS["visa_status"]
    requirement = (job.visa_requirement or "").strip().lower()
    status = (candidate.visa_status or "").strip().lower()

    if not requirement and not status:
        return ComponentScore(
            max_pts - 2, max_pts, "Neither side specified a visa requirement."
        )
    if not requirement:
        return ComponentScore(max_pts - 1, max_pts, "Job has no visa requirement.")
    if not status:
        return ComponentScore(0, max_pts, f"Candidate visa status not recorded ({requirement}).")

    # Heuristic match: look for shared keywords.
    req_tokens = {t for t in re.split(r"[^a-z0-9]+", requirement) if len(t) > 2}
    status_tokens = {t for t in re.split(r"[^a-z0-9]+", status) if len(t) > 2}
    overlap = req_tokens & status_tokens
    if overlap:
        return ComponentScore(
            max_pts,
            max_pts,
            f"Visa status matches requirement ({', '.join(sorted(overlap))}).",
        )
    if "transferable" in status or "noc" in status:
        return ComponentScore(
            max_pts - 1, max_pts, "Has a transferable visa / NOC available."
        )
    return ComponentScore(
        0,
        max_pts,
        f"Visa status '{candidate.visa_status}' does not match '{job.visa_requirement}'.",
    )


def _score_language_match(
    candidate: Candidate,
    job: JobOpening,
    extracted: Optional[CandidateExtractedData],
) -> ComponentScore:
    max_pts = MAX_POINTS["language_match"]
    required = _tokenize_csv(job.language_requirement)
    if not required:
        return ComponentScore(max_pts - 1, max_pts, "Job has no language requirement.")

    candidate_langs: Set[str] = set()
    if extracted and isinstance(extracted.languages, list):
        candidate_langs |= {str(l).strip().lower() for l in extracted.languages if l}
    if not candidate_langs:
        return ComponentScore(
            0, max_pts, "No languages recorded on the candidate."
        )

    matched = {lang for lang in required if lang in candidate_langs}
    if not matched:
        return ComponentScore(
            0,
            max_pts,
            f"Missing required languages: {', '.join(sorted(required))}.",
        )
    ratio = len(matched) / len(required)
    pts = int(round(ratio * max_pts))
    return ComponentScore(
        pts,
        max_pts,
        f"Speaks {len(matched)}/{len(required)} required languages.",
    )


# ---------------------------------------------------------------------------
# Tokenisers / shared helpers
# ---------------------------------------------------------------------------


def _tokenize_csv(value: Optional[str]) -> Set[str]:
    if not value:
        return set()
    return {
        tok.strip().lower()
        for tok in re.split(r"[,/;|\n]+", value)
        if tok.strip()
    }


def _tokenize_skills(value: Optional[str]) -> Set[str]:
    return _tokenize_csv(value)


def _candidate_skill_tokens(
    candidate: Candidate, extracted: Optional[CandidateExtractedData]
) -> Set[str]:
    tokens: Set[str] = set()
    if extracted and extracted.skills:
        tokens |= _tokenize_csv(extracted.skills)
    # Fall back to scanning the full extracted text for skill phrases.
    if extracted and extracted.full_text:
        tokens |= {w.strip().lower() for w in extracted.full_text.split() if len(w) > 2}
    if candidate.current_designation:
        tokens |= {
            t.strip().lower()
            for t in re.split(r"[\s,/]+", candidate.current_designation)
            if t.strip()
        }
    return tokens


def _education_haystack(
    candidate: Candidate, extracted: Optional[CandidateExtractedData]
) -> str:
    parts: List[str] = []
    if extracted and isinstance(extracted.education, list):
        for item in extracted.education:
            if isinstance(item, dict):
                for k in ("raw", "degree", "institution"):
                    val = item.get(k)
                    if val:
                        parts.append(str(val))
    return " ".join(parts)


_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _notice_to_months(text: Optional[str]) -> Optional[int]:
    """Convert a free-form notice-period string to whole months."""
    if not text:
        return None
    lowered = text.lower().strip()
    if "immediate" in lowered:
        return 0
    # "30 days", "2 weeks", "1 month", "two months", "60 days", etc.
    m = re.search(r"(\d+)\s*(day|week|month|year)s?", lowered)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit == "day":
            return max(0, round(n / 30))
        if unit == "week":
            return max(0, round(n / 4))
        if unit == "month":
            return n
        if unit == "year":
            return n * 12
    for word, value in _NUMBER_WORDS.items():
        if word in lowered:
            if "week" in lowered:
                return max(0, round(value / 4))
            if "day" in lowered:
                return max(0, round(value / 30))
            if "year" in lowered:
                return value * 12
            return value
    return None

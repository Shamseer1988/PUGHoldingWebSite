"""Offer-letter template rendering.

Substitutes ``{{token}}`` merge fields in a template body from the
offer / candidate / job context. Substitution happens when HR applies a
template (the rendered text is stored on ``OfferTracking.letter_body``
and stays editable), so the PDF renderer just prints the stored body.
"""
from __future__ import annotations

import re
from datetime import date
from typing import List, Optional, Tuple

from app.models.hr_ats import Candidate, JobOpening, OfferTracking

COMPANY_NAME = "PUG Holding"

# (token, human label) — surfaced in the builder so HR can insert fields.
MERGE_FIELDS: List[Tuple[str, str]] = [
    ("candidate_name", "Candidate full name"),
    ("candidate_email", "Candidate email"),
    ("position", "Position / role"),
    ("department", "Department"),
    ("company", "Company"),
    ("salary", "Monthly basic salary (formatted)"),
    ("allowances", "Allowances"),
    ("joining_date", "Joining date (formatted)"),
    ("probation_period", "Probation period"),
    ("reporting_manager", "Reporting manager"),
    ("work_location", "Work location"),
    ("offer_letter_number", "Offer letter number"),
    ("today", "Today's date (formatted)"),
]

_TOKEN_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def available_merge_fields() -> List[Tuple[str, str]]:
    return list(MERGE_FIELDS)


def _money(value: Optional[int]) -> str:
    return f"QAR {value:,.0f}" if value is not None else ""


def _fmt_date(value: Optional[date]) -> str:
    return value.strftime("%d %b %Y") if value is not None else ""


def build_context(
    *,
    offer: OfferTracking,
    candidate: Optional[Candidate],
    job: Optional[JobOpening],
) -> dict[str, str]:
    """Resolve every merge token to a string (missing → empty)."""
    company = (job.company if job and job.company else COMPANY_NAME) or COMPANY_NAME
    return {
        "candidate_name": (candidate.full_name if candidate else "") or "",
        "candidate_email": (candidate.email if candidate else "") or "",
        "position": offer.position or (job.title if job else "") or "",
        "department": (job.department if job else "") or "",
        "company": company,
        "salary": _money(offer.salary_offered),
        "allowances": offer.allowances or "",
        "joining_date": _fmt_date(offer.joining_date),
        "probation_period": offer.probation_period or "",
        "reporting_manager": offer.reporting_manager or "",
        "work_location": offer.work_location or (job.location if job else "") or "",
        "offer_letter_number": offer.offer_letter_number or "",
        "today": _fmt_date(date.today()),
    }


def render_template(
    body: str,
    *,
    offer: OfferTracking,
    candidate: Optional[Candidate],
    job: Optional[JobOpening],
) -> str:
    """Render a template body by substituting ``{{token}}`` fields.

    Unknown tokens are left untouched so a typo is visible rather than
    silently dropped.
    """
    ctx = build_context(offer=offer, candidate=candidate, job=job)

    def _sub(match: "re.Match[str]") -> str:
        token = match.group(1)
        return ctx[token] if token in ctx else match.group(0)

    return _TOKEN_RE.sub(_sub, body)

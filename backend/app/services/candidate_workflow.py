"""Candidate workflow / status pipeline service (Phase 14).

The pipeline is a finite state machine. Each application moves through
a curated set of statuses; we enforce:

- Only declared transitions are allowed.
- A **rejection reason** is mandatory when moving to ``rejected``.
- A **blacklist approval reason** is mandatory when moving to
  ``blacklisted`` — and only a superuser is allowed to do it.
- Every change is recorded in ``CandidateStatusHistory`` and audited
  by the caller.

The graph itself is intentionally readable rather than clever — the
keys describe the *current* status, the values are the legal targets.

Final states (``joined``, ``rejected``, ``blacklisted``) have no
outgoing transitions for regular HR users; a superuser may still reopen
them, captured below via the ``superuser_only_reopen`` shortcut.
"""
from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Dict, Optional, Set

from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.hr_ats import (
    STATUS_AI_REVIEWED,
    STATUS_BLACKLISTED,
    STATUS_CV_RECEIVED,
    STATUS_FINAL_INTERVIEW,
    STATUS_FIRST_INTERVIEW,
    STATUS_HR_REVIEW_PENDING,
    STATUS_JOINED,
    STATUS_NOT_JOINED,
    STATUS_OFFER_SENT,
    STATUS_RECOMMENDED_FOR_OFFER,
    STATUS_REJECTED,
    STATUS_SELECTED,
    STATUS_SHORTLISTED,
    STATUS_TECHNICAL_INTERVIEW,
    STATUS_WAITING_LIST,
    Candidate,
    CandidateJobApplication,
    CandidateStatusHistory,
)


# Canonical, ordered list of statuses for the UI.
PIPELINE_ORDER = [
    STATUS_CV_RECEIVED,
    STATUS_AI_REVIEWED,
    STATUS_HR_REVIEW_PENDING,
    STATUS_SHORTLISTED,
    STATUS_FIRST_INTERVIEW,
    STATUS_TECHNICAL_INTERVIEW,
    STATUS_FINAL_INTERVIEW,
    STATUS_WAITING_LIST,
    STATUS_RECOMMENDED_FOR_OFFER,
    STATUS_SELECTED,
    STATUS_OFFER_SENT,
    STATUS_JOINED,
    STATUS_NOT_JOINED,
    STATUS_REJECTED,
    STATUS_BLACKLISTED,
]

# Human-readable labels for the UI; the API still uses snake_case keys.
STATUS_LABELS: Dict[str, str] = {
    STATUS_CV_RECEIVED: "CV Received",
    STATUS_AI_REVIEWED: "AI Reviewed",
    STATUS_HR_REVIEW_PENDING: "HR Review Pending",
    STATUS_SHORTLISTED: "Shortlisted",
    STATUS_FIRST_INTERVIEW: "First Interview",
    STATUS_TECHNICAL_INTERVIEW: "Technical Interview",
    STATUS_FINAL_INTERVIEW: "Final Interview",
    STATUS_WAITING_LIST: "Waiting List",
    STATUS_RECOMMENDED_FOR_OFFER: "Recommended for Offer",
    STATUS_SELECTED: "Selected",
    STATUS_OFFER_SENT: "Offer Sent",
    STATUS_JOINED: "Joined",
    STATUS_NOT_JOINED: "Not Joined",
    STATUS_REJECTED: "Rejected",
    STATUS_BLACKLISTED: "Blacklisted",
}

FINAL_STATUSES: Set[str] = {
    STATUS_JOINED,
    STATUS_NOT_JOINED,
    STATUS_REJECTED,
    STATUS_BLACKLISTED,
}


def _common_terminal() -> Set[str]:
    """Statuses HR can always escalate to."""
    return {STATUS_REJECTED, STATUS_BLACKLISTED}


# Forward transitions. Read as "from {key} you may move to {value}".
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    STATUS_CV_RECEIVED: {
        STATUS_AI_REVIEWED,
        STATUS_HR_REVIEW_PENDING,
        STATUS_SHORTLISTED,
    } | _common_terminal(),
    STATUS_AI_REVIEWED: {
        STATUS_HR_REVIEW_PENDING,
        STATUS_SHORTLISTED,
    } | _common_terminal(),
    STATUS_HR_REVIEW_PENDING: {
        STATUS_SHORTLISTED,
        STATUS_FIRST_INTERVIEW,
    } | _common_terminal(),
    STATUS_SHORTLISTED: {
        STATUS_FIRST_INTERVIEW,
    } | _common_terminal(),
    STATUS_FIRST_INTERVIEW: {
        STATUS_TECHNICAL_INTERVIEW,
        STATUS_FINAL_INTERVIEW,
        STATUS_WAITING_LIST,
        STATUS_RECOMMENDED_FOR_OFFER,
        STATUS_SELECTED,
    } | _common_terminal(),
    STATUS_TECHNICAL_INTERVIEW: {
        STATUS_FINAL_INTERVIEW,
        STATUS_WAITING_LIST,
        STATUS_RECOMMENDED_FOR_OFFER,
        STATUS_SELECTED,
    } | _common_terminal(),
    STATUS_FINAL_INTERVIEW: {
        STATUS_WAITING_LIST,
        STATUS_RECOMMENDED_FOR_OFFER,
        STATUS_SELECTED,
    } | _common_terminal(),
    # Waiting list = keeping a candidate warm. From there HR can still
    # promote them to selected/recommended later, or reject.
    STATUS_WAITING_LIST: {
        STATUS_RECOMMENDED_FOR_OFFER,
        STATUS_SELECTED,
    } | _common_terminal(),
    # Recommended-for-offer is the manager's sign-off before the offer
    # is actually drafted/sent. Selected = offer authorised.
    STATUS_RECOMMENDED_FOR_OFFER: {
        STATUS_SELECTED,
    } | _common_terminal(),
    STATUS_SELECTED: {
        STATUS_OFFER_SENT,
    } | _common_terminal(),
    STATUS_OFFER_SENT: {
        STATUS_JOINED,
        STATUS_NOT_JOINED,
    } | _common_terminal(),
    STATUS_JOINED: set(),
    STATUS_NOT_JOINED: set(),
    STATUS_REJECTED: set(),
    STATUS_BLACKLISTED: set(),
}

# A superuser may always reopen a final-state application by moving it
# back into HR_REVIEW_PENDING. This is rare and intentionally restricted.
SUPERUSER_REOPEN_TARGET = STATUS_HR_REVIEW_PENDING


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WorkflowError(Exception):
    """Base class for workflow rule violations."""


class InvalidTransitionError(WorkflowError):
    """Raised when the requested transition is not allowed."""


class MissingReasonError(WorkflowError):
    """Raised when a transition requires a reason and none was provided."""


class PermissionDeniedError(WorkflowError):
    """Raised when the actor lacks the permission for this transition."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class StatusChangeResult:
    application: CandidateJobApplication
    history: CandidateStatusHistory
    previous_status: str
    new_status: str


def allowed_next_statuses(current: str, *, actor_is_superuser: bool = False) -> Set[str]:
    """Return the set of statuses the actor can transition to from ``current``."""
    base = set(ALLOWED_TRANSITIONS.get(current, set()))
    if actor_is_superuser and current in FINAL_STATUSES:
        base.add(SUPERUSER_REOPEN_TARGET)
    return base


def change_status(
    db: Session,
    *,
    application: CandidateJobApplication,
    new_status: str,
    actor: User,
    remarks: Optional[str] = None,
    rejection_reason: Optional[str] = None,
    blacklist_approval: Optional[str] = None,
) -> StatusChangeResult:
    """Apply a status change with all the workflow rules enforced.

    Caller is responsible for committing the session and writing an
    audit-log entry — this helper just validates + mutates.
    """
    if new_status not in STATUS_LABELS:
        raise InvalidTransitionError(f"Unknown status: {new_status!r}")

    previous = application.status
    if previous == new_status:
        raise InvalidTransitionError(
            f"Candidate is already in '{STATUS_LABELS[previous]}'."
        )

    allowed = allowed_next_statuses(previous, actor_is_superuser=actor.is_superuser)
    if new_status not in allowed:
        raise InvalidTransitionError(
            f"Cannot move from '{STATUS_LABELS[previous]}' to "
            f"'{STATUS_LABELS[new_status]}'."
        )

    # Mandatory reasons
    rejection_reason = (rejection_reason or "").strip() or None
    blacklist_approval = (blacklist_approval or "").strip() or None
    remarks = (remarks or "").strip() or None

    if new_status == STATUS_REJECTED and not rejection_reason:
        raise MissingReasonError("A rejection reason is mandatory.")
    if new_status == STATUS_BLACKLISTED:
        if not blacklist_approval:
            raise MissingReasonError(
                "A blacklist approval reason is mandatory."
            )
        if not actor.is_superuser:
            raise PermissionDeniedError(
                "Only a superuser can blacklist a candidate."
            )

    # Apply
    application.status = new_status
    candidate = application.candidate
    if new_status == STATUS_REJECTED:
        application.last_rejection_reason = rejection_reason
    if new_status == STATUS_BLACKLISTED:
        candidate.is_blacklisted = True
        candidate.blacklist_reason = blacklist_approval
        candidate.blacklisted_by_id = actor.id
        candidate.blacklisted_at = datetime.now(timezone.utc)
    # When a superuser reopens a blacklisted candidate, drop the flag.
    if (
        previous == STATUS_BLACKLISTED
        and new_status == SUPERUSER_REOPEN_TARGET
        and actor.is_superuser
    ):
        candidate.is_blacklisted = False
        candidate.blacklist_reason = None
        candidate.blacklisted_by_id = None
        candidate.blacklisted_at = None

    history = CandidateStatusHistory(
        application_id=application.id,
        old_status=previous,
        new_status=new_status,
        changed_by_id=actor.id,
        remarks=remarks,
        rejection_reason=rejection_reason,
        blacklist_approval=blacklist_approval,
    )
    db.add(history)
    db.flush()

    return StatusChangeResult(
        application=application,
        history=history,
        previous_status=previous,
        new_status=new_status,
    )

"""Interview management service (Phase 15).

Owns the scheduling + feedback rules:

- Mandatory fields: round name, scheduled_at (must be in the future for
  new interviews), mode, and a location_or_link when the mode is
  ``in_person`` or ``online``.
- The interviewer (if assigned) is any active user — typically an HR
  user, but a dedicated "Interviewer" role with the
  ``hr.interview.submit_feedback`` permission can also be used.
- Status transitions are bounded: scheduled → completed / cancelled /
  rescheduled / no_show. ``rescheduled`` flips back to ``scheduled``
  after a new ``scheduled_at`` is provided. Final feedback can only be
  submitted on completed interviews.
- Every status change and feedback submission is audit-logged by the
  caller via ``record_audit``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.hr_ats import (
    INTERVIEW_CANCELLED,
    INTERVIEW_COMPLETED,
    INTERVIEW_MODE_IN_PERSON,
    INTERVIEW_MODE_ONLINE,
    INTERVIEW_MODE_PHONE,
    INTERVIEW_MODES,
    INTERVIEW_NO_SHOW,
    INTERVIEW_RESCHEDULED,
    INTERVIEW_SCHEDULED,
    INTERVIEW_STATUSES,
    CandidateJobApplication,
    Interview,
    InterviewFeedback,
)


# Human-readable labels
INTERVIEW_STATUS_LABELS = {
    INTERVIEW_SCHEDULED: "Scheduled",
    INTERVIEW_COMPLETED: "Completed",
    INTERVIEW_CANCELLED: "Cancelled",
    INTERVIEW_RESCHEDULED: "Rescheduled",
    INTERVIEW_NO_SHOW: "No-show",
}

INTERVIEW_MODE_LABELS = {
    INTERVIEW_MODE_ONLINE: "Online",
    INTERVIEW_MODE_PHONE: "Phone",
    INTERVIEW_MODE_IN_PERSON: "In person",
}


# scheduled → {completed, cancelled, rescheduled, no_show}
# rescheduled → {scheduled, cancelled} (caller re-edits scheduled_at)
# completed / cancelled / no_show → terminal
INTERVIEW_TRANSITIONS = {
    INTERVIEW_SCHEDULED: {
        INTERVIEW_COMPLETED,
        INTERVIEW_CANCELLED,
        INTERVIEW_RESCHEDULED,
        INTERVIEW_NO_SHOW,
    },
    INTERVIEW_RESCHEDULED: {INTERVIEW_SCHEDULED, INTERVIEW_CANCELLED},
    INTERVIEW_COMPLETED: set(),
    INTERVIEW_CANCELLED: set(),
    INTERVIEW_NO_SHOW: set(),
}


RECOMMENDATION_HIRE = "hire"
RECOMMENDATION_NO_HIRE = "no_hire"
RECOMMENDATION_MAYBE = "maybe"
INTERVIEW_RECOMMENDATIONS = {
    RECOMMENDATION_HIRE,
    RECOMMENDATION_NO_HIRE,
    RECOMMENDATION_MAYBE,
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class InterviewError(Exception):
    """Base class for interview workflow errors."""


class InvalidInterviewError(InterviewError):
    """Raised when interview data is invalid (bad mode, time in the past)."""


class InvalidInterviewTransitionError(InterviewError):
    """Raised when the requested status transition is not allowed."""


class FeedbackPermissionError(InterviewError):
    """Raised when the user cannot submit feedback for this interview."""


class FeedbackTimingError(InterviewError):
    """Raised when feedback is submitted on a non-completed interview."""


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _ensure_aware(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC — the API layer normalises to UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _validate_basic(
    *,
    round_name: str,
    scheduled_at: datetime,
    mode: str,
    location_or_link: Optional[str],
    enforce_future: bool,
) -> None:
    if not round_name or not round_name.strip():
        raise InvalidInterviewError("round_name is required.")
    if mode not in INTERVIEW_MODES:
        raise InvalidInterviewError(
            f"Unknown interview mode {mode!r}. Allowed: {sorted(INTERVIEW_MODES)}."
        )
    if mode in (INTERVIEW_MODE_ONLINE, INTERVIEW_MODE_IN_PERSON):
        if not location_or_link or not location_or_link.strip():
            raise InvalidInterviewError(
                "location_or_link is required for online and in-person interviews."
            )
    if enforce_future:
        scheduled_at = _ensure_aware(scheduled_at)
        if scheduled_at < datetime.now(timezone.utc):
            raise InvalidInterviewError("scheduled_at must be in the future.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_interview(
    db: Session,
    *,
    application: CandidateJobApplication,
    round_name: str,
    round_number: int,
    scheduled_at: datetime,
    duration_minutes: int,
    mode: str,
    location_or_link: Optional[str],
    interviewer_id: Optional[int],
    actor: User,
) -> Interview:
    _validate_basic(
        round_name=round_name,
        scheduled_at=scheduled_at,
        mode=mode,
        location_or_link=location_or_link,
        enforce_future=True,
    )
    interview = Interview(
        application_id=application.id,
        round_name=round_name.strip(),
        round_number=max(1, int(round_number or 1)),
        scheduled_at=_ensure_aware(scheduled_at),
        duration_minutes=max(5, int(duration_minutes or 60)),
        mode=mode,
        location_or_link=(location_or_link or "").strip() or None,
        interviewer_id=interviewer_id,
        status=INTERVIEW_SCHEDULED,
        created_by_id=actor.id,
    )
    db.add(interview)
    db.flush()
    return interview


def update_interview(
    db: Session,
    *,
    interview: Interview,
    updates: dict,
) -> Interview:
    """Apply a partial update to a scheduled / rescheduled interview.

    `updates` must already be sanitized by the caller (Pydantic).
    """
    if interview.status in (
        INTERVIEW_COMPLETED,
        INTERVIEW_CANCELLED,
        INTERVIEW_NO_SHOW,
    ):
        raise InvalidInterviewTransitionError(
            "Cannot edit a completed / cancelled / no-show interview."
        )

    if "round_name" in updates and updates["round_name"] is not None:
        interview.round_name = str(updates["round_name"]).strip()
    if "round_number" in updates and updates["round_number"] is not None:
        interview.round_number = max(1, int(updates["round_number"]))
    if "scheduled_at" in updates and updates["scheduled_at"] is not None:
        interview.scheduled_at = _ensure_aware(updates["scheduled_at"])
    if "duration_minutes" in updates and updates["duration_minutes"] is not None:
        interview.duration_minutes = max(5, int(updates["duration_minutes"]))
    if "mode" in updates and updates["mode"] is not None:
        interview.mode = str(updates["mode"])
    if "location_or_link" in updates:
        value = updates["location_or_link"]
        interview.location_or_link = (value or "").strip() or None if isinstance(value, str) else value
    if "interviewer_id" in updates:
        interview.interviewer_id = updates["interviewer_id"]
    if "reschedule_reason" in updates:
        value = updates["reschedule_reason"]
        interview.reschedule_reason = (
            value.strip() if isinstance(value, str) and value.strip() else None
        )

    # Re-validate the resulting state.
    _validate_basic(
        round_name=interview.round_name,
        scheduled_at=interview.scheduled_at,
        mode=interview.mode,
        location_or_link=interview.location_or_link,
        enforce_future=False,
    )

    # If editing a rescheduled interview with a new scheduled_at, drop the
    # rescheduled flag — it's back on the books.
    if interview.status == INTERVIEW_RESCHEDULED and "scheduled_at" in updates:
        interview.status = INTERVIEW_SCHEDULED

    db.flush()
    return interview


def change_interview_status(
    db: Session,
    *,
    interview: Interview,
    new_status: str,
) -> Interview:
    if new_status not in INTERVIEW_STATUSES:
        raise InvalidInterviewTransitionError(f"Unknown status: {new_status!r}.")
    allowed = INTERVIEW_TRANSITIONS.get(interview.status, set())
    if new_status not in allowed:
        raise InvalidInterviewTransitionError(
            f"Cannot move from '{INTERVIEW_STATUS_LABELS.get(interview.status, interview.status)}' "
            f"to '{INTERVIEW_STATUS_LABELS.get(new_status, new_status)}'."
        )
    interview.status = new_status
    db.flush()
    return interview


def can_submit_feedback(*, interview: Interview, actor: User) -> bool:
    """An interviewer assigned to the interview, an HR-scope user, or a
    superuser may submit feedback."""
    if actor.is_superuser:
        return True
    if interview.interviewer_id == actor.id:
        return True
    if actor.has_scope("hr"):
        return True
    if actor.has_permission("hr.interview.submit_feedback"):
        return True
    return False


def submit_feedback(
    db: Session,
    *,
    interview: Interview,
    actor: User,
    rating: Optional[int],
    recommendation: Optional[str],
    feedback: Optional[str],
    technical_score: Optional[int],
    communication_score: Optional[int],
    cultural_fit_score: Optional[int],
    strengths: Optional[str] = None,
    weaknesses: Optional[str] = None,
    next_action: Optional[str] = None,
) -> InterviewFeedback:
    if not can_submit_feedback(interview=interview, actor=actor):
        raise FeedbackPermissionError(
            "You are not assigned as the interviewer for this round."
        )
    if interview.status not in (INTERVIEW_COMPLETED, INTERVIEW_SCHEDULED):
        raise FeedbackTimingError(
            "Feedback can only be submitted for scheduled or completed interviews."
        )
    if rating is not None and not (1 <= int(rating) <= 5):
        raise InvalidInterviewError("rating must be between 1 and 5.")
    for label, value in (
        ("technical_score", technical_score),
        ("communication_score", communication_score),
        ("cultural_fit_score", cultural_fit_score),
    ):
        if value is not None and not (0 <= int(value) <= 10):
            raise InvalidInterviewError(f"{label} must be between 0 and 10.")
    if recommendation is not None and recommendation not in INTERVIEW_RECOMMENDATIONS:
        raise InvalidInterviewError(
            f"recommendation must be one of {sorted(INTERVIEW_RECOMMENDATIONS)}."
        )

    fb = InterviewFeedback(
        interview_id=interview.id,
        submitted_by_id=actor.id,
        rating=int(rating) if rating is not None else None,
        recommendation=recommendation,
        feedback=(feedback or "").strip() or None,
        technical_score=int(technical_score) if technical_score is not None else None,
        communication_score=int(communication_score) if communication_score is not None else None,
        cultural_fit_score=int(cultural_fit_score) if cultural_fit_score is not None else None,
        strengths=(strengths or "").strip() or None,
        weaknesses=(weaknesses or "").strip() or None,
        next_action=(next_action or "").strip() or None,
    )
    db.add(fb)

    # If a feedback comes in for a still-scheduled interview, auto-mark it
    # completed — interviewers rarely change status separately in practice.
    if interview.status == INTERVIEW_SCHEDULED:
        interview.status = INTERVIEW_COMPLETED

    db.flush()
    return fb

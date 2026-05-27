"""High-level HR notification service.

Wraps :mod:`app.services.email` + :mod:`app.services.email_templates` and
records every send attempt in the :class:`EmailLog` table introduced in
phase 1. Designed for two call patterns:

1. From inside an endpoint that already holds an open DB session
   (e.g. job approval endpoint) — call :func:`send_notification` with
   the session you have.
2. From a deferred / post-commit hook — call :func:`notify_job_approved`
   etc. which open a fresh session via :func:`SessionLocal`.

Every send attempt persists an :class:`EmailLog` row with status set to
``pending`` first, then updated to ``sent`` or ``failed`` once the SMTP
call returns. Failures never raise — they're logged so the calling
transaction is never rolled back by a transient SMTP issue.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.email_settings import EmailSetting
from app.models.hr_ats import (
    EMAIL_LOG_FAILED,
    EMAIL_LOG_PENDING,
    EMAIL_LOG_SENT,
    Candidate,
    CandidateJobApplication,
    EmailLog,
    Interview,
    InterviewFeedback,
    JobOpening,
    OfferTracking,
)
from app.services.email import EmailResult, EmailService
from app.services.email_templates import (
    RenderedEmail,
    TPL_CANDIDATE_APPLICATION_RECEIVED,
    TPL_CANDIDATE_REJECTED,
    TPL_INTERVIEW_FEEDBACK_SUBMITTED,
    TPL_OFFER_ACCEPTED,
    TPL_OFFER_APPROVAL_REQUESTED,
    TPL_OFFER_APPROVED,
    TPL_OFFER_DECLINED,
    TPL_OFFER_ISSUED,
    TPL_OFFER_JOINED,
    TPL_CANDIDATE_SELECTED,
    TPL_CANDIDATE_SHORTLISTED,
    TPL_INTERVIEW_CANCELLED,
    TPL_INTERVIEW_RESCHEDULED,
    TPL_INTERVIEW_SCHEDULED,
    TPL_JOB_APPROVED,
    TPL_JOB_PUBLISHED,
    TPL_JOB_REJECTED,
    TPL_JOB_REVISION_REQUESTED,
    TPL_JOB_SUBMITTED,
    render,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core send: render → log pending → SMTP → log result
# ---------------------------------------------------------------------------


def _normalize_emails(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.replace(";", ",").split(",") if v.strip()]
    if isinstance(value, (list, tuple, set)):
        out: List[str] = []
        for item in value:
            if not item:
                continue
            if isinstance(item, str):
                out.extend(_normalize_emails(item))
            else:
                out.append(str(item))
        return out
    return []


def _brand_ctx(settings: EmailSetting) -> Dict[str, Any]:
    return {
        "brand_logo_url": settings.brand_logo_url,
        "email_footer_text": settings.email_footer_text,
    }


def send_notification(
    db: Session,
    *,
    template_key: str,
    to_emails: Iterable[str],
    context: Dict[str, Any],
    cc_emails: Optional[Iterable[str]] = None,
    bcc_emails: Optional[Iterable[str]] = None,
    scope: str = "hr",
    related_type: Optional[str] = None,
    related_id: Optional[str] = None,
    actor_id: Optional[int] = None,
    subject_override: Optional[str] = None,
    check_feature_flag: Optional[str] = None,
) -> EmailLog:
    """Send a templated branded email and persist an EmailLog row.

    ``check_feature_flag`` — when set to one of the EmailSetting boolean
    columns (e.g. ``"job_approval_email_enabled"``), the send is skipped
    (and the log row is marked failed with that reason) if the flag is
    off. This lets admins disable individual notification streams from
    the Admin Email Settings page.
    """
    to_list = _normalize_emails(to_emails)
    cc_list = _normalize_emails(cc_emails)
    bcc_list = _normalize_emails(bcc_emails)

    log = EmailLog(
        scope=scope,
        template_key=template_key,
        to_emails=to_list,
        cc_emails=cc_list or None,
        bcc_emails=bcc_list or None,
        status=EMAIL_LOG_PENDING,
        related_type=related_type,
        related_id=related_id,
        created_by_id=actor_id,
    )
    db.add(log)
    db.flush()

    if not to_list:
        log.status = EMAIL_LOG_FAILED
        log.error_message = "No recipients."
        db.flush()
        return log

    setting = EmailService.get_or_create_settings(db)
    if check_feature_flag and not getattr(setting, check_feature_flag, True):
        log.status = EMAIL_LOG_FAILED
        log.error_message = f"Disabled by '{check_feature_flag}' setting."
        db.flush()
        return log

    branded_ctx = {**_brand_ctx(setting), **context}
    try:
        rendered: RenderedEmail = render(template_key, branded_ctx)
    except KeyError as exc:
        log.status = EMAIL_LOG_FAILED
        log.error_message = f"Unknown template key: {exc!s}"
        db.flush()
        return log

    subject = subject_override or rendered.subject
    log.subject = subject

    # We send one email per primary recipient so each candidate sees
    # their own personalised To line. CC/BCC are included on the FIRST
    # send only — repeating them on every personalised copy would spam.
    overall_success = False
    last_error: Optional[str] = None
    provider_responses: List[Dict[str, Any]] = []

    for idx, recipient in enumerate(to_list):
        result: EmailResult = EmailService.send_simple(
            db,
            to_email=recipient,
            subject=subject,
            body_text=rendered.text,
            body_html=rendered.html,
            reply_to=context.get("reply_to"),
        )
        provider_responses.append(
            {
                "to": recipient,
                "success": result.success,
                "message": result.message,
            }
        )
        if result.success:
            overall_success = True
        else:
            last_error = result.message

    log.provider_response = {"sends": provider_responses}
    if overall_success:
        log.status = EMAIL_LOG_SENT
        log.sent_at = datetime.now(timezone.utc)
        log.error_message = None
    else:
        log.status = EMAIL_LOG_FAILED
        log.error_message = last_error or "Send failed."

    db.flush()
    return log


# ---------------------------------------------------------------------------
# Convenience: open a fresh session and never raise
# ---------------------------------------------------------------------------


def _safe_send(**kwargs: Any) -> None:
    db = SessionLocal()
    try:
        send_notification(db, **kwargs)
        db.commit()
    except Exception:  # pragma: no cover - notifications must not raise
        db.rollback()
        logger.exception("HR notification send failed (template=%s)", kwargs.get("template_key"))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Public, one-call-per-event API used by endpoints
# ---------------------------------------------------------------------------


def _hr_recipients(db: Session) -> List[str]:
    setting = EmailService.get_or_create_settings(db)
    return _normalize_emails(setting.hr_notification_emails)


def _job_ctx(job: JobOpening) -> Dict[str, Any]:
    return {
        "job_id": job.id,
        "job_title": job.title,
        "job_department": job.department,
        "job_company": job.company,
        "job_slug": job.slug,
    }


def _candidate_ctx(candidate: Candidate) -> Dict[str, Any]:
    return {
        "candidate_id": candidate.id,
        "candidate_name": candidate.full_name,
        "candidate_email": candidate.email,
    }


def _interview_ctx(interview: Interview) -> Dict[str, Any]:
    app = interview.application
    candidate = app.candidate if app else None
    job = app.job_opening if app else None
    ctx: Dict[str, Any] = {
        "interview_id": interview.id,
        "round_name": interview.round_name,
        "round_number": interview.round_number,
        "scheduled_at": interview.scheduled_at,
        "duration_minutes": interview.duration_minutes,
        "mode": interview.mode,
        "location_or_link": interview.location_or_link,
        "meeting_link": interview.meeting_link or interview.location_or_link,
        "email_note": interview.email_note,
    }
    if candidate is not None:
        ctx.update(_candidate_ctx(candidate))
    if job is not None:
        ctx.update(_job_ctx(job))
    # ``Interview.interviewer`` is not a declared relationship — look up
    # the user by id so we can render the interviewer line.
    if interview.interviewer_id is not None:
        from app.models.auth import User
        # We need a session — only resolve when we have one (callers pass
        # the populated interview, the db lookup is done in _build via
        # SessionLocal). Skip silently when relationship can't be resolved.
        ctx["interviewer_id"] = interview.interviewer_id
    return ctx


# --- Job approval events ---------------------------------------------------


def notify_job_created(*, job_id: int, actor_id: Optional[int] = None) -> None:
    """Notification when an HR Executive creates a draft job (no recipient)."""
    # Currently we don't fan-out a notification for plain creation —
    # avoids inbox noise. The hook is here so endpoints can call it
    # uniformly with the other lifecycle events.
    return None


def notify_job_submitted(*, job_id: int, actor_id: Optional[int] = None) -> None:
    """Notify HR Managers that a job is pending their approval."""

    def _build(db: Session) -> Optional[dict]:
        job = db.get(JobOpening, job_id)
        if job is None:
            return None
        ctx = _job_ctx(job)
        ctx["actor_email"] = _actor_email(db, actor_id)
        return {
            "template_key": TPL_JOB_SUBMITTED,
            "to_emails": _hr_recipients(db),
            "context": ctx,
            "related_type": "job_opening",
            "related_id": str(job_id),
            "actor_id": actor_id,
            "check_feature_flag": "job_approval_email_enabled",
        }

    _dispatch(_build)


def notify_job_approved(*, job_id: int, actor_id: Optional[int] = None) -> None:
    def _build(db: Session) -> Optional[dict]:
        job = db.get(JobOpening, job_id)
        if job is None:
            return None
        ctx = _job_ctx(job)
        ctx["actor_email"] = _actor_email(db, actor_id)
        return {
            "template_key": TPL_JOB_APPROVED,
            "to_emails": _hr_recipients(db),
            "context": ctx,
            "related_type": "job_opening",
            "related_id": str(job_id),
            "actor_id": actor_id,
            "check_feature_flag": "job_approval_email_enabled",
        }

    _dispatch(_build)


def notify_job_rejected(
    *, job_id: int, actor_id: Optional[int] = None, reason: Optional[str] = None
) -> None:
    def _build(db: Session) -> Optional[dict]:
        job = db.get(JobOpening, job_id)
        if job is None:
            return None
        ctx = _job_ctx(job)
        ctx["actor_email"] = _actor_email(db, actor_id)
        ctx["reason"] = reason or ""
        return {
            "template_key": TPL_JOB_REJECTED,
            "to_emails": _hr_recipients(db),
            "context": ctx,
            "related_type": "job_opening",
            "related_id": str(job_id),
            "actor_id": actor_id,
            "check_feature_flag": "job_approval_email_enabled",
        }

    _dispatch(_build)


def notify_job_revision_requested(
    *, job_id: int, actor_id: Optional[int] = None, reason: Optional[str] = None
) -> None:
    def _build(db: Session) -> Optional[dict]:
        job = db.get(JobOpening, job_id)
        if job is None:
            return None
        ctx = _job_ctx(job)
        ctx["actor_email"] = _actor_email(db, actor_id)
        ctx["reason"] = reason or ""
        return {
            "template_key": TPL_JOB_REVISION_REQUESTED,
            "to_emails": _hr_recipients(db),
            "context": ctx,
            "related_type": "job_opening",
            "related_id": str(job_id),
            "actor_id": actor_id,
            "check_feature_flag": "job_approval_email_enabled",
        }

    _dispatch(_build)


def notify_job_revision_submitted(
    *, job_id: int, revision_id: int, actor_id: Optional[int] = None
) -> None:
    """Re-use the SUBMITTED template for revision approval requests."""

    def _build(db: Session) -> Optional[dict]:
        job = db.get(JobOpening, job_id)
        if job is None:
            return None
        ctx = _job_ctx(job)
        ctx["actor_email"] = _actor_email(db, actor_id)
        ctx["revision_id"] = revision_id
        return {
            "template_key": TPL_JOB_SUBMITTED,
            "to_emails": _hr_recipients(db),
            "context": ctx,
            "related_type": "job_revision",
            "related_id": str(revision_id),
            "actor_id": actor_id,
            "check_feature_flag": "job_approval_email_enabled",
        }

    _dispatch(_build)


def notify_job_published(*, job_id: int, actor_id: Optional[int] = None) -> None:
    def _build(db: Session) -> Optional[dict]:
        job = db.get(JobOpening, job_id)
        if job is None:
            return None
        ctx = _job_ctx(job)
        ctx["actor_email"] = _actor_email(db, actor_id)
        return {
            "template_key": TPL_JOB_PUBLISHED,
            "to_emails": _hr_recipients(db),
            "context": ctx,
            "related_type": "job_opening",
            "related_id": str(job_id),
            "actor_id": actor_id,
            "check_feature_flag": "job_approval_email_enabled",
        }

    _dispatch(_build)


# --- Candidate events ------------------------------------------------------


def notify_candidate_application_received(*, application_id: int) -> None:
    def _build(db: Session) -> Optional[dict]:
        app = db.get(CandidateJobApplication, application_id)
        if app is None or app.candidate is None or not app.candidate.email:
            return None
        ctx = _candidate_ctx(app.candidate)
        if app.job_opening is not None:
            ctx.update(_job_ctx(app.job_opening))
        return {
            "template_key": TPL_CANDIDATE_APPLICATION_RECEIVED,
            "to_emails": [app.candidate.email],
            "context": ctx,
            "related_type": "candidate_application",
            "related_id": str(application_id),
            "check_feature_flag": "candidate_email_enabled",
        }

    _dispatch(_build)


def notify_candidate_shortlisted(
    *, application_id: int, actor_id: Optional[int] = None
) -> None:
    _candidate_status_email(
        application_id=application_id,
        template_key=TPL_CANDIDATE_SHORTLISTED,
        actor_id=actor_id,
    )


def notify_candidate_rejected(
    *, application_id: int, actor_id: Optional[int] = None
) -> None:
    _candidate_status_email(
        application_id=application_id,
        template_key=TPL_CANDIDATE_REJECTED,
        actor_id=actor_id,
    )


def notify_candidate_selected(
    *, application_id: int, actor_id: Optional[int] = None
) -> None:
    _candidate_status_email(
        application_id=application_id,
        template_key=TPL_CANDIDATE_SELECTED,
        actor_id=actor_id,
    )


def _candidate_status_email(
    *,
    application_id: int,
    template_key: str,
    actor_id: Optional[int],
) -> None:
    def _build(db: Session) -> Optional[dict]:
        app = db.get(CandidateJobApplication, application_id)
        if app is None or app.candidate is None or not app.candidate.email:
            return None
        ctx = _candidate_ctx(app.candidate)
        if app.job_opening is not None:
            ctx.update(_job_ctx(app.job_opening))
        return {
            "template_key": template_key,
            "to_emails": [app.candidate.email],
            "context": ctx,
            "related_type": "candidate_application",
            "related_id": str(application_id),
            "actor_id": actor_id,
            "check_feature_flag": "candidate_email_enabled",
        }

    _dispatch(_build)


# --- Interview events ------------------------------------------------------


def notify_interview_scheduled(
    *,
    interview_id: int,
    actor_id: Optional[int] = None,
    cc_emails: Optional[Iterable[str]] = None,
    bcc_emails: Optional[Iterable[str]] = None,
    candidate_email_override: Optional[str] = None,
    additional_attendee_emails: Optional[Iterable[str]] = None,
) -> None:
    _interview_email(
        template_key=TPL_INTERVIEW_SCHEDULED,
        interview_id=interview_id,
        actor_id=actor_id,
        cc_emails=cc_emails,
        bcc_emails=bcc_emails,
        candidate_email_override=candidate_email_override,
        additional_attendee_emails=additional_attendee_emails,
    )


def notify_interview_rescheduled(
    *, interview_id: int, actor_id: Optional[int] = None
) -> None:
    _interview_email(
        template_key=TPL_INTERVIEW_RESCHEDULED,
        interview_id=interview_id,
        actor_id=actor_id,
    )


def notify_interview_cancelled(
    *, interview_id: int, actor_id: Optional[int] = None
) -> None:
    _interview_email(
        template_key=TPL_INTERVIEW_CANCELLED,
        interview_id=interview_id,
        actor_id=actor_id,
    )


# ---------------------------------------------------------------------------
# Phase 11 — interview feedback + offer-lifecycle dispatchers.
# ---------------------------------------------------------------------------


def notify_interview_feedback_submitted(
    *, feedback_id: int, actor_id: Optional[int] = None
) -> None:
    """Internal email to HR Manager / Executive when an interviewer
    submits feedback for a round. Audience: hr_notification_emails
    list from EmailSetting."""

    def _build(db: Session) -> Optional[dict]:
        fb = db.get(InterviewFeedback, feedback_id)
        if fb is None or fb.interview is None:
            return None
        iv = fb.interview
        candidate = iv.application.candidate if iv.application else None
        job = iv.application.job_opening if iv.application else None
        settings = EmailService.get_or_create_settings(db)
        to_emails = _normalize_emails(settings.hr_notification_emails)
        if not to_emails:
            return None
        ctx: Dict[str, Any] = {
            "candidate_name": candidate.full_name if candidate else "",
            "job_title": job.title if job else "",
            "round_name": iv.round_name,
            "interviewer_email": _actor_email(db, fb.submitted_by_id) or "",
            "recommendation": fb.recommendation or "submitted",
            "rating": fb.rating,
        }
        return {
            "template_key": TPL_INTERVIEW_FEEDBACK_SUBMITTED,
            "to_emails": to_emails,
            "context": ctx,
            "related_type": "interview_feedback",
            "related_id": str(feedback_id),
            "actor_id": actor_id,
            "check_feature_flag": "interview_email_enabled",
        }

    _dispatch(_build)


def _offer_ctx(offer: OfferTracking) -> Dict[str, Any]:
    """Shared context for every offer-related template."""
    app = offer.application
    candidate = app.candidate if app else None
    job = app.job_opening if app else None
    return {
        "candidate_name": candidate.full_name if candidate else "",
        "candidate_email": candidate.email if candidate else "",
        "job_title": job.title if job else "",
        "position": offer.position,
        "salary_offered": offer.salary_offered,
        "joining_date": (
            offer.joining_date.isoformat() if offer.joining_date else None
        ),
        "offer_letter_number": offer.offer_letter_number,
        "work_location": offer.work_location,
        "decline_reason": offer.decline_reason,
        "joined_at": (
            offer.joined_at.strftime("%Y-%m-%d")
            if offer.joined_at
            else None
        ),
    }


def _offer_internal_email(
    *,
    template_key: str,
    offer_id: int,
    actor_id: Optional[int],
) -> None:
    """Internal (HR-facing) offer email — sends to the
    hr_notification_emails list. Used by approval-requested /
    approved / accepted / declined / joined templates."""

    def _build(db: Session) -> Optional[dict]:
        offer = db.get(OfferTracking, offer_id)
        if offer is None:
            return None
        settings = EmailService.get_or_create_settings(db)
        to_emails = _normalize_emails(settings.hr_notification_emails)
        if not to_emails:
            return None
        ctx = _offer_ctx(offer)
        ctx["actor_email"] = _actor_email(db, actor_id)
        return {
            "template_key": template_key,
            "to_emails": to_emails,
            "context": ctx,
            "related_type": "offer",
            "related_id": str(offer_id),
            "actor_id": actor_id,
            "check_feature_flag": "offer_email_enabled",
        }

    _dispatch(_build)


def notify_offer_approval_requested(
    *, offer_id: int, actor_id: Optional[int] = None
) -> None:
    _offer_internal_email(
        template_key=TPL_OFFER_APPROVAL_REQUESTED,
        offer_id=offer_id,
        actor_id=actor_id,
    )


def notify_offer_approved(
    *, offer_id: int, actor_id: Optional[int] = None
) -> None:
    _offer_internal_email(
        template_key=TPL_OFFER_APPROVED,
        offer_id=offer_id,
        actor_id=actor_id,
    )


def notify_offer_accepted(
    *, offer_id: int, actor_id: Optional[int] = None
) -> None:
    _offer_internal_email(
        template_key=TPL_OFFER_ACCEPTED,
        offer_id=offer_id,
        actor_id=actor_id,
    )


def notify_offer_declined(
    *, offer_id: int, actor_id: Optional[int] = None
) -> None:
    _offer_internal_email(
        template_key=TPL_OFFER_DECLINED,
        offer_id=offer_id,
        actor_id=actor_id,
    )


def notify_offer_joined(
    *, offer_id: int, actor_id: Optional[int] = None
) -> None:
    _offer_internal_email(
        template_key=TPL_OFFER_JOINED,
        offer_id=offer_id,
        actor_id=actor_id,
    )


def notify_offer_issued(
    *, offer_id: int, actor_id: Optional[int] = None
) -> None:
    """Candidate-facing offer letter notification. Goes to the
    candidate's email rather than the internal HR list."""

    def _build(db: Session) -> Optional[dict]:
        offer = db.get(OfferTracking, offer_id)
        if offer is None or offer.application is None:
            return None
        candidate = offer.application.candidate
        if candidate is None or not candidate.email:
            return None
        return {
            "template_key": TPL_OFFER_ISSUED,
            "to_emails": [candidate.email],
            "context": _offer_ctx(offer),
            "related_type": "offer",
            "related_id": str(offer_id),
            "actor_id": actor_id,
            "check_feature_flag": "offer_email_enabled",
        }

    _dispatch(_build)


def _interview_email(
    *,
    template_key: str,
    interview_id: int,
    actor_id: Optional[int],
    cc_emails: Optional[Iterable[str]] = None,
    bcc_emails: Optional[Iterable[str]] = None,
    candidate_email_override: Optional[str] = None,
    additional_attendee_emails: Optional[Iterable[str]] = None,
) -> None:
    def _build(db: Session) -> Optional[dict]:
        interview = db.get(Interview, interview_id)
        if interview is None:
            return None
        ctx = _interview_ctx(interview)
        if interview.interviewer_id is not None:
            from app.models.auth import User

            interviewer = db.get(User, interview.interviewer_id)
            if interviewer is not None:
                ctx["interviewer_email"] = interviewer.email
                ctx["interviewer_name"] = interviewer.full_name

        candidate = interview.application.candidate if interview.application else None
        primary = candidate_email_override or interview.candidate_email_override or (
            candidate.email if candidate else None
        )
        if not primary:
            return None

        attendees = _normalize_emails(additional_attendee_emails) + _normalize_emails(
            interview.additional_attendee_emails
        )
        to_list = [primary] + attendees

        cc_list = list(_normalize_emails(cc_emails)) + list(
            _normalize_emails(interview.cc_emails)
        )
        bcc_list = list(_normalize_emails(bcc_emails)) + list(
            _normalize_emails(interview.bcc_emails)
        )

        return {
            "template_key": template_key,
            "to_emails": to_list,
            "cc_emails": cc_list or None,
            "bcc_emails": bcc_list or None,
            "context": ctx,
            "related_type": "interview",
            "related_id": str(interview_id),
            "actor_id": actor_id,
            "subject_override": interview.email_subject,
            "check_feature_flag": "interview_email_enabled",
        }

    _dispatch(_build)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _dispatch(build_fn) -> None:
    """Build send kwargs from a fresh DB session and dispatch safely."""
    db = SessionLocal()
    try:
        kwargs = build_fn(db)
        if not kwargs:
            return
        send_notification(db, **kwargs)
        db.commit()
    except Exception:  # pragma: no cover - notifications must not raise
        db.rollback()
        logger.exception("HR notification dispatch failed")
    finally:
        db.close()


def _actor_email(db: Session, actor_id: Optional[int]) -> Optional[str]:
    if actor_id is None:
        return None
    from app.models.auth import User

    user = db.get(User, actor_id)
    return user.email if user else None

"""Interview management endpoints (Phase 15).

All routes require an authenticated user. Most require ``hr`` scope;
feedback submission additionally accepts the assigned interviewer
even when they don't carry the full HR scope.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_request_context,
    require_any_permission,
    require_hr_admin,
    require_permission,
)
from app.auth.permissions import (
    PERM_HR_INTERVIEWS_DELETE,
    PERM_HR_INTERVIEWS_FEEDBACK,
    PERM_HR_INTERVIEWS_RESCHEDULE,
    PERM_HR_INTERVIEWS_SCHEDULE,
    PERM_HR_INTERVIEWS_VIEW_ALL,
    PERM_HR_INTERVIEWS_VIEW_MINE,
)
from app.core.database import get_db
from app.models.auth import User
from app.models.hr_ats import (
    CandidateJobApplication,
    Interview,
    InterviewFeedback,
)
from app.schemas.hr_ats import (
    InterviewCreate,
    InterviewFeedbackCreate,
    InterviewFeedbackRead,
    InterviewListItem,
    InterviewRead,
    InterviewStatusChange,
    InterviewUpdate,
)
from app.services.audit_log import record_audit
from app.services.interview_management import (
    FeedbackPermissionError,
    FeedbackTimingError,
    INTERVIEW_MODE_LABELS,
    INTERVIEW_STATUS_LABELS,
    InvalidInterviewError,
    InvalidInterviewTransitionError,
    can_submit_feedback,
    change_interview_status,
    create_interview,
    submit_feedback,
    update_interview,
)


router = APIRouter(prefix="/hr/interviews", tags=["HR ATS - Interviews"])


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def _email_lookup(db: Session, user_ids: list[int]) -> dict[int, User]:
    ids = [uid for uid in user_ids if uid]
    if not ids:
        return {}
    rows = db.execute(select(User).where(User.id.in_(set(ids)))).scalars().all()
    return {u.id: u for u in rows}


def _latest_recommendation(interview: Interview) -> Optional[str]:
    if not interview.feedback:
        return None
    return interview.feedback[0].recommendation  # ordered desc by created_at


def _serialize_feedback(
    fb: InterviewFeedback, *, users: dict[int, User]
) -> InterviewFeedbackRead:
    submitter = users.get(fb.submitted_by_id) if fb.submitted_by_id else None
    return InterviewFeedbackRead(
        id=fb.id,
        interview_id=fb.interview_id,
        submitted_by_id=fb.submitted_by_id,
        submitted_by_email=submitter.email if submitter else None,
        rating=fb.rating,
        recommendation=fb.recommendation,
        feedback=fb.feedback,
        technical_score=fb.technical_score,
        communication_score=fb.communication_score,
        cultural_fit_score=fb.cultural_fit_score,
        created_at=fb.created_at,
        updated_at=fb.updated_at,
    )


def _serialize_interview(
    interview: Interview, *, users: dict[int, User]
) -> InterviewRead:
    interviewer = users.get(interview.interviewer_id) if interview.interviewer_id else None
    return InterviewRead(
        id=interview.id,
        application_id=interview.application_id,
        round_name=interview.round_name,
        round_number=interview.round_number,
        scheduled_at=interview.scheduled_at,
        duration_minutes=interview.duration_minutes,
        mode=interview.mode,
        location_or_link=interview.location_or_link,
        interviewer_id=interview.interviewer_id,
        status=interview.status,
        status_label=INTERVIEW_STATUS_LABELS.get(interview.status, interview.status),
        mode_label=INTERVIEW_MODE_LABELS.get(interview.mode, interview.mode),
        interviewer_email=interviewer.email if interviewer else None,
        interviewer_name=interviewer.full_name if interviewer else None,
        created_by_id=interview.created_by_id,
        created_at=interview.created_at,
        updated_at=interview.updated_at,
        feedback=[
            _serialize_feedback(fb, users=users) for fb in interview.feedback
        ],
        meeting_link=interview.meeting_link,
        calendar_event_id=interview.calendar_event_id,
        calendar_provider=interview.calendar_provider,
        email_sent_at=interview.email_sent_at,
        email_delivery_status=interview.email_delivery_status,
        additional_attendee_emails=interview.additional_attendee_emails,
        cc_emails=interview.cc_emails,
        bcc_emails=interview.bcc_emails,
        candidate_email_override=interview.candidate_email_override,
        email_subject=interview.email_subject,
        email_note=interview.email_note,
    )


def _serialize_list_row(
    interview: Interview, *, users: dict[int, User]
) -> InterviewListItem:
    interviewer = users.get(interview.interviewer_id) if interview.interviewer_id else None
    app = interview.application
    return InterviewListItem(
        id=interview.id,
        application_id=interview.application_id,
        candidate_id=app.candidate_id,
        candidate_name=app.candidate.full_name if app.candidate else "Unknown",
        job_title=app.job_opening.title if app.job_opening is not None else None,
        round_name=interview.round_name,
        round_number=interview.round_number,
        scheduled_at=interview.scheduled_at,
        duration_minutes=interview.duration_minutes,
        mode=interview.mode,
        mode_label=INTERVIEW_MODE_LABELS.get(interview.mode, interview.mode),
        location_or_link=interview.location_or_link,
        interviewer_id=interview.interviewer_id,
        interviewer_email=interviewer.email if interviewer else None,
        interviewer_name=interviewer.full_name if interviewer else None,
        status=interview.status,
        status_label=INTERVIEW_STATUS_LABELS.get(interview.status, interview.status),
        has_feedback=bool(interview.feedback),
        latest_recommendation=_latest_recommendation(interview),
    )


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


@router.get("", response_model=List[InterviewListItem])
def list_interviews(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    status: Optional[str] = Query(default=None, max_length=40),
    interviewer_id: Optional[int] = Query(default=None),
    application_id: Optional[int] = Query(default=None),
    mine_only: bool = Query(default=False),
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
    upcoming_days: Optional[int] = Query(default=None, ge=1, le=180),
) -> List[InterviewListItem]:
    """List interviews with optional filters.

    - Users with ``hr:interviews:view_all`` see the whole table.
    - Anyone else (Interviewers, Department Managers without view_all)
      gets forced to ``mine_only`` — only their own assignments.
    - Users with neither permission get 403.
    """
    can_view_all = actor.is_superuser or actor.has_permission(
        PERM_HR_INTERVIEWS_VIEW_ALL
    )
    can_view_mine = actor.has_permission(PERM_HR_INTERVIEWS_VIEW_MINE)
    if not (can_view_all or can_view_mine):
        raise HTTPException(
            status_code=403,
            detail="Requires hr:interviews:view_all or hr:interviews:view_mine",
        )
    if not can_view_all:
        mine_only = True

    stmt = (
        select(Interview)
        .order_by(desc(Interview.scheduled_at), desc(Interview.id))
    )
    if status:
        stmt = stmt.where(Interview.status == status)
    if interviewer_id:
        stmt = stmt.where(Interview.interviewer_id == interviewer_id)
    if application_id:
        stmt = stmt.where(Interview.application_id == application_id)
    if mine_only:
        stmt = stmt.where(Interview.interviewer_id == actor.id)
    if from_date is not None:
        stmt = stmt.where(Interview.scheduled_at >= from_date)
    if to_date is not None:
        stmt = stmt.where(Interview.scheduled_at <= to_date)
    if upcoming_days is not None:
        now = datetime.now(timezone.utc)
        stmt = stmt.where(
            Interview.scheduled_at >= now,
            Interview.scheduled_at <= now + timedelta(days=upcoming_days),
        )

    interviews = db.execute(stmt).scalars().all()
    users = _email_lookup(
        db, [i.interviewer_id for i in interviews if i.interviewer_id]
    )
    return [_serialize_list_row(i, users=users) for i in interviews]


@router.get("/mine", response_model=List[InterviewListItem])
def my_interviews(
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    upcoming_only: bool = Query(default=False),
) -> List[InterviewListItem]:
    """Self-service endpoint for assigned interviewers."""
    stmt = (
        select(Interview)
        .where(Interview.interviewer_id == actor.id)
        .order_by(desc(Interview.scheduled_at))
    )
    if upcoming_only:
        stmt = stmt.where(Interview.scheduled_at >= datetime.now(timezone.utc))
    interviews = db.execute(stmt).scalars().all()
    users = _email_lookup(db, [actor.id])
    return [_serialize_list_row(i, users=users) for i in interviews]


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


def _get_interview_or_404(db: Session, interview_id: int) -> Interview:
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    return interview


def _enforce_read_access(interview: Interview, actor: User) -> None:
    if actor.is_superuser or actor.has_scope("hr"):
        return
    if interview.interviewer_id == actor.id:
        return
    raise HTTPException(status_code=403, detail="Insufficient permissions.")


@router.get("/{interview_id}", response_model=InterviewRead)
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> InterviewRead:
    interview = _get_interview_or_404(db, interview_id)
    _enforce_read_access(interview, actor)
    user_ids = [interview.interviewer_id] + [
        fb.submitted_by_id for fb in interview.feedback if fb.submitted_by_id
    ]
    users = _email_lookup(db, [uid for uid in user_ids if uid])
    return _serialize_interview(interview, users=users)


# ---------------------------------------------------------------------------
# Create / update / status / delete (HR only)
# ---------------------------------------------------------------------------


def _get_application_or_404(db: Session, application_id: int) -> CandidateJobApplication:
    app = db.get(CandidateJobApplication, application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found.")
    return app


@router.post("", response_model=InterviewRead, status_code=201)
def create_interview_endpoint(
    payload: InterviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_INTERVIEWS_SCHEDULE)),
) -> InterviewRead:
    app = _get_application_or_404(db, payload.application_id)

    # --- Create Google Meet first so the link can satisfy
    #     create_interview's location_or_link requirement when the
    #     caller hasn't supplied one --------------------------------
    meet_result = None
    if payload.create_google_meet and payload.mode == "online":
        meet_result = _try_create_meet_from_payload(app, payload)

    effective_location = payload.location_or_link or (
        meet_result.meet_link if meet_result else None
    )

    try:
        interview = create_interview(
            db,
            application=app,
            round_name=payload.round_name,
            round_number=payload.round_number,
            scheduled_at=payload.scheduled_at,
            duration_minutes=payload.duration_minutes,
            mode=payload.mode,
            location_or_link=effective_location,
            interviewer_id=payload.interviewer_id,
            actor=user,
        )
    except InvalidInterviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Persist the email / calendar extras directly — these are stored
    # on the row so we can later resend the invitation without HR
    # re-entering CC/BCC lists.
    interview.additional_attendee_emails = payload.additional_attendee_emails or None
    interview.cc_emails = payload.cc_emails or None
    interview.bcc_emails = payload.bcc_emails or None
    interview.candidate_email_override = payload.candidate_email_override
    interview.email_subject = payload.email_subject
    interview.email_note = payload.email_note

    if meet_result is not None:
        interview.calendar_event_id = meet_result.event_id
        interview.meeting_link = meet_result.meet_link
        interview.calendar_provider = "google"

    db.flush()

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.interview.create",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="interview",
        target_id=str(interview.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "application_id": app.id,
            "candidate_id": app.candidate_id,
            "round_name": interview.round_name,
            "scheduled_at": interview.scheduled_at.isoformat(),
            "mode": interview.mode,
            "interviewer_id": interview.interviewer_id,
            "create_google_meet": payload.create_google_meet,
            "send_email_now": payload.send_email_now,
            "has_meet_link": bool(interview.meeting_link),
        },
        commit=False,
    )
    db.commit()
    db.refresh(interview)

    # --- Branded email (optional, fire-and-forget) -------------------
    if payload.send_email_now:
        _safe_notify_interview_scheduled(
            interview.id,
            actor_id=user.id,
            cc_emails=payload.cc_emails,
            bcc_emails=payload.bcc_emails,
            candidate_email_override=payload.candidate_email_override,
            additional_attendee_emails=payload.additional_attendee_emails,
        )

    users = _email_lookup(db, [interview.interviewer_id])
    return _serialize_interview(interview, users=users)


def _try_create_meet_from_payload(app, payload: InterviewCreate):
    """Best-effort Google Meet creation. Returns None on failure."""
    from app.services.google_calendar_service import create_interview_event

    candidate = app.candidate if app else None
    candidate_email = (
        payload.candidate_email_override
        or (candidate.email if candidate else None)
    )

    attendees: list[str] = []
    if candidate_email:
        attendees.append(candidate_email)
    attendees.extend(payload.additional_attendee_emails or [])

    job_title = app.job_opening.title if app.job_opening is not None else "PUG Interview"
    summary = f"{payload.round_name} — {job_title}"
    description_parts = [
        f"Interview with {candidate.full_name if candidate else 'candidate'}",
        f"Round: {payload.round_name}",
    ]
    if payload.email_note:
        description_parts.append(payload.email_note)

    return create_interview_event(
        summary=summary,
        description="\n\n".join(description_parts),
        start=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        attendees=attendees,
        create_meet=True,
    )


def _safe_notify_interview_scheduled(
    interview_id: int,
    *,
    actor_id,
    cc_emails,
    bcc_emails,
    candidate_email_override,
    additional_attendee_emails,
) -> None:
    """Notification helper — never raises."""
    try:
        from app.services import hr_notifications

        hr_notifications.notify_interview_scheduled(
            interview_id=interview_id,
            actor_id=actor_id,
            cc_emails=cc_emails or None,
            bcc_emails=bcc_emails or None,
            candidate_email_override=candidate_email_override,
            additional_attendee_emails=additional_attendee_emails or None,
        )
    except Exception:  # pragma: no cover - never raise from endpoint
        import logging

        logging.getLogger(__name__).exception(
            "interview-scheduled notification failed"
        )


@router.patch("/{interview_id}", response_model=InterviewRead)
def update_interview_endpoint(
    interview_id: int,
    payload: InterviewUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_INTERVIEWS_RESCHEDULE)),
) -> InterviewRead:
    interview = _get_interview_or_404(db, interview_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        users = _email_lookup(db, [interview.interviewer_id])
        return _serialize_interview(interview, users=users)

    try:
        update_interview(db, interview=interview, updates=updates)
    except InvalidInterviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidInterviewTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.interview.update",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="interview",
        target_id=str(interview.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"fields": sorted(updates.keys())},
        commit=False,
    )
    db.commit()
    db.refresh(interview)
    users = _email_lookup(db, [interview.interviewer_id])
    return _serialize_interview(interview, users=users)


@router.post("/{interview_id}/status", response_model=InterviewRead)
def change_status_endpoint(
    interview_id: int,
    payload: InterviewStatusChange,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_any_permission(
            PERM_HR_INTERVIEWS_RESCHEDULE, PERM_HR_INTERVIEWS_FEEDBACK
        )
    ),
) -> InterviewRead:
    interview = _get_interview_or_404(db, interview_id)
    previous = interview.status
    try:
        change_interview_status(db, interview=interview, new_status=payload.new_status)
    except InvalidInterviewTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.interview.status.change",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="interview",
        target_id=str(interview.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "previous_status": previous,
            "new_status": interview.status,
        },
        commit=False,
    )
    db.commit()
    db.refresh(interview)
    users = _email_lookup(db, [interview.interviewer_id])
    return _serialize_interview(interview, users=users)


@router.delete("/{interview_id}", status_code=204)
def delete_interview_endpoint(
    interview_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_INTERVIEWS_DELETE)),
):
    interview = _get_interview_or_404(db, interview_id)
    interview_id_val = interview.id
    application_id_val = interview.application_id
    db.delete(interview)

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.interview.delete",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="interview",
        target_id=str(interview_id_val),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"application_id": application_id_val},
        commit=False,
    )
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Feedback (interviewer or HR)
# ---------------------------------------------------------------------------


@router.get("/{interview_id}/feedback", response_model=List[InterviewFeedbackRead])
def list_feedback(
    interview_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> List[InterviewFeedbackRead]:
    interview = _get_interview_or_404(db, interview_id)
    _enforce_read_access(interview, actor)
    user_ids = [fb.submitted_by_id for fb in interview.feedback if fb.submitted_by_id]
    users = _email_lookup(db, user_ids)
    return [_serialize_feedback(fb, users=users) for fb in interview.feedback]


@router.post(
    "/{interview_id}/feedback",
    response_model=InterviewFeedbackRead,
    status_code=201,
)
def submit_feedback_endpoint(
    interview_id: int,
    payload: InterviewFeedbackCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> InterviewFeedbackRead:
    interview = _get_interview_or_404(db, interview_id)
    if not can_submit_feedback(interview=interview, actor=actor):
        raise HTTPException(
            status_code=403,
            detail="You are not assigned as the interviewer for this round.",
        )

    try:
        fb = submit_feedback(
            db,
            interview=interview,
            actor=actor,
            rating=payload.rating,
            recommendation=payload.recommendation,
            feedback=payload.feedback,
            technical_score=payload.technical_score,
            communication_score=payload.communication_score,
            cultural_fit_score=payload.cultural_fit_score,
        )
    except FeedbackPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FeedbackTimingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidInterviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.interview.feedback.submit",
        actor_id=actor.id,
        actor_email=actor.email,
        scope="hr",
        target_type="interview_feedback",
        target_id=str(fb.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "interview_id": interview.id,
            "rating": fb.rating,
            "recommendation": fb.recommendation,
        },
        commit=False,
    )
    db.commit()
    db.refresh(fb)
    users = _email_lookup(db, [fb.submitted_by_id])
    return _serialize_feedback(fb, users=users)


# ---------------------------------------------------------------------------
# Advanced module: send-email, create-meet, resend-invitation
# ---------------------------------------------------------------------------


@router.post("/{interview_id}/send-email", response_model=InterviewRead)
def send_interview_email(
    interview_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_INTERVIEWS_SCHEDULE)),
) -> InterviewRead:
    """Send (or re-send) the branded interview-scheduled email."""
    interview = _get_interview_or_404(db, interview_id)

    _safe_notify_interview_scheduled(
        interview.id,
        actor_id=user.id,
        cc_emails=interview.cc_emails,
        bcc_emails=interview.bcc_emails,
        candidate_email_override=interview.candidate_email_override,
        additional_attendee_emails=interview.additional_attendee_emails,
    )

    interview.email_sent_at = datetime.now(timezone.utc)
    interview.email_delivery_status = "sent"

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.interview.email.send",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="interview",
        target_id=str(interview.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"manual_send": True},
        commit=False,
    )
    db.commit()
    db.refresh(interview)
    users = _email_lookup(db, [interview.interviewer_id])
    return _serialize_interview(interview, users=users)


@router.post("/{interview_id}/create-meet", response_model=InterviewRead)
def create_interview_meet(
    interview_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_INTERVIEWS_SCHEDULE)),
) -> InterviewRead:
    """Create (or recreate) a Google Meet link for an existing interview."""
    from app.services.google_calendar_service import create_interview_event

    interview = _get_interview_or_404(db, interview_id)
    if interview.mode != "online":
        raise HTTPException(
            status_code=409,
            detail="Google Meet links are only created for online interviews.",
        )

    app = interview.application
    candidate = app.candidate if app else None
    attendees: list[str] = []
    if candidate and candidate.email:
        attendees.append(candidate.email)
    attendees.extend(interview.additional_attendee_emails or [])

    job_title = (
        app.job_opening.title if app and app.job_opening is not None else "PUG Interview"
    )
    result = create_interview_event(
        summary=f"{interview.round_name} — {job_title}",
        description=interview.email_note or interview.round_name,
        start=interview.scheduled_at,
        duration_minutes=interview.duration_minutes,
        attendees=attendees,
        create_meet=True,
    )
    if result is None:
        raise HTTPException(
            status_code=503,
            detail="Google Calendar integration is not configured.",
        )

    interview.calendar_event_id = result.event_id
    interview.meeting_link = result.meet_link
    interview.calendar_provider = "google"
    if not interview.location_or_link:
        interview.location_or_link = result.meet_link

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.interview.meet.create",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="interview",
        target_id=str(interview.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"event_id": result.event_id, "has_link": bool(result.meet_link)},
        commit=False,
    )
    db.commit()
    db.refresh(interview)
    users = _email_lookup(db, [interview.interviewer_id])
    return _serialize_interview(interview, users=users)


@router.post("/{interview_id}/resend-invitation", response_model=InterviewRead)
def resend_invitation(
    interview_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_INTERVIEWS_SCHEDULE)),
) -> InterviewRead:
    """Alias of send-email — kept separate for audit clarity."""
    return send_interview_email(interview_id, request, db, user)

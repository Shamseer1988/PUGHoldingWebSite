"""HR-facing assessment template + invite endpoints (Phase 2).

This is the *internal* side of the assessment workflow — HR creates
and edits templates, sends/cancels invites, and reviews submissions.

The candidate-facing side (token verify, fetch questions, submit
answers) lives in :mod:`app.api.endpoints.public_assessments`.

Permissions:

  * ``hr:assessments:manage`` — write / send / cancel
  * ``hr:assessments:view``   — read templates + submissions

Every write action writes an ``audit_logs`` row with
``scope="hr"`` so HR audit / compliance can trace which user issued
or cancelled an invite.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_request_context,
    require_hr_admin,
    require_permission,
)
from app.auth.permissions import (
    PERM_HR_ASSESSMENTS_MANAGE,
    PERM_HR_ASSESSMENTS_VIEW,
)
from app.core.database import get_db
from app.models.auth import User
from app.models.hr_assessment import (
    Assessment,
    AssessmentInvite,
    AssessmentSubmission,
)
from app.models.hr_ats import CandidateJobApplication
from app.schemas.hr_assessment import (
    AssessmentCreate,
    AssessmentInviteRead,
    AssessmentInviteSend,
    AssessmentList,
    AssessmentQuestionCreate,
    AssessmentQuestionRead,
    AssessmentQuestionUpdate,
    AssessmentRead,
    AssessmentSubmissionRead,
    AssessmentSummary,
    AssessmentUpdate,
)
from app.services import assessment_service as svc
from app.services.audit_log import record_audit
from app.services.hr_notifications import notify_assessment_invite_sent


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/hr/assessments",
    tags=["HR ATS - Assessments"],
    dependencies=[Depends(require_hr_admin)],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _audit(
    db: Session,
    actor: User,
    request: Request,
    *,
    action: str,
    target_id: Optional[str],
    details: Optional[dict] = None,
) -> None:
    """Single helper so every write in this file logs consistently."""
    ctx = get_request_context(request)
    record_audit(
        db,
        action=action,
        actor_id=actor.id,
        actor_email=actor.email,
        scope="hr",
        target_type="assessment",
        target_id=target_id,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details=details,
        commit=False,
    )


def _to_read(db: Session, assessment: Assessment) -> AssessmentRead:
    """Build the full AssessmentRead with counts populated."""
    qc, total_points, ic, sc = svc.assessment_counts(db, assessment.id)
    data = AssessmentRead.model_validate(assessment).model_dump()
    data["total_points"] = total_points
    data["invite_count"] = ic
    data["submission_count"] = sc
    return AssessmentRead(**data)


def _to_summary(db: Session, assessment: Assessment) -> AssessmentSummary:
    qc, _tp, ic, sc = svc.assessment_counts(db, assessment.id)
    data = AssessmentSummary.model_validate(assessment).model_dump()
    data["question_count"] = qc
    data["invite_count"] = ic
    data["submission_count"] = sc
    return AssessmentSummary(**data)


def _handle_service_error(exc: svc.AssessmentError) -> HTTPException:
    """Map the service exceptions to clean HTTP responses."""
    if isinstance(exc, svc.AssessmentNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, svc.AssessmentLocked):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, svc.AssessmentValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    # Fallthrough — let unexpected service errors surface as 500.
    return HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=AssessmentList)
def list_assessments(
    job_opening_id: Optional[int] = Query(default=None, ge=1),
    is_active: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_HR_ASSESSMENTS_VIEW)),
) -> AssessmentList:
    items_models = svc.list_assessments(
        db, job_opening_id=job_opening_id, is_active=is_active
    )
    items = [_to_summary(db, a) for a in items_models]
    return AssessmentList(items=items, total=len(items))


@router.get("/{assessment_id}", response_model=AssessmentRead)
def get_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_HR_ASSESSMENTS_VIEW)),
) -> AssessmentRead:
    try:
        assessment = svc.get_assessment(db, assessment_id)
    except svc.AssessmentError as exc:
        raise _handle_service_error(exc) from exc
    return _to_read(db, assessment)


@router.post("", response_model=AssessmentRead, status_code=201)
def create_assessment(
    payload: AssessmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_ASSESSMENTS_MANAGE)),
) -> AssessmentRead:
    try:
        assessment = svc.create_assessment(db, payload=payload, actor_id=actor.id)
    except svc.AssessmentError as exc:
        raise _handle_service_error(exc) from exc

    _audit(
        db,
        actor,
        request,
        action="hr.assessment.create",
        target_id=str(assessment.id),
        details={
            "job_opening_id": assessment.job_opening_id,
            "title": assessment.title,
            "question_count": len(assessment.questions),
        },
    )
    db.commit()
    db.refresh(assessment)
    return _to_read(db, assessment)


@router.patch("/{assessment_id}", response_model=AssessmentRead)
def update_assessment(
    assessment_id: int,
    payload: AssessmentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_ASSESSMENTS_MANAGE)),
) -> AssessmentRead:
    try:
        assessment = svc.update_assessment(
            db, assessment_id=assessment_id, payload=payload
        )
    except svc.AssessmentError as exc:
        raise _handle_service_error(exc) from exc

    _audit(
        db,
        actor,
        request,
        action="hr.assessment.update",
        target_id=str(assessment.id),
        details=payload.model_dump(exclude_unset=True),
    )
    db.commit()
    db.refresh(assessment)
    return _to_read(db, assessment)


@router.delete(
    "/{assessment_id}", status_code=204, response_class=Response
)
def delete_assessment(
    assessment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_ASSESSMENTS_MANAGE)),
) -> Response:
    try:
        svc.delete_assessment(db, assessment_id=assessment_id)
    except svc.AssessmentError as exc:
        raise _handle_service_error(exc) from exc

    _audit(
        db,
        actor,
        request,
        action="hr.assessment.delete",
        target_id=str(assessment_id),
    )
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Question helpers (nested under /{assessment_id}/questions)
# ---------------------------------------------------------------------------


@router.post(
    "/{assessment_id}/questions",
    response_model=AssessmentQuestionRead,
    status_code=201,
)
def add_question(
    assessment_id: int,
    payload: AssessmentQuestionCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_ASSESSMENTS_MANAGE)),
) -> AssessmentQuestionRead:
    try:
        question = svc.add_question(
            db, assessment_id=assessment_id, payload=payload
        )
    except svc.AssessmentError as exc:
        raise _handle_service_error(exc) from exc

    _audit(
        db,
        actor,
        request,
        action="hr.assessment.question.add",
        target_id=str(assessment_id),
        details={"question_id": question.id, "text": question.text[:120]},
    )
    db.commit()
    db.refresh(question)
    return question


@router.patch(
    "/{assessment_id}/questions/{question_id}",
    response_model=AssessmentQuestionRead,
)
def update_question(
    assessment_id: int,
    question_id: int,
    payload: AssessmentQuestionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_ASSESSMENTS_MANAGE)),
) -> AssessmentQuestionRead:
    try:
        question = svc.update_question(
            db, question_id=question_id, payload=payload
        )
    except svc.AssessmentError as exc:
        raise _handle_service_error(exc) from exc

    if question.assessment_id != assessment_id:
        raise HTTPException(
            status_code=404,
            detail="Question does not belong to that assessment.",
        )

    _audit(
        db,
        actor,
        request,
        action="hr.assessment.question.update",
        target_id=str(assessment_id),
        details={
            "question_id": question_id,
            "fields": list(payload.model_dump(exclude_unset=True).keys()),
        },
    )
    db.commit()
    db.refresh(question)
    return question


@router.delete(
    "/{assessment_id}/questions/{question_id}",
    status_code=204,
    response_class=Response,
)
def delete_question(
    assessment_id: int,
    question_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_ASSESSMENTS_MANAGE)),
) -> Response:
    try:
        svc.delete_question(db, question_id=question_id)
    except svc.AssessmentError as exc:
        raise _handle_service_error(exc) from exc

    _audit(
        db,
        actor,
        request,
        action="hr.assessment.question.delete",
        target_id=str(assessment_id),
        details={"question_id": question_id},
    )
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Invites — send / cancel / read
# ---------------------------------------------------------------------------


@router.post(
    "/{assessment_id}/invites",
    response_model=AssessmentInviteRead,
    status_code=201,
)
def send_invite(
    assessment_id: int,
    payload: AssessmentInviteSend,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_ASSESSMENTS_MANAGE)),
) -> AssessmentInviteRead:
    """Create (or refresh) an invite for a candidate, mark it sent.

    The email send itself is dispatched in a follow-up commit
    (Slice 3 of Phase 2) — for now the endpoint flips the row to
    ``sent`` so the rest of the workflow can be exercised end-to-end
    against the DB. HR sees the token in the response and can copy
    the link manually until the email pipeline lands.
    """
    # If application_id supplied, confirm the application actually
    # belongs to (candidate_id, the job that owns the assessment).
    if payload.application_id is not None:
        app = db.get(CandidateJobApplication, payload.application_id)
        if app is None or app.candidate_id != payload.candidate_id:
            raise HTTPException(
                status_code=400,
                detail="application_id does not match candidate_id.",
            )

    try:
        invite = svc.create_or_refresh_invite(
            db,
            assessment_id=assessment_id,
            candidate_id=payload.candidate_id,
            application_id=payload.application_id,
            sent_by_id=actor.id,
            expires_at=payload.expires_at,
        )
        invite = svc.mark_invite_sent(db, invite.id)
    except svc.AssessmentError as exc:
        raise _handle_service_error(exc) from exc

    _audit(
        db,
        actor,
        request,
        action="hr.assessment.invite.sent",
        target_id=str(assessment_id),
        details={
            "invite_id": invite.id,
            "candidate_id": invite.candidate_id,
            "application_id": invite.application_id,
            "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
        },
    )
    db.commit()
    db.refresh(invite)

    # Email dispatch happens *after* commit — ``_dispatch`` opens
    # its own session and swallows errors, so a flaky SMTP can't
    # roll back the invite the operator already requested.
    try:
        notify_assessment_invite_sent(invite_id=invite.id)
    except Exception:  # pragma: no cover — notifier must never raise
        logger.exception(
            "Failed to dispatch assessment-invite email for invite %s",
            invite.id,
        )
    return invite


@router.post(
    "/invites/{invite_id}/cancel",
    response_model=AssessmentInviteRead,
)
def cancel_invite(
    invite_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_ASSESSMENTS_MANAGE)),
) -> AssessmentInviteRead:
    try:
        invite = svc.cancel_invite(db, invite_id)
    except svc.AssessmentError as exc:
        raise _handle_service_error(exc) from exc

    _audit(
        db,
        actor,
        request,
        action="hr.assessment.invite.cancelled",
        target_id=str(invite.assessment_id),
        details={"invite_id": invite_id},
    )
    db.commit()
    db.refresh(invite)
    return invite


@router.get(
    "/invites/{invite_id}",
    response_model=AssessmentInviteRead,
)
def get_invite(
    invite_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_HR_ASSESSMENTS_VIEW)),
) -> AssessmentInviteRead:
    invite = db.get(AssessmentInvite, invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found.")
    return invite


@router.get(
    "/invites/{invite_id}/submission",
    response_model=AssessmentSubmissionRead,
)
def get_submission(
    invite_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_HR_ASSESSMENTS_VIEW)),
) -> AssessmentSubmissionRead:
    invite = db.get(AssessmentInvite, invite_id)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found.")
    if invite.submission is None:
        raise HTTPException(
            status_code=404,
            detail="No submission yet — candidate hasn't started.",
        )
    return invite.submission

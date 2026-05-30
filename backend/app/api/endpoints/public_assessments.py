"""Candidate-facing assessment endpoints (Phase 2, public surface).

Three endpoints, all rooted at ``/api/v1/assessments``:

* ``POST /{token}/verify`` — candidate enters DOB / email / mobile;
  on match the backend returns a short-lived session JWT plus the
  submit deadline (computed from time_limit, if any). Rate-limited
  per-IP to defend against brute-forcing the identity check on a
  captured token URL.
* ``GET  /me``             — fetches the form (questions + choices
  *without* the ``is_correct`` flag). Bearer token from
  ``/verify``.
* ``POST /me/submit``      — submits the full answer set, auto-
  scores, returns the candidate-visible ack (score / max_score /
  pass-fail).

The session JWT carries:
  * ``sub``      = candidate_id
  * ``token``    = the invite token (so a token rotated by HR after
                   issue invalidates any existing session)
  * ``invite``   = invite_id (saves a token lookup on every request)
  * ``purpose``  = "assessment" (separate namespace from regular
                   admin/HR access tokens)
  * ``exp``      = ``min(time_limit_deadline, default_ttl)``
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, decode_token
from app.core.database import get_db
from app.core.rate_limit import rate_limit_assessment_verify
from app.models.hr_assessment import AssessmentInvite, Assessment
from app.models.hr_ats import Candidate
from app.schemas.hr_assessment import (
    IdentityVerifyRequest,
    IdentityVerifyResponse,
    PublicAssessmentRead,
    PublicAssessmentSubmit,
    PublicChoiceRead,
    PublicQuestionRead,
    PublicSubmissionAck,
)
from app.services import assessment_service as svc


logger = logging.getLogger(__name__)


# Session JWT defaults. A candidate who hasn't started a clocked
# assessment still gets a deadline — otherwise an HR-side template
# without a time-limit would never expire the session.
_DEFAULT_SESSION_TTL = timedelta(hours=2)
_PURPOSE = "assessment"


router = APIRouter(
    prefix="/assessments",
    tags=["Public - Assessments"],
)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def _issue_session_token(
    *, invite: AssessmentInvite, candidate: Candidate, deadline: Optional[datetime]
) -> str:
    """Build the short-lived JWT the candidate uses for fetch + submit."""
    now = datetime.now(timezone.utc)
    if deadline is not None:
        ttl = max(deadline - now, timedelta(seconds=30))
    else:
        ttl = _DEFAULT_SESSION_TTL
    if ttl > _DEFAULT_SESSION_TTL:
        ttl = _DEFAULT_SESSION_TTL
    return create_access_token(
        subject=candidate.id,
        scopes=[],
        extra_claims={
            "token": invite.token,
            "invite": invite.id,
            "purpose": _PURPOSE,
        },
        expires_delta=ttl,
    )


def _decode_session(
    authorization: Optional[str],
) -> tuple[int, str, int]:
    """Return (candidate_id, invite_token, invite_id) — raise 401 if bad."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing assessment session token.")
    raw = authorization.split(" ", 1)[1].strip()
    try:
        claims = decode_token(raw)
    except JWTError as exc:
        raise HTTPException(
            status_code=401, detail="Invalid or expired session token."
        ) from exc
    if claims.get("purpose") != _PURPOSE:
        raise HTTPException(status_code=401, detail="Wrong token type.")
    try:
        candidate_id = int(claims["sub"])
        invite_token = str(claims["token"])
        invite_id = int(claims["invite"])
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Malformed session token.") from exc
    return candidate_id, invite_token, invite_id


def _load_session_invite(
    db: Session, *, candidate_id: int, invite_id: int, invite_token: str
) -> tuple[AssessmentInvite, Candidate, Assessment]:
    invite = db.get(AssessmentInvite, invite_id)
    if invite is None or invite.token != invite_token:
        # ``token`` mismatch happens when HR re-issued the invite —
        # the candidate's stashed JWT is now stale.
        raise HTTPException(
            status_code=401, detail="Session does not match this invite."
        )
    if invite.candidate_id != candidate_id:
        raise HTTPException(status_code=401, detail="Session candidate mismatch.")
    candidate = db.get(Candidate, candidate_id)
    assessment = db.get(Assessment, invite.assessment_id)
    if candidate is None or assessment is None:
        raise HTTPException(status_code=404, detail="Invite references missing data.")
    return invite, candidate, assessment


def _submit_deadline(invite: AssessmentInvite, template: Assessment) -> Optional[datetime]:
    """``opened_at + time_limit`` if both are set, capped by ``expires_at``."""
    soft = None
    if invite.opened_at is not None and template.time_limit_minutes:
        soft = invite.opened_at + timedelta(minutes=template.time_limit_minutes)
    hard = invite.expires_at
    candidates = [d for d in (soft, hard) if d is not None]
    if not candidates:
        return None
    return min(candidates)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{token}/verify",
    response_model=IdentityVerifyResponse,
    dependencies=[Depends(rate_limit_assessment_verify)],
)
def verify_identity(
    token: str,
    payload: IdentityVerifyRequest,
    db: Session = Depends(get_db),
) -> IdentityVerifyResponse:
    """Identity-check the candidate, mint a session token, open the form.

    The matched-field name is returned so the frontend can show a
    confirmation ("Verified with email", etc.). The session token is
    a JWT — the frontend stashes it in memory (not localStorage) and
    sends it on subsequent fetch + submit calls.
    """
    try:
        invite, candidate, template = svc.lookup_invite_by_token(db, token)
    except svc.AssessmentNotFound as exc:
        # Don't reveal whether the link existed at all — a captured
        # link can't be probed by trial-and-erroring identity values.
        raise HTTPException(status_code=404, detail="Invite not found.") from exc

    if invite.status == "cancelled":
        raise HTTPException(status_code=410, detail="This invite was cancelled.")
    if invite.status == "submitted":
        raise HTTPException(status_code=410, detail="This assessment is already submitted.")
    expires = svc.as_aware_utc(invite.expires_at)
    if expires is not None and datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=410, detail="This invite has expired.")

    matched_field = svc.verify_identity(invite, candidate, payload.identity_value)
    if matched_field is None:
        # Generic 401 — don't reveal which field was tried; an attacker
        # who captures the token still needs the candidate's PII.
        raise HTTPException(
            status_code=401,
            detail="Identity check failed. Please try again.",
        )

    try:
        submission = svc.open_submission(
            db, invite=invite, matched_field=matched_field
        )
    except svc.InviteExpired as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except svc.AssessmentLocked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    deadline = _submit_deadline(invite, template)
    session_token = _issue_session_token(
        invite=invite, candidate=candidate, deadline=deadline
    )
    return IdentityVerifyResponse(
        session_token=session_token,
        matched_field=matched_field,
        opened_at=submission.started_at,
        submit_deadline=deadline,
    )


@router.get("/me", response_model=PublicAssessmentRead)
def fetch_assessment(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> PublicAssessmentRead:
    """Return the form bundle — questions + choices, *no answer key*."""
    candidate_id, invite_token, invite_id = _decode_session(authorization)
    invite, candidate, template = _load_session_invite(
        db, candidate_id=candidate_id, invite_id=invite_id, invite_token=invite_token
    )

    questions = [
        PublicQuestionRead(
            id=q.id,
            text=q.text,
            order_index=q.order_index,
            points=q.points,
            choices=[
                PublicChoiceRead(
                    id=c.id, text=c.text, order_index=c.order_index
                )
                for c in sorted(q.choices, key=lambda c: c.order_index)
            ],
        )
        for q in sorted(template.questions, key=lambda q: q.order_index)
    ]

    return PublicAssessmentRead(
        title=template.title,
        instructions=template.instructions,
        time_limit_minutes=template.time_limit_minutes,
        questions=questions,
        candidate_name=candidate.full_name,
        candidate_email=candidate.email,
        submit_deadline=_submit_deadline(invite, template),
    )


@router.post("/me/submit", response_model=PublicSubmissionAck)
def submit_assessment(
    payload: PublicAssessmentSubmit,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> PublicSubmissionAck:
    """Persist the candidate's answers, auto-score, and return the ack."""
    candidate_id, invite_token, invite_id = _decode_session(authorization)
    invite, _candidate, _template = _load_session_invite(
        db, candidate_id=candidate_id, invite_id=invite_id, invite_token=invite_token
    )
    if invite.submission is None:
        raise HTTPException(
            status_code=409,
            detail="Submission row is missing — verify the link first.",
        )

    try:
        submission = svc.finalise_submission(
            db, submission=invite.submission, answers=payload.answers
        )
    except svc.InviteExpired as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
    except svc.AssessmentLocked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    db.commit()
    db.refresh(submission)
    return PublicSubmissionAck(
        score=submission.score or 0,
        max_score=submission.max_score or 0,
        passed=submission.passed,
        submitted_at=submission.submitted_at,  # type: ignore[arg-type]
    )

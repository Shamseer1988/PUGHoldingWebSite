"""Scorecard template CRUD + scorecard submission against feedback.

Endpoints
=========

  GET    /hr/scorecard-templates                     list active templates
  GET    /hr/scorecard-templates/{id}                fetch one
  POST   /hr/scorecard-templates                     create
  PATCH  /hr/scorecard-templates/{id}                edit
  DELETE /hr/scorecard-templates/{id}                soft-archive
  POST   /hr/scorecard-templates/{id}/default        mark as default

  POST   /hr/interviews/{interview_id}/feedback/{feedback_id}/scorecard
                                                      submit / update the
                                                      scorecard scores for
                                                      an existing feedback
                                                      row, computing the
                                                      cached weighted total.

Permission model: template CRUD requires
``hr:interviews:edit`` (HR Admin tier); submission requires
``hr:interviews:edit_feedback`` (interviewer tier).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context, require_permission
from app.auth.permissions import (
    PERM_HR_INTERVIEWS_SCHEDULE,
    PERM_HR_INTERVIEWS_FEEDBACK,
)
from app.core.database import get_db
from app.models.auth import User
from app.models.hr_ats import (
    SCORECARD_SCOPE_JOB,
    Interview,
    InterviewFeedback,
    JobOpening,
    ScorecardTemplate,
)
from app.schemas.scorecard import (
    ScorecardSubmission,
    ScorecardTemplateCreate,
    ScorecardTemplateRead,
    ScorecardTemplateUpdate,
)
from app.services.audit_log import record_audit
from app.services.scorecard import (
    ScorecardError,
    compute_weighted_total,
    validate_template_dimensions,
)


router = APIRouter(
    prefix="/hr",
    tags=["HR - Scorecard Templates"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_template(
    row: ScorecardTemplate, *, job_title_lookup: dict[int, str]
) -> ScorecardTemplateRead:
    return ScorecardTemplateRead(
        id=row.id,
        name=row.name,
        description=row.description,
        scope=row.scope,
        job_opening_id=row.job_opening_id,
        job_title=(
            job_title_lookup.get(row.job_opening_id)
            if row.job_opening_id
            else None
        ),
        dimensions=row.dimensions or [],
        is_active=row.is_active,
        is_default=row.is_default,
        created_by_id=row.created_by_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _audit(
    db: Session,
    actor: User,
    request: Request,
    *,
    action: str,
    target_id: Optional[int],
    details: Optional[dict] = None,
) -> None:
    ctx = get_request_context(request)
    record_audit(
        db,
        action=action,
        actor_id=actor.id,
        actor_email=actor.email,
        scope="hr",
        target_type="scorecard_template",
        target_id=str(target_id) if target_id is not None else None,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details=details,
        commit=False,
    )


def _job_title_lookup(
    db: Session, job_ids: list[int]
) -> dict[int, str]:
    clean = {i for i in job_ids if i}
    if not clean:
        return {}
    rows = db.execute(
        select(JobOpening.id, JobOpening.title).where(JobOpening.id.in_(clean))
    ).all()
    return {jid: title for jid, title in rows}


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/scorecard-templates", response_model=List[ScorecardTemplateRead]
)
def list_templates(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_INTERVIEWS_FEEDBACK)),
    include_inactive: bool = False,
    job_opening_id: Optional[int] = None,
) -> list[ScorecardTemplateRead]:
    """List templates an interviewer might attach to their feedback.

    Read access is granted to anyone with feedback-edit permission so
    interviewers see the rubric they're scoring against; CRUD is
    locked to the interview-edit tier below.
    """
    stmt = select(ScorecardTemplate).order_by(
        ScorecardTemplate.is_default.desc(), ScorecardTemplate.name
    )
    if not include_inactive:
        stmt = stmt.where(ScorecardTemplate.is_active.is_(True))
    if job_opening_id is not None:
        # When a job is in play, show templates that apply: the global
        # ones + the ones pinned to this specific job.
        stmt = stmt.where(
            (ScorecardTemplate.scope == "global")
            | (ScorecardTemplate.job_opening_id == job_opening_id)
        )
    rows = db.execute(stmt).scalars().all()
    job_titles = _job_title_lookup(db, [r.job_opening_id for r in rows])
    return [_serialize_template(r, job_title_lookup=job_titles) for r in rows]


@router.get(
    "/scorecard-templates/{template_id}",
    response_model=ScorecardTemplateRead,
)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_INTERVIEWS_FEEDBACK)),
) -> ScorecardTemplateRead:
    row = db.get(ScorecardTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return _serialize_template(
        row, job_title_lookup=_job_title_lookup(db, [row.job_opening_id])
    )


@router.post(
    "/scorecard-templates",
    response_model=ScorecardTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
def create_template(
    payload: ScorecardTemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_INTERVIEWS_SCHEDULE)),
) -> ScorecardTemplateRead:
    if payload.scope == SCORECARD_SCOPE_JOB and payload.job_opening_id is None:
        raise HTTPException(
            status_code=422,
            detail="job_opening_id is required when scope is 'job'.",
        )
    if payload.scope != SCORECARD_SCOPE_JOB and payload.job_opening_id is not None:
        raise HTTPException(
            status_code=422,
            detail="job_opening_id may only be set when scope is 'job'.",
        )

    dimensions = [d.model_dump() for d in payload.dimensions]
    try:
        validate_template_dimensions(dimensions)
    except ScorecardError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Only one default at a time — flip the previous default off.
    if payload.is_default:
        _clear_existing_default(db)

    row = ScorecardTemplate(
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        scope=payload.scope,
        job_opening_id=payload.job_opening_id,
        dimensions=dimensions,
        is_active=payload.is_active,
        is_default=payload.is_default,
        created_by_id=actor.id,
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        actor,
        request,
        action="hr.scorecard_template.create",
        target_id=row.id,
        details={"name": row.name, "scope": row.scope},
    )
    db.commit()
    db.refresh(row)
    return _serialize_template(
        row, job_title_lookup=_job_title_lookup(db, [row.job_opening_id])
    )


@router.patch(
    "/scorecard-templates/{template_id}",
    response_model=ScorecardTemplateRead,
)
def update_template(
    template_id: int,
    payload: ScorecardTemplateUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_INTERVIEWS_SCHEDULE)),
) -> ScorecardTemplateRead:
    row = db.get(ScorecardTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")

    updates = payload.model_dump(exclude_unset=True)
    if updates.get("scope") == SCORECARD_SCOPE_JOB and (
        updates.get("job_opening_id") or row.job_opening_id
    ) is None:
        raise HTTPException(
            status_code=422,
            detail="job_opening_id is required when scope is 'job'.",
        )

    if "dimensions" in updates and updates["dimensions"] is not None:
        try:
            validate_template_dimensions(updates["dimensions"])
        except ScorecardError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    if updates.get("is_default") is True and not row.is_default:
        _clear_existing_default(db, except_id=row.id)

    for key, value in updates.items():
        if value is None and key not in ("description",):
            continue
        setattr(row, key, value)

    _audit(
        db,
        actor,
        request,
        action="hr.scorecard_template.update",
        target_id=row.id,
        details={"fields": sorted(updates.keys())},
    )
    db.commit()
    db.refresh(row)
    return _serialize_template(
        row, job_title_lookup=_job_title_lookup(db, [row.job_opening_id])
    )


@router.delete(
    "/scorecard-templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def deactivate_template(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_INTERVIEWS_SCHEDULE)),
) -> Response:
    """Soft archive — flips ``is_active`` to false. Hard delete is
    avoided so submitted feedback rows keep their template reference."""
    row = db.get(ScorecardTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if not row.is_active:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    row.is_active = False
    row.is_default = False
    _audit(
        db,
        actor,
        request,
        action="hr.scorecard_template.deactivate",
        target_id=row.id,
        details={"name": row.name},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _clear_existing_default(
    db: Session, *, except_id: Optional[int] = None
) -> None:
    stmt = select(ScorecardTemplate).where(ScorecardTemplate.is_default.is_(True))
    if except_id is not None:
        stmt = stmt.where(ScorecardTemplate.id != except_id)
    for row in db.execute(stmt).scalars().all():
        row.is_default = False


# ---------------------------------------------------------------------------
# Scorecard submission against a feedback row
# ---------------------------------------------------------------------------


@router.post(
    "/interviews/{interview_id}/feedback/{feedback_id}/scorecard",
    response_model=dict,
)
def submit_scorecard(
    interview_id: int,
    feedback_id: int,
    payload: ScorecardSubmission,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_INTERVIEWS_FEEDBACK)),
) -> dict:
    """Attach scorecard scores to an existing feedback row.

    The template's dimension keys are the authoritative set; any
    extra keys in the submission are dropped, and missing keys
    contribute 0 to the weighted total. Submitting twice overwrites
    the previous scorecard for the same feedback row.
    """
    interview = db.get(Interview, interview_id)
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found")
    feedback = db.get(InterviewFeedback, feedback_id)
    if feedback is None or feedback.interview_id != interview_id:
        raise HTTPException(
            status_code=404,
            detail="Feedback row not found on that interview.",
        )

    template = db.get(ScorecardTemplate, payload.template_id)
    if template is None or not template.is_active:
        raise HTTPException(
            status_code=404, detail="Scorecard template not found or inactive."
        )

    dim_keys = {d["key"] for d in (template.dimensions or [])}
    submitted = {
        k: v.model_dump() for k, v in payload.scores.items() if k in dim_keys
    }

    feedback.scorecard_template_id = template.id
    feedback.scorecard_scores = submitted
    feedback.scorecard_total = compute_weighted_total(
        template.dimensions or [], submitted
    )

    _audit(
        db,
        actor,
        request,
        action="hr.scorecard.submit",
        target_id=feedback.id,
        details={
            "interview_id": interview_id,
            "template_id": template.id,
            "scorecard_total": feedback.scorecard_total,
        },
    )
    db.commit()
    db.refresh(feedback)
    return {
        "feedback_id": feedback.id,
        "interview_id": interview_id,
        "template_id": template.id,
        "scorecard_total": feedback.scorecard_total,
        "scorecard_scores": feedback.scorecard_scores or {},
    }


__all__ = ["router"]

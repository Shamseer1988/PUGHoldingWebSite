"""HR ATS Job Opening CRUD endpoints (Phase 9).

All routes require an HR-scoped bearer token. Write actions write
entries to the shared ``audit_logs`` table with ``scope='hr'``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context, require_hr_admin
from app.core.database import get_db
from app.models.auth import User
from app.models.hr_ats import (
    JOB_STATUS_CLOSED,
    JOB_STATUS_ON_HOLD,
    JOB_STATUS_OPEN,
    JobOpening,
)
from app.schemas.hr_ats import (
    JobOpeningCreate,
    JobOpeningRead,
    JobOpeningUpdate,
)
from app.services.audit_log import record_audit


router = APIRouter(
    prefix="/hr/jobs",
    tags=["HR ATS - Jobs"],
    dependencies=[Depends(require_hr_admin)],
)


# ---------------------------------------------------------------------------
# List + read
# ---------------------------------------------------------------------------


@router.get("", response_model=List[JobOpeningRead])
def list_jobs(
    db: Session = Depends(get_db),
    job_status: Optional[str] = Query(
        default=None,
        alias="status",
        pattern=r"^(open|on_hold|closed)$",
    ),
    department: Optional[str] = None,
    company: Optional[str] = None,
    q: Optional[str] = Query(default=None, max_length=200),
) -> List[JobOpening]:
    stmt = select(JobOpening).order_by(desc(JobOpening.posted_at), JobOpening.id)
    if job_status:
        stmt = stmt.where(JobOpening.status == job_status)
    if department:
        stmt = stmt.where(JobOpening.department == department)
    if company:
        stmt = stmt.where(JobOpening.company == company)
    if q:
        like = f"%{q.lower()}%"
        # Postgres ilike works case-insensitively. For SQLite tests
        # we use lower(...) like which both engines accept.
        from sqlalchemy import func

        stmt = stmt.where(
            (func.lower(JobOpening.title).like(like))
            | (func.lower(JobOpening.required_skills).like(like))
            | (func.lower(JobOpening.preferred_skills).like(like))
        )
    return db.execute(stmt).scalars().all()


@router.get("/{job_id}", response_model=JobOpeningRead)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobOpening:
    job = db.get(JobOpening, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------------------------
# Create / update / delete
# ---------------------------------------------------------------------------


@router.post("", response_model=JobOpeningRead, status_code=201)
def create_job(
    payload: JobOpeningCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> JobOpening:
    data = payload.model_dump()
    job = JobOpening(**data, created_by_id=user.id)
    db.add(job)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already exists") from exc

    _audit(
        db,
        user,
        request,
        action="hr.job.create",
        target_id=job.id,
        details={"slug": job.slug, "title": job.title, "status": job.status},
    )
    db.commit()
    db.refresh(job)
    return job


@router.patch("/{job_id}", response_model=JobOpeningRead)
def update_job(
    job_id: int,
    payload: JobOpeningUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> JobOpening:
    job = db.get(JobOpening, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    changes = payload.model_dump(exclude_unset=True)

    # Auto-stamp closed_at when transitioning to closed (or clear it
    # when moving back to open / on_hold).
    if "status" in changes and changes["status"] != job.status:
        if changes["status"] == JOB_STATUS_CLOSED:
            job.closed_at = datetime.now(timezone.utc)
        else:
            job.closed_at = None

    for k, v in changes.items():
        setattr(job, k, v)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already exists") from exc

    _audit(
        db,
        user,
        request,
        action="hr.job.update",
        target_id=job.id,
        details={"changed_keys": list(changes.keys())},
    )
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/close", response_model=JobOpeningRead)
def close_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> JobOpening:
    return _transition(db, user, request, job_id, JOB_STATUS_CLOSED, "hr.job.close")


@router.post("/{job_id}/reopen", response_model=JobOpeningRead)
def reopen_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> JobOpening:
    return _transition(db, user, request, job_id, JOB_STATUS_OPEN, "hr.job.reopen")


@router.post("/{job_id}/hold", response_model=JobOpeningRead)
def hold_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> JobOpening:
    return _transition(db, user, request, job_id, JOB_STATUS_ON_HOLD, "hr.job.hold")


@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> Response:
    job = db.get(JobOpening, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    db.delete(job)
    _audit(
        db,
        user,
        request,
        action="hr.job.delete",
        target_id=job_id,
        details={"slug": job.slug, "title": job.title},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _transition(
    db: Session,
    user: User,
    request: Request,
    job_id: int,
    next_status: str,
    action: str,
) -> JobOpening:
    job = db.get(JobOpening, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == next_status:
        return job  # no-op; idempotent

    old_status = job.status
    job.status = next_status
    if next_status == JOB_STATUS_CLOSED:
        job.closed_at = datetime.now(timezone.utc)
    else:
        job.closed_at = None

    _audit(
        db,
        user,
        request,
        action=action,
        target_id=job.id,
        details={"old_status": old_status, "new_status": next_status},
    )
    db.commit()
    db.refresh(job)
    return job


def _audit(
    db: Session,
    user: User,
    request: Request,
    *,
    action: str,
    target_id: int,
    details: Optional[dict] = None,
) -> None:
    ctx = get_request_context(request)
    record_audit(
        db,
        action=action,
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="job_opening",
        target_id=str(target_id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details=details,
        commit=False,
    )

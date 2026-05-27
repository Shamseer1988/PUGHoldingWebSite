"""HR ATS Job Opening CRUD endpoints with approval workflow.

All routes require an HR-scoped bearer token. Write actions write
entries to the shared ``audit_logs`` table with ``scope='hr'`` and (for
approval transitions) to ``hr_job_approval_history``.

The advanced module adds:

* :func:`create_job` lands new jobs in ``approval_status='draft'`` so the
  public site cannot show them until an HR Manager approves.
* :func:`update_job` routes edits on already-approved jobs into a
  :class:`JobRevision` row instead of mutating the public content.
* Approval endpoints (``submit-approval``, ``approve``, ``reject``,
  ``request-revision``, ``publish``, ``unpublish``,
  ``approval-history``) drive the workflow.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_request_context,
    require_any_permission,
    require_hr_admin,
    require_permission,
)
from app.auth.permissions import (
    PERM_HR_JOBS_APPROVE,
    PERM_HR_JOBS_CREATE,
    PERM_HR_JOBS_DELETE,
    PERM_HR_JOBS_EDIT,
    PERM_HR_JOBS_PUBLISH,
    PERM_HR_JOBS_VIEW,
    PERM_HR_JOBS_VIEW_DEPT,
    PERM_HR_SETTINGS_MANAGE,
)
from app.core.database import get_db
from app.models.auth import User
from app.models.hr_ats import (
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_DRAFT,
    JOB_STATUS_CLOSED,
    JOB_STATUS_ON_HOLD,
    JOB_STATUS_OPEN,
    JobOpening,
    JobRevision,
    PUBLISH_STATUS_DRAFT,
)


def _assert_not_self_approval(job: JobOpening, user: User) -> None:
    """Approval-workflow row-level rule: the submitter cannot approve,
    reject, or request revision on their own submission.

    Super-users bypass for emergency unblocks (rare; audited).
    """
    if user.is_superuser:
        return
    submitter = job.submitted_for_approval_by_id or job.created_by_id
    if submitter == user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You cannot approve, reject, or request revision on a job "
                "opening you submitted. Ask another manager to review it."
            ),
        )


def _apply_dept_scope(stmt, user: User):
    """If the user has only the department-scoped permission, restrict the
    SELECT to rows whose ``department`` matches ``user.department``.

    Returns the (possibly filtered) statement. No-op for users with the
    full ``hr:jobs:view`` permission or superusers.
    """
    if user.is_superuser or user.has_permission(PERM_HR_JOBS_VIEW):
        return stmt
    if user.has_permission(PERM_HR_JOBS_VIEW_DEPT) and user.department:
        return stmt.where(JobOpening.department == user.department)
    return stmt
from app.schemas.hr_ats import (
    ArchiveRequest,
    DeleteRequest,
    JobApprovalActionRequest,
    JobApprovalHistoryRead,
    JobApprovalRejectRequest,
    JobAutoReviewRuleRead,
    JobAutoReviewRuleUpdate,
    JobAutoReviewSummary,
    JobOpeningCreate,
    JobOpeningRead,
    JobOpeningUpdate,
    JobRevisionRead,
)
from app.services import job_approval as approval
from app.services.audit_log import record_audit


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/hr/jobs",
    tags=["HR ATS - Jobs"],
    dependencies=[Depends(require_hr_admin)],
)


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


def _serialize(job: JobOpening) -> JobOpeningRead:
    """Build the response payload, adding has_pending_revision."""
    has_pending = approval.get_pending_revision(None, job) is not None
    data = JobOpeningRead.model_validate(job).model_dump()
    data["has_pending_revision"] = has_pending
    return JobOpeningRead(**data)


# ---------------------------------------------------------------------------
# List + read
# ---------------------------------------------------------------------------


@router.get("", response_model=List[JobOpeningRead])
def list_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(
        require_any_permission(PERM_HR_JOBS_VIEW, PERM_HR_JOBS_VIEW_DEPT)
    ),
    job_status: Optional[str] = Query(
        default=None,
        alias="status",
        pattern=r"^(open|on_hold|closed)$",
    ),
    approval_status: Optional[str] = Query(
        default=None,
        pattern=r"^(draft|pending_approval|approved|rejected|revision_required)$",
    ),
    publish_status: Optional[str] = Query(
        default=None, pattern=r"^(draft|published|unpublished)$"
    ),
    department: Optional[str] = None,
    company: Optional[str] = None,
    q: Optional[str] = Query(default=None, max_length=200),
    include_archived: bool = Query(default=False),
) -> List[JobOpeningRead]:
    stmt = select(JobOpening).order_by(desc(JobOpening.posted_at), JobOpening.id)
    stmt = _apply_dept_scope(stmt, user)
    # Phase 8 — archived jobs hidden from the default list. HR can pass
    # ?include_archived=true to see them (e.g. for the archive browser).
    if not include_archived:
        stmt = stmt.where(JobOpening.is_archived.is_(False))
    if job_status:
        stmt = stmt.where(JobOpening.status == job_status)
    if approval_status:
        stmt = stmt.where(JobOpening.approval_status == approval_status)
    if publish_status:
        stmt = stmt.where(JobOpening.publish_status == publish_status)
    if department:
        stmt = stmt.where(JobOpening.department == department)
    if company:
        stmt = stmt.where(JobOpening.company == company)
    if q:
        from sqlalchemy import func

        like = f"%{q.lower()}%"
        stmt = stmt.where(
            (func.lower(JobOpening.title).like(like))
            | (func.lower(JobOpening.required_skills).like(like))
            | (func.lower(JobOpening.preferred_skills).like(like))
        )
    rows = db.execute(stmt).scalars().all()
    return [_serialize(job) for job in rows]


@router.get("/{job_id}", response_model=JobOpeningRead)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_any_permission(PERM_HR_JOBS_VIEW, PERM_HR_JOBS_VIEW_DEPT)
    ),
) -> JobOpeningRead:
    job = db.get(JobOpening, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    # Department-scope check: 404 (not 403) so we don't leak existence.
    if (
        not user.is_superuser
        and not user.has_permission(PERM_HR_JOBS_VIEW)
        and user.has_permission(PERM_HR_JOBS_VIEW_DEPT)
        and user.department
        and job.department != user.department
    ):
        raise HTTPException(status_code=404, detail="Job not found")
    return _serialize(job)


# ---------------------------------------------------------------------------
# Create / update / delete
# ---------------------------------------------------------------------------


@router.post("", response_model=JobOpeningRead, status_code=201)
def create_job(
    payload: JobOpeningCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_CREATE)),
) -> JobOpeningRead:
    data = payload.model_dump()
    # New jobs always land in draft regardless of what the client sent —
    # approval is required before the public site can show them.
    job = JobOpening(
        **data,
        created_by_id=user.id,
        approval_status=APPROVAL_STATUS_DRAFT,
        publish_status=PUBLISH_STATUS_DRAFT,
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already exists") from exc

    approval.record_approval_history(
        db,
        job=job,
        action="created",
        actor=user,
        old_status=None,
        new_status=APPROVAL_STATUS_DRAFT,
        remarks="Job draft created",
    )

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
    _notify_safe(
        "notify_job_created",
        job_id=job.id,
        actor_id=user.id,
    )
    return _serialize(job)


@router.patch("/{job_id}", response_model=JobOpeningRead)
def update_job(
    job_id: int,
    payload: JobOpeningUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_EDIT)),
) -> JobOpeningRead:
    job = db.get(JobOpening, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    changes = payload.model_dump(exclude_unset=True)

    # Lifecycle ``status`` (open/on_hold/closed) is handled outside the
    # approval workflow — pull it off and apply it directly even on
    # approved jobs (HR still needs to close/hold immediately).
    lifecycle_change = changes.pop("status", None)

    edit_keys = list(changes.keys())
    job, revision = approval.apply_edit(
        db, job=job, changes=changes, actor=user
    )

    if lifecycle_change and lifecycle_change != job.status:
        old_lifecycle = job.status
        job.status = lifecycle_change
        if lifecycle_change == JOB_STATUS_CLOSED:
            job.closed_at = datetime.now(timezone.utc)
        else:
            job.closed_at = None
        _audit(
            db,
            user,
            request,
            action="hr.job.status_change",
            target_id=job.id,
            details={"old_status": old_lifecycle, "new_status": lifecycle_change},
        )

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already exists") from exc

    audit_action = "hr.job.update_revision" if revision is not None else "hr.job.update"
    _audit(
        db,
        user,
        request,
        action=audit_action,
        target_id=job.id,
        details={
            "changed_keys": edit_keys,
            "revision_id": revision.id if revision else None,
        },
    )
    db.commit()
    db.refresh(job)
    if revision is not None:
        _notify_safe(
            "notify_job_revision_submitted",
            job_id=job.id,
            revision_id=revision.id,
            actor_id=user.id,
        )
    return _serialize(job)


@router.post("/{job_id}/close", response_model=JobOpeningRead)
def close_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_EDIT)),
) -> JobOpeningRead:
    return _transition(db, user, request, job_id, JOB_STATUS_CLOSED, "hr.job.close")


@router.post("/{job_id}/reopen", response_model=JobOpeningRead)
def reopen_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_EDIT)),
) -> JobOpeningRead:
    return _transition(db, user, request, job_id, JOB_STATUS_OPEN, "hr.job.reopen")


@router.post("/{job_id}/hold", response_model=JobOpeningRead)
def hold_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_EDIT)),
) -> JobOpeningRead:
    return _transition(db, user, request, job_id, JOB_STATUS_ON_HOLD, "hr.job.hold")


@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    request: Request,
    payload: Optional[DeleteRequest] = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_DELETE)),
) -> Response:
    """Hard-delete a job. Restricted to hr:jobs:delete (HR Manager +
    Super Admin per the default role matrix). HR users should
    normally archive instead — see POST /hr/jobs/{id}/archive."""
    job = db.get(JobOpening, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    reason = payload.reason if payload else None
    db.delete(job)
    _audit(
        db,
        user,
        request,
        action="hr.job.delete",
        target_id=job_id,
        details={"slug": job.slug, "title": job.title, "reason": reason},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{job_id}/archive", response_model=JobOpeningRead)
def archive_job(
    job_id: int,
    payload: ArchiveRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_DELETE)),
) -> JobOpeningRead:
    """Soft-archive: flips is_archived=True, records who/when/why,
    and hides the job from default listing queries. Preserves all
    history. Use unarchive to restore."""
    job = _get_or_404(db, job_id)
    if job.is_archived:
        raise HTTPException(status_code=409, detail="Job is already archived.")
    job.is_archived = True
    job.archived_at = datetime.now(timezone.utc)
    job.archived_by_id = user.id
    job.archive_reason = payload.reason
    _audit(
        db,
        user,
        request,
        action="hr.job.archive",
        target_id=job_id,
        details={"reason": payload.reason},
    )
    db.commit()
    db.refresh(job)
    return _serialize(job)


@router.post("/{job_id}/unarchive", response_model=JobOpeningRead)
def unarchive_job(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_DELETE)),
) -> JobOpeningRead:
    """Restore a soft-archived job."""
    job = _get_or_404(db, job_id)
    if not job.is_archived:
        raise HTTPException(status_code=409, detail="Job is not archived.")
    job.is_archived = False
    job.archived_at = None
    job.archived_by_id = None
    job.archive_reason = None
    _audit(
        db,
        user,
        request,
        action="hr.job.unarchive",
        target_id=job_id,
    )
    db.commit()
    db.refresh(job)
    return _serialize(job)


# ---------------------------------------------------------------------------
# Approval workflow endpoints
# ---------------------------------------------------------------------------


@router.post("/{job_id}/submit-approval", response_model=JobOpeningRead)
def submit_for_approval(
    job_id: int,
    payload: Optional[JobApprovalActionRequest] = None,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_CREATE)),
) -> JobOpeningRead:
    job = _get_or_404(db, job_id)
    remarks = (payload.remarks if payload else None)
    approval.submit_for_approval(db, job=job, actor=user, remarks=remarks)
    _audit(
        db,
        user,
        request,
        action="hr.job.submit_for_approval",
        target_id=job.id,
        details={"remarks": remarks},
    )
    db.commit()
    db.refresh(job)
    _notify_safe("notify_job_submitted", job_id=job.id, actor_id=user.id)
    return _serialize(job)


@router.post("/{job_id}/approve", response_model=JobOpeningRead)
def approve_job_endpoint(
    job_id: int,
    payload: Optional[JobApprovalActionRequest] = None,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_APPROVE)),
) -> JobOpeningRead:
    job = _get_or_404(db, job_id)
    _assert_not_self_approval(job, user)
    remarks = (payload.remarks if payload else None)

    # If a pending revision exists, approving the job approves the revision
    # too (HR Manager has signed off on the new content).
    pending_revision = approval.get_pending_revision(db, job)
    if pending_revision is not None:
        approval.approve_revision(
            db, revision=pending_revision, actor=user, remarks=remarks
        )
        # If the job is still pending_approval, also approve the job itself.
        if job.approval_status != APPROVAL_STATUS_APPROVED:
            approval.approve_job(db, job=job, actor=user, remarks=remarks)
    else:
        approval.approve_job(db, job=job, actor=user, remarks=remarks)

    _audit(
        db,
        user,
        request,
        action="hr.job.approve",
        target_id=job.id,
        details={"remarks": remarks},
    )
    db.commit()
    db.refresh(job)
    _notify_safe("notify_job_approved", job_id=job.id, actor_id=user.id)
    return _serialize(job)


@router.post("/{job_id}/reject", response_model=JobOpeningRead)
def reject_job_endpoint(
    job_id: int,
    payload: JobApprovalRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_APPROVE)),
) -> JobOpeningRead:
    job = _get_or_404(db, job_id)
    _assert_not_self_approval(job, user)

    pending_revision = approval.get_pending_revision(db, job)
    if pending_revision is not None:
        approval.reject_revision(
            db, revision=pending_revision, actor=user, remarks=payload.remarks
        )
        # The public job stays untouched. If the job itself was pending
        # (first approval), also mark it rejected.
        from app.models.hr_ats import APPROVAL_STATUS_PENDING

        if job.approval_status == APPROVAL_STATUS_PENDING:
            approval.reject_job(db, job=job, actor=user, remarks=payload.remarks)
    else:
        approval.reject_job(db, job=job, actor=user, remarks=payload.remarks)

    _audit(
        db,
        user,
        request,
        action="hr.job.reject",
        target_id=job.id,
        details={"remarks": payload.remarks},
    )
    db.commit()
    db.refresh(job)
    _notify_safe(
        "notify_job_rejected",
        job_id=job.id,
        actor_id=user.id,
        reason=payload.remarks,
    )
    return _serialize(job)


@router.post("/{job_id}/request-revision", response_model=JobOpeningRead)
def request_revision_endpoint(
    job_id: int,
    payload: Optional[JobApprovalActionRequest] = None,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_APPROVE)),
) -> JobOpeningRead:
    job = _get_or_404(db, job_id)
    _assert_not_self_approval(job, user)
    remarks = (payload.remarks if payload else None)
    approval.request_revision(db, job=job, actor=user, remarks=remarks)
    _audit(
        db,
        user,
        request,
        action="hr.job.request_revision",
        target_id=job.id,
        details={"remarks": remarks},
    )
    db.commit()
    db.refresh(job)
    _notify_safe(
        "notify_job_revision_requested",
        job_id=job.id,
        actor_id=user.id,
        reason=remarks,
    )
    return _serialize(job)


@router.post("/{job_id}/publish", response_model=JobOpeningRead)
def publish_job_endpoint(
    job_id: int,
    payload: Optional[JobApprovalActionRequest] = None,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_PUBLISH)),
) -> JobOpeningRead:
    job = _get_or_404(db, job_id)
    remarks = (payload.remarks if payload else None)
    approval.publish_job(db, job=job, actor=user, remarks=remarks)
    _audit(
        db,
        user,
        request,
        action="hr.job.publish",
        target_id=job.id,
        details={"remarks": remarks},
    )
    db.commit()
    db.refresh(job)
    _notify_safe("notify_job_published", job_id=job.id, actor_id=user.id)
    return _serialize(job)


@router.post("/{job_id}/unpublish", response_model=JobOpeningRead)
def unpublish_job_endpoint(
    job_id: int,
    payload: Optional[JobApprovalActionRequest] = None,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_PUBLISH)),
) -> JobOpeningRead:
    job = _get_or_404(db, job_id)
    remarks = (payload.remarks if payload else None)
    approval.unpublish_job(db, job=job, actor=user, remarks=remarks)
    _audit(
        db,
        user,
        request,
        action="hr.job.unpublish",
        target_id=job.id,
        details={"remarks": remarks},
    )
    db.commit()
    db.refresh(job)
    return _serialize(job)


@router.get(
    "/{job_id}/approval-history",
    response_model=List[JobApprovalHistoryRead],
)
def get_approval_history(
    job_id: int,
    db: Session = Depends(get_db),
) -> List[JobApprovalHistoryRead]:
    job = _get_or_404(db, job_id)
    history = approval.list_approval_history(db, job.id)
    return [JobApprovalHistoryRead.model_validate(h) for h in history]


@router.get(
    "/{job_id}/pending-revision",
    response_model=Optional[JobRevisionRead],
)
def get_pending_revision_endpoint(
    job_id: int,
    db: Session = Depends(get_db),
) -> Optional[JobRevisionRead]:
    """Return the active pending revision (or null) for the HR Manager UI."""
    job = _get_or_404(db, job_id)
    revision = approval.get_pending_revision(db, job)
    return JobRevisionRead.model_validate(revision) if revision else None


@router.get("/{job_id}/revisions", response_model=List[JobRevisionRead])
def list_revisions(
    job_id: int,
    db: Session = Depends(get_db),
) -> List[JobRevisionRead]:
    job = _get_or_404(db, job_id)
    return [JobRevisionRead.model_validate(r) for r in job.revisions]


@router.post(
    "/{job_id}/revisions/{revision_id}/approve",
    response_model=JobOpeningRead,
)
def approve_revision_endpoint(
    job_id: int,
    revision_id: int,
    payload: Optional[JobApprovalActionRequest] = None,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_APPROVE)),
) -> JobOpeningRead:
    """Approve a specific pending revision — applies the payload to the
    live job. Requires hr:jobs:approve. Self-approval guard applies:
    the manager who submitted the original job (or revision) cannot
    approve their own changes."""
    job = _get_or_404(db, job_id)
    _assert_not_self_approval(job, user)

    revision = next(
        (r for r in job.revisions if r.id == revision_id), None
    )
    if revision is None:
        raise HTTPException(status_code=404, detail="Revision not found")

    remarks = (payload.remarks if payload else None)
    approval.approve_revision(db, revision=revision, actor=user, remarks=remarks)
    _audit(
        db,
        user,
        request,
        action="hr.job.revision.approve",
        target_id=job.id,
        details={"revision_id": revision_id, "remarks": remarks},
    )
    db.commit()
    db.refresh(job)
    return _serialize(job)


@router.post(
    "/{job_id}/revisions/{revision_id}/reject",
    response_model=JobOpeningRead,
)
def reject_revision_endpoint(
    job_id: int,
    revision_id: int,
    payload: JobApprovalRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_APPROVE)),
) -> JobOpeningRead:
    """Reject a specific pending revision — discards the payload, the
    live job stays unchanged. Requires hr:jobs:approve and a remarks
    string (min 4 chars, enforced by the JobApprovalRejectRequest
    schema)."""
    job = _get_or_404(db, job_id)
    _assert_not_self_approval(job, user)

    revision = next(
        (r for r in job.revisions if r.id == revision_id), None
    )
    if revision is None:
        raise HTTPException(status_code=404, detail="Revision not found")

    approval.reject_revision(
        db, revision=revision, actor=user, remarks=payload.remarks
    )
    _audit(
        db,
        user,
        request,
        action="hr.job.revision.reject",
        target_id=job.id,
        details={"revision_id": revision_id, "remarks": payload.remarks},
    )
    db.commit()
    db.refresh(job)
    return _serialize(job)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _get_or_404(db: Session, job_id: int) -> JobOpening:
    job = db.get(JobOpening, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _transition(
    db: Session,
    user: User,
    request: Request,
    job_id: int,
    next_status: str,
    action: str,
) -> JobOpeningRead:
    job = _get_or_404(db, job_id)

    if job.status == next_status:
        return _serialize(job)  # no-op; idempotent

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
    return _serialize(job)


def _audit(
    db: Session,
    user: User,
    request: Optional[Request],
    *,
    action: str,
    target_id: int,
    details: Optional[dict] = None,
) -> None:
    ctx = (
        get_request_context(request)
        if request is not None
        else {"ip_address": None, "user_agent": None}
    )
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


def _notify_safe(func_name: str, **kwargs) -> None:
    """Call hr_notifications.<func_name>(**kwargs) and swallow any error.

    Notifications must never break the API transaction — the caller has
    already committed. The notifications module is added in Phase 3; until
    it exists this just no-ops, letting Phase 2 land cleanly.
    """
    try:
        from app.services import hr_notifications  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover - module not yet present
        return
    func = getattr(hr_notifications, func_name, None)
    if func is None:
        return
    try:
        func(**kwargs)
    except Exception:  # pragma: no cover - never break the transaction
        logger.exception("hr_notifications.%s failed", func_name)


# ---------------------------------------------------------------------------
# Auto-review rule per job (advanced module — phase 4)
# ---------------------------------------------------------------------------


@router.get(
    "/{job_id}/auto-review-rule",
    response_model=Optional[JobAutoReviewRuleRead],
)
def get_auto_review_rule(
    job_id: int,
    db: Session = Depends(get_db),
) -> Optional[JobAutoReviewRuleRead]:
    from app.models.hr_ats import JobAutoReviewRule

    _get_or_404(db, job_id)
    rule = db.execute(
        select(JobAutoReviewRule).where(JobAutoReviewRule.job_opening_id == job_id)
    ).scalar_one_or_none()
    return JobAutoReviewRuleRead.model_validate(rule) if rule else None


@router.put(
    "/{job_id}/auto-review-rule",
    response_model=JobAutoReviewRuleRead,
)
def upsert_auto_review_rule(
    job_id: int,
    payload: JobAutoReviewRuleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_SETTINGS_MANAGE)),
) -> JobAutoReviewRuleRead:
    from app.services import candidate_auto_review

    _get_or_404(db, job_id)
    rule = candidate_auto_review.get_or_create_rule(
        db, job_opening_id=job_id, created_by_id=user.id
    )

    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(rule, k, v)
    rule.updated_by_id = user.id

    _audit(
        db,
        user,
        request,
        action="hr.job.auto_review_rule.upsert",
        target_id=job_id,
        details={"keys": list(changes.keys())},
    )
    db.commit()
    db.refresh(rule)
    return JobAutoReviewRuleRead.model_validate(rule)


@router.post("/{job_id}/auto-review-run", response_model=dict)
def run_job_auto_review(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_JOBS_EDIT)),
) -> dict:
    """Re-run auto-review on every application of this job."""
    from app.services import candidate_auto_review

    _get_or_404(db, job_id)
    reviews = candidate_auto_review.run_auto_review_for_job(
        db, job_opening_id=job_id
    )
    _audit(
        db,
        user,
        request,
        action="hr.job.auto_review.run",
        target_id=job_id,
        details={"reviewed": len(reviews)},
    )
    db.commit()
    return {"reviewed": len(reviews)}


@router.get("/{job_id}/auto-review-summary", response_model=JobAutoReviewSummary)
def get_auto_review_summary(
    job_id: int,
    db: Session = Depends(get_db),
) -> JobAutoReviewSummary:
    from app.services import candidate_auto_review

    _get_or_404(db, job_id)
    summary = candidate_auto_review.summarise_job(db, job_opening_id=job_id)
    return JobAutoReviewSummary(**summary)

"""HR Job approval workflow service.

The advanced HR module enforces a two-step lifecycle on every job:

1. An HR Executive creates or edits a job. New jobs land in
   ``approval_status='draft'`` / ``publish_status='draft'``. Editing an
   approved+published job creates a :class:`JobRevision` row instead of
   mutating the public job content.
2. An HR Manager reviews the pending job (or pending revision) and
   approves, rejects, or requests another revision. Only after approval
   does the job (or the revision's payload) flow into the public listing.

Every transition is recorded in two places: the cross-cutting
``audit_logs`` table (via :func:`record_audit`) and the
:class:`JobApprovalHistory` table that gives HR a chronological view per
job. Email notifications are dispatched through the notification service
added in Phase 3 — failures there are swallowed so the underlying
transaction never rolls back.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.hr_ats import (
    APPROVAL_ACTION_APPROVED,
    APPROVAL_ACTION_CREATED,
    APPROVAL_ACTION_PUBLISHED,
    APPROVAL_ACTION_REJECTED,
    APPROVAL_ACTION_REVISION_REQUESTED,
    APPROVAL_ACTION_REVISION_SUBMITTED,
    APPROVAL_ACTION_SUBMITTED,
    APPROVAL_ACTION_UNPUBLISHED,
    APPROVAL_STATUS_APPROVED,
    APPROVAL_STATUS_DRAFT,
    APPROVAL_STATUS_PENDING,
    APPROVAL_STATUS_REJECTED,
    APPROVAL_STATUS_REVISION_REQUIRED,
    JOB_STATUS_OPEN,
    JobApprovalHistory,
    JobOpening,
    JobRevision,
    PUBLISH_STATUS_DRAFT,
    PUBLISH_STATUS_PUBLISHED,
    PUBLISH_STATUS_UNPUBLISHED,
    REVISION_STATUS_APPROVED,
    REVISION_STATUS_PENDING,
    REVISION_STATUS_REJECTED,
)


# Fields the HR Executive can edit on a job. Any field not on this list
# is ignored when building the revision payload — keeps approval-status
# columns from ever being smuggled through the edit endpoint.
JOB_EDITABLE_FIELDS = (
    "slug",
    "title",
    "department",
    "division",
    "company",
    "location",
    "employment_type",
    "min_experience",
    "max_experience",
    "required_education",
    "salary_min",
    "salary_max",
    "visa_requirement",
    "nationality_preference",
    "language_requirement",
    "notice_period_preference",
    "description",
    "responsibilities",
    "requirements",
    "required_skills",
    "preferred_skills",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _public_visible(job: JobOpening) -> bool:
    """Predicate: is this job currently visible to the public site?"""
    return (
        job.status == JOB_STATUS_OPEN
        and job.approval_status == APPROVAL_STATUS_APPROVED
        and job.publish_status == PUBLISH_STATUS_PUBLISHED
    )


def record_approval_history(
    db: Session,
    *,
    job: JobOpening,
    action: str,
    actor: Optional[User],
    old_status: Optional[str],
    new_status: Optional[str],
    remarks: Optional[str] = None,
    changed_fields: Optional[Dict[str, Any]] = None,
    revision_id: Optional[int] = None,
) -> JobApprovalHistory:
    """Persist one row of :class:`JobApprovalHistory`."""

    entry = JobApprovalHistory(
        job_opening_id=job.id,
        action=action,
        old_approval_status=old_status,
        new_approval_status=new_status,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        remarks=remarks,
        changed_fields=changed_fields,
        revision_id=revision_id,
    )
    db.add(entry)
    db.flush()
    return entry


# ---------------------------------------------------------------------------
# Submit / approve / reject / revision flow
# ---------------------------------------------------------------------------


def submit_for_approval(
    db: Session,
    *,
    job: JobOpening,
    actor: User,
    remarks: Optional[str] = None,
) -> JobApprovalHistory:
    """Move a draft (or rejected/revision_required) job into pending_approval."""

    if job.approval_status == APPROVAL_STATUS_PENDING:
        # Idempotent: re-submitting a pending job is a no-op.
        return record_approval_history(
            db,
            job=job,
            action=APPROVAL_ACTION_SUBMITTED,
            actor=actor,
            old_status=APPROVAL_STATUS_PENDING,
            new_status=APPROVAL_STATUS_PENDING,
            remarks=remarks or "Re-submitted (no-op)",
        )

    if job.approval_status not in (
        APPROVAL_STATUS_DRAFT,
        APPROVAL_STATUS_REJECTED,
        APPROVAL_STATUS_REVISION_REQUIRED,
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Job in '{job.approval_status}' status cannot be submitted "
                "for approval."
            ),
        )

    old_status = job.approval_status
    job.approval_status = APPROVAL_STATUS_PENDING
    job.submitted_for_approval_by_id = actor.id
    job.submitted_for_approval_at = _utc_now()
    job.approval_remarks = remarks
    # Submitting always clears any prior rejection metadata.
    job.rejected_by_id = None
    job.rejected_at = None

    return record_approval_history(
        db,
        job=job,
        action=APPROVAL_ACTION_SUBMITTED,
        actor=actor,
        old_status=old_status,
        new_status=APPROVAL_STATUS_PENDING,
        remarks=remarks,
    )


def approve_job(
    db: Session,
    *,
    job: JobOpening,
    actor: User,
    remarks: Optional[str] = None,
    auto_publish: bool = True,
) -> JobApprovalHistory:
    """HR Manager approves the pending job. Optionally publishes immediately."""

    if job.approval_status != APPROVAL_STATUS_PENDING:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Job in '{job.approval_status}' status cannot be approved — "
                "it must be 'pending_approval'."
            ),
        )

    old_status = job.approval_status
    job.approval_status = APPROVAL_STATUS_APPROVED
    job.approved_by_id = actor.id
    job.approved_at = _utc_now()
    job.approval_remarks = remarks
    job.rejected_by_id = None
    job.rejected_at = None

    history = record_approval_history(
        db,
        job=job,
        action=APPROVAL_ACTION_APPROVED,
        actor=actor,
        old_status=old_status,
        new_status=APPROVAL_STATUS_APPROVED,
        remarks=remarks,
    )

    if auto_publish:
        # Approval auto-publishes — make the job visible immediately.
        old_publish = job.publish_status
        job.publish_status = PUBLISH_STATUS_PUBLISHED
        record_approval_history(
            db,
            job=job,
            action=APPROVAL_ACTION_PUBLISHED,
            actor=actor,
            old_status=old_publish,
            new_status=PUBLISH_STATUS_PUBLISHED,
            remarks="Auto-published on approval",
        )

    return history


def reject_job(
    db: Session,
    *,
    job: JobOpening,
    actor: User,
    remarks: str,
) -> JobApprovalHistory:
    """HR Manager rejects the pending job. Reason is mandatory."""

    if not remarks or not remarks.strip():
        raise HTTPException(
            status_code=400, detail="A rejection reason is required."
        )

    if job.approval_status != APPROVAL_STATUS_PENDING:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Job in '{job.approval_status}' status cannot be rejected — "
                "it must be 'pending_approval'."
            ),
        )

    old_status = job.approval_status
    job.approval_status = APPROVAL_STATUS_REJECTED
    job.rejected_by_id = actor.id
    job.rejected_at = _utc_now()
    job.approval_remarks = remarks
    # Rejection on a never-approved job leaves publish_status untouched
    # (still draft). If somehow the job was already published (edge case
    # for a re-review), unpublish it so the public surface stays consistent.
    if job.publish_status == PUBLISH_STATUS_PUBLISHED:
        job.publish_status = PUBLISH_STATUS_UNPUBLISHED

    return record_approval_history(
        db,
        job=job,
        action=APPROVAL_ACTION_REJECTED,
        actor=actor,
        old_status=old_status,
        new_status=APPROVAL_STATUS_REJECTED,
        remarks=remarks,
    )


def request_revision(
    db: Session,
    *,
    job: JobOpening,
    actor: User,
    remarks: Optional[str] = None,
) -> JobApprovalHistory:
    """HR Manager sends the pending job back to HR Executive for changes."""

    if job.approval_status != APPROVAL_STATUS_PENDING:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Job in '{job.approval_status}' status cannot have a "
                "revision requested — it must be 'pending_approval'."
            ),
        )

    old_status = job.approval_status
    job.approval_status = APPROVAL_STATUS_REVISION_REQUIRED
    job.approval_remarks = remarks

    return record_approval_history(
        db,
        job=job,
        action=APPROVAL_ACTION_REVISION_REQUESTED,
        actor=actor,
        old_status=old_status,
        new_status=APPROVAL_STATUS_REVISION_REQUIRED,
        remarks=remarks,
    )


def publish_job(
    db: Session,
    *,
    job: JobOpening,
    actor: User,
    remarks: Optional[str] = None,
) -> JobApprovalHistory:
    """Toggle publish_status to published. Requires approval_status='approved'."""

    if job.approval_status != APPROVAL_STATUS_APPROVED:
        raise HTTPException(
            status_code=409,
            detail="Only approved jobs can be published.",
        )

    if job.publish_status == PUBLISH_STATUS_PUBLISHED:
        return record_approval_history(
            db,
            job=job,
            action=APPROVAL_ACTION_PUBLISHED,
            actor=actor,
            old_status=PUBLISH_STATUS_PUBLISHED,
            new_status=PUBLISH_STATUS_PUBLISHED,
            remarks=remarks or "Already published (no-op)",
        )

    old_publish = job.publish_status
    job.publish_status = PUBLISH_STATUS_PUBLISHED

    return record_approval_history(
        db,
        job=job,
        action=APPROVAL_ACTION_PUBLISHED,
        actor=actor,
        old_status=old_publish,
        new_status=PUBLISH_STATUS_PUBLISHED,
        remarks=remarks,
    )


def unpublish_job(
    db: Session,
    *,
    job: JobOpening,
    actor: User,
    remarks: Optional[str] = None,
) -> JobApprovalHistory:
    """Hide an approved job from the public site without changing approval."""

    if job.publish_status != PUBLISH_STATUS_PUBLISHED:
        return record_approval_history(
            db,
            job=job,
            action=APPROVAL_ACTION_UNPUBLISHED,
            actor=actor,
            old_status=job.publish_status,
            new_status=job.publish_status,
            remarks=remarks or "Already unpublished (no-op)",
        )

    old_publish = job.publish_status
    job.publish_status = PUBLISH_STATUS_UNPUBLISHED

    return record_approval_history(
        db,
        job=job,
        action=APPROVAL_ACTION_UNPUBLISHED,
        actor=actor,
        old_status=old_publish,
        new_status=PUBLISH_STATUS_UNPUBLISHED,
        remarks=remarks,
    )


# ---------------------------------------------------------------------------
# Revision flow (editing an approved/published job)
# ---------------------------------------------------------------------------


def _strip_to_editable(changes: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in changes.items() if k in JOB_EDITABLE_FIELDS}


def _job_snapshot(job: JobOpening) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {}
    for field in JOB_EDITABLE_FIELDS:
        snapshot[field] = getattr(job, field, None)
    return snapshot


def apply_edit(
    db: Session,
    *,
    job: JobOpening,
    changes: Dict[str, Any],
    actor: User,
) -> Tuple[JobOpening, Optional[JobRevision]]:
    """Apply an HR-Executive edit. Returns (job, revision-or-None).

    When the job is in draft / rejected / revision_required, the edit is
    applied directly to ``job``. When the job is already approved (and
    therefore potentially live to the public), the changes are stored as
    a pending :class:`JobRevision` instead — the public job stays
    unchanged until the HR Manager approves the revision.
    """
    editable = _strip_to_editable(changes)
    if not editable:
        return job, None

    direct_states = (
        APPROVAL_STATUS_DRAFT,
        APPROVAL_STATUS_REJECTED,
        APPROVAL_STATUS_REVISION_REQUIRED,
    )

    if job.approval_status in direct_states:
        # Apply directly.
        for k, v in editable.items():
            setattr(job, k, v)
        db.flush()
        return job, None

    # Approved (and possibly pending) jobs route through revisions. If
    # there's already a pending revision, update it rather than spawning
    # a duplicate so HR Manager always sees the latest pending payload.
    revision = _find_pending_revision(db, job)
    if revision is None:
        revision = JobRevision(
            job_opening_id=job.id,
            payload=editable,
            status=REVISION_STATUS_PENDING,
            created_by_id=actor.id,
        )
        db.add(revision)
    else:
        merged = dict(revision.payload or {})
        merged.update(editable)
        revision.payload = merged
        revision.created_by_id = actor.id  # last editor wins

    db.flush()
    job.active_revision_id = revision.id

    record_approval_history(
        db,
        job=job,
        action=APPROVAL_ACTION_REVISION_SUBMITTED,
        actor=actor,
        old_status=job.approval_status,
        new_status=job.approval_status,
        remarks=None,
        changed_fields=editable,
        revision_id=revision.id,
    )
    return job, revision


def _find_pending_revision(db: Session, job: JobOpening) -> Optional[JobRevision]:
    return next(
        (r for r in job.revisions if r.status == REVISION_STATUS_PENDING),
        None,
    )


def approve_revision(
    db: Session,
    *,
    revision: JobRevision,
    actor: User,
    remarks: Optional[str] = None,
) -> JobOpening:
    """Apply a pending revision's payload to its JobOpening and republish."""

    if revision.status != REVISION_STATUS_PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Revision is already '{revision.status}'.",
        )

    job = revision.job_opening
    snapshot = _job_snapshot(job)

    for k, v in (revision.payload or {}).items():
        if k in JOB_EDITABLE_FIELDS:
            setattr(job, k, v)

    revision.status = REVISION_STATUS_APPROVED
    revision.reviewed_by_id = actor.id
    revision.reviewed_at = _utc_now()
    revision.remarks = remarks
    job.active_revision_id = None

    record_approval_history(
        db,
        job=job,
        action=APPROVAL_ACTION_APPROVED,
        actor=actor,
        old_status=job.approval_status,
        new_status=job.approval_status,
        remarks=remarks,
        changed_fields={
            "applied_keys": list((revision.payload or {}).keys()),
            "previous": {
                k: snapshot.get(k) for k in (revision.payload or {}).keys()
            },
        },
        revision_id=revision.id,
    )
    return job


def reject_revision(
    db: Session,
    *,
    revision: JobRevision,
    actor: User,
    remarks: str,
) -> JobRevision:
    """Reject a pending revision without changing the public job content."""

    if not remarks or not remarks.strip():
        raise HTTPException(
            status_code=400, detail="A rejection reason is required."
        )

    if revision.status != REVISION_STATUS_PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Revision is already '{revision.status}'.",
        )

    revision.status = REVISION_STATUS_REJECTED
    revision.reviewed_by_id = actor.id
    revision.reviewed_at = _utc_now()
    revision.remarks = remarks

    job = revision.job_opening
    if job.active_revision_id == revision.id:
        job.active_revision_id = None

    record_approval_history(
        db,
        job=job,
        action=APPROVAL_ACTION_REJECTED,
        actor=actor,
        old_status=job.approval_status,
        new_status=job.approval_status,
        remarks=remarks,
        revision_id=revision.id,
    )
    return revision


# ---------------------------------------------------------------------------
# Helpers exposed to endpoints
# ---------------------------------------------------------------------------


def get_pending_revision(
    db: Optional[Session], job: JobOpening
) -> Optional[JobRevision]:
    """Public helper so endpoints don't reach into private internals.

    ``db`` is accepted for symmetry with the rest of this module but the
    lookup walks ``job.revisions`` (loaded via SQLAlchemy's selectin
    eager-loading) so a session reference is not actually needed.
    """
    return _find_pending_revision(db, job) if db is not None else next(
        (r for r in job.revisions if r.status == REVISION_STATUS_PENDING),
        None,
    )


def is_publicly_visible(job: JobOpening) -> bool:
    return _public_visible(job)


def list_approval_history(db: Session, job_id: int) -> List[JobApprovalHistory]:
    from sqlalchemy import select

    return list(
        db.execute(
            select(JobApprovalHistory)
            .where(JobApprovalHistory.job_opening_id == job_id)
            .order_by(JobApprovalHistory.created_at.desc(), JobApprovalHistory.id.desc())
        )
        .scalars()
    )

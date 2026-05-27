"""HR Offers — Phase 6 lifecycle endpoints.

All routes require an HR-scoped token (defence in depth via the
router-level require_hr_admin) and a specific permission per-route.
The hr:offers:* permission family from Phase 1 gates each action:

    list / detail / status-history     -> hr:offers:view
    create / update draft              -> hr:offers:create
    submit-approval / withdraw         -> hr:offers:create
    approve / reject (internal)        -> hr:offers:approve
    issue / record response /
    mark joined / not-joined           -> hr:offers:create
    delete                             -> hr:offers:delete

Approve enforces the "cannot approve own submission" guard from
Phase 1 — the user who created the offer cannot approve it.

Email notifications:
The offer-issued path emails the candidate; the joining-pending path
emails the candidate; both go through hr_notifications and fail-soft.
Templates that don't exist yet log a warning but don't break the
transaction (matches the existing pattern for the few interview
templates that were added before their email designs landed).
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_request_context,
    require_hr_admin,
    require_permission,
)
from app.auth.permissions import (
    PERM_HR_OFFERS_APPROVE,
    PERM_HR_OFFERS_CREATE,
    PERM_HR_OFFERS_DELETE,
    PERM_HR_OFFERS_VIEW,
)
from app.core.database import get_db
from app.models.auth import User
from app.models.hr_ats import (
    OFFER_ACCEPTED,
    OFFER_APPROVED,
    OFFER_DECLINED,
    OFFER_JOINED,
    OFFER_NOT_JOINED,
    OFFER_PENDING_APPROVAL,
    OFFER_SENT,
    OFFER_WITHDRAWN,
    CandidateJobApplication,
    OfferStatusHistory,
    OfferTracking,
)
from app.schemas.hr_ats import (
    OfferActionRequest,
    OfferCreate,
    OfferMarkNotJoinedRequest,
    OfferRead,
    OfferRejectRequest,
    OfferResponseRequest,
    OfferStatusHistoryRead,
    OfferSummaryStats,
    OfferUpdate,
)
from app.services import offers as offer_svc
from app.services.audit_log import record_audit


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/hr/offers",
    tags=["HR ATS - Offers"],
    dependencies=[Depends(require_hr_admin)],
)


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------


def _serialize_offer(offer: OfferTracking) -> OfferRead:
    """Hydrate an OfferRead with the joined candidate + job fields the
    UI needs (so it doesn't have to make a second call for every row)."""
    app = offer.application
    candidate = app.candidate if app else None
    job = app.job_opening if app else None
    base = OfferRead.model_validate(offer).model_dump()
    base.update(
        {
            "candidate_id": candidate.id if candidate else None,
            "candidate_name": candidate.full_name if candidate else None,
            "candidate_email": candidate.email if candidate else None,
            "job_title": job.title if job else None,
            "job_slug": job.slug if job else None,
            "department": job.department if job else None,
        }
    )
    return OfferRead(**base)


def _get_or_404(db: Session, offer_id: int) -> OfferTracking:
    offer = db.get(OfferTracking, offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


def _get_application_or_404(
    db: Session, application_id: int
) -> CandidateJobApplication:
    app = db.get(CandidateJobApplication, application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


def _assert_not_self_approval(offer: OfferTracking, user: User) -> None:
    """Mirrors the job-approval rule: the offer's creator (HR Admin)
    cannot approve it. Manager must be a different user. Super admin
    bypasses for emergency unblocks."""
    if user.is_superuser:
        return
    if offer.created_by_id == user.id:
        raise HTTPException(
            status_code=403,
            detail=(
                "You cannot approve an offer you created — ask another "
                "HR Manager to review it."
            ),
        )


def _audit(
    db: Session,
    user: User,
    request: Optional[Request],
    *,
    action: str,
    offer_id: int,
    details: Optional[dict] = None,
) -> None:
    ctx = get_request_context(request) if request is not None else {
        "ip_address": None,
        "user_agent": None,
    }
    record_audit(
        db,
        action=action,
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="offer",
        target_id=str(offer_id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details=details or {},
        commit=False,
    )


def _notify_safe(name: str, **kwargs) -> None:
    """Call hr_notifications.<name>(**kwargs) and swallow any error.

    Notification helpers for offer events are added incrementally —
    older deployments may not have them yet. Missing helpers log a
    warning rather than raising.
    """
    try:
        from app.services import hr_notifications  # local import
    except Exception:  # pragma: no cover
        return
    func = getattr(hr_notifications, name, None)
    if func is None:
        logger.info("hr_notifications.%s not present — skipping", name)
        return
    try:
        func(**kwargs)
    except Exception:  # pragma: no cover
        logger.exception("HR notification %s failed", name)


# ---------------------------------------------------------------------------
# List / detail / dashboard
# ---------------------------------------------------------------------------


@router.get("", response_model=List[OfferRead])
def list_offers(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_VIEW)),
    status: Optional[str] = Query(default=None, max_length=40),
    job_slug: Optional[str] = Query(default=None, max_length=200),
    department: Optional[str] = Query(default=None, max_length=120),
    limit: int = Query(default=200, ge=1, le=500),
) -> List[OfferRead]:
    stmt = select(OfferTracking).order_by(desc(OfferTracking.created_at)).limit(limit)
    if status:
        stmt = stmt.where(OfferTracking.status == status)
    offers = list(db.execute(stmt).scalars())
    # Apply job filters in Python — small dataset, keeps the SQL simple.
    if job_slug or department:
        filtered = []
        for o in offers:
            job = o.application.job_opening if o.application else None
            if job_slug and (not job or job.slug != job_slug):
                continue
            if department and (not job or job.department != department):
                continue
            filtered.append(o)
        offers = filtered
    return [_serialize_offer(o) for o in offers]


@router.get("/stats", response_model=OfferSummaryStats)
def offer_stats(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_VIEW)),
) -> OfferSummaryStats:
    """Return per-bucket counts for the /hr/offers dashboard cards."""
    rows = list(db.execute(select(OfferTracking.status)).scalars())
    stats = OfferSummaryStats()
    counter = {
        OFFER_PENDING_APPROVAL: "pending_approval",
        OFFER_APPROVED: "approved",
        OFFER_SENT: "sent",
        OFFER_ACCEPTED: "accepted",
        OFFER_DECLINED: "declined",
        OFFER_WITHDRAWN: "withdrawn",
        OFFER_JOINED: "joined",
        OFFER_NOT_JOINED: "not_joined",
    }
    for status in rows:
        attr = counter.get(status)
        if attr is not None:
            setattr(stats, attr, getattr(stats, attr) + 1)
    return stats


@router.get("/{offer_id}", response_model=OfferRead)
def get_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_VIEW)),
) -> OfferRead:
    offer = _get_or_404(db, offer_id)
    return _serialize_offer(offer)


@router.get(
    "/{offer_id}/status-history",
    response_model=List[OfferStatusHistoryRead],
)
def get_offer_status_history(
    offer_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_VIEW)),
) -> List[OfferStatusHistoryRead]:
    offer = _get_or_404(db, offer_id)
    return [OfferStatusHistoryRead.model_validate(h) for h in offer.status_history]


# ---------------------------------------------------------------------------
# Create / update draft
# ---------------------------------------------------------------------------


@router.post("", response_model=OfferRead, status_code=201)
def create_offer_endpoint(
    payload: OfferCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_CREATE)),
) -> OfferRead:
    application = _get_application_or_404(db, payload.application_id)

    try:
        offer = offer_svc.create_offer(
            db,
            application=application,
            actor=user,
            payload=offer_svc.OfferCreatePayload(
                position=payload.position,
                salary_offered=payload.salary_offered,
                allowances=payload.allowances,
                joining_date=payload.joining_date,
                probation_period=payload.probation_period,
                reporting_manager=payload.reporting_manager,
                work_location=payload.work_location,
                benefits_summary=payload.benefits_summary,
                remarks=payload.remarks,
            ),
        )
    except offer_svc.OfferPreconditionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _audit(
        db,
        user,
        request,
        action="hr.offer.create",
        offer_id=offer.id,
        details={"application_id": application.id},
    )
    db.commit()
    db.refresh(offer)
    return _serialize_offer(offer)


@router.patch("/{offer_id}", response_model=OfferRead)
def update_offer_endpoint(
    offer_id: int,
    payload: OfferUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_CREATE)),
) -> OfferRead:
    offer = _get_or_404(db, offer_id)
    try:
        offer_svc.update_draft(
            db,
            offer=offer,
            actor=user,
            changes=payload.model_dump(exclude_unset=True),
        )
    except offer_svc.InvalidOfferTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _audit(db, user, request, action="hr.offer.update", offer_id=offer.id)
    db.commit()
    db.refresh(offer)
    return _serialize_offer(offer)


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


@router.post("/{offer_id}/submit-approval", response_model=OfferRead)
def submit_for_approval_endpoint(
    offer_id: int,
    payload: Optional[OfferActionRequest] = None,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_CREATE)),
) -> OfferRead:
    offer = _get_or_404(db, offer_id)
    try:
        offer_svc.submit_for_approval(
            db,
            offer=offer,
            actor=user,
            remarks=payload.remarks if payload else None,
        )
    except offer_svc.InvalidOfferTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _audit(db, user, request, action="hr.offer.submit_approval", offer_id=offer.id)
    db.commit()
    db.refresh(offer)
    _notify_safe(
        "notify_offer_approval_requested", offer_id=offer.id, actor_id=user.id
    )
    return _serialize_offer(offer)


@router.post("/{offer_id}/approve", response_model=OfferRead)
def approve_offer_endpoint(
    offer_id: int,
    payload: Optional[OfferActionRequest] = None,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_APPROVE)),
) -> OfferRead:
    offer = _get_or_404(db, offer_id)
    _assert_not_self_approval(offer, user)
    try:
        offer_svc.approve(
            db,
            offer=offer,
            actor=user,
            remarks=payload.remarks if payload else None,
        )
    except offer_svc.InvalidOfferTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _audit(db, user, request, action="hr.offer.approve", offer_id=offer.id)
    db.commit()
    db.refresh(offer)
    _notify_safe("notify_offer_approved", offer_id=offer.id, actor_id=user.id)
    return _serialize_offer(offer)


@router.post("/{offer_id}/reject", response_model=OfferRead)
def reject_offer_endpoint(
    offer_id: int,
    payload: OfferRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_APPROVE)),
) -> OfferRead:
    """Manager rejects (internal) — kicks the offer back to draft."""
    offer = _get_or_404(db, offer_id)
    _assert_not_self_approval(offer, user)
    try:
        offer_svc.reject_internal(db, offer=offer, actor=user, reason=payload.remarks)
    except offer_svc.InvalidOfferTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _audit(
        db,
        user,
        request,
        action="hr.offer.reject_internal",
        offer_id=offer.id,
        details={"remarks": payload.remarks},
    )
    db.commit()
    db.refresh(offer)
    return _serialize_offer(offer)


@router.post("/{offer_id}/issue", response_model=OfferRead)
def issue_offer_endpoint(
    offer_id: int,
    payload: Optional[OfferActionRequest] = None,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_CREATE)),
) -> OfferRead:
    offer = _get_or_404(db, offer_id)
    try:
        offer_svc.issue(
            db,
            offer=offer,
            actor=user,
            remarks=payload.remarks if payload else None,
        )
    except offer_svc.InvalidOfferTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _audit(
        db,
        user,
        request,
        action="hr.offer.issue",
        offer_id=offer.id,
        details={"offer_letter_number": offer.offer_letter_number},
    )
    db.commit()
    db.refresh(offer)

    # Fire-and-forget candidate notification.
    _notify_safe("notify_offer_issued", offer_id=offer.id, actor_id=user.id)
    return _serialize_offer(offer)


@router.post("/{offer_id}/respond", response_model=OfferRead)
def respond_offer_endpoint(
    offer_id: int,
    payload: OfferResponseRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_CREATE)),
) -> OfferRead:
    """HR records the candidate's response — accepted=true means
    accepted; false plus an optional decline_reason means declined."""
    offer = _get_or_404(db, offer_id)
    try:
        offer_svc.record_response(
            db,
            offer=offer,
            actor=user,
            accepted=payload.accepted,
            decline_reason=payload.decline_reason,
        )
    except offer_svc.InvalidOfferTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _audit(
        db,
        user,
        request,
        action=("hr.offer.accept" if payload.accepted else "hr.offer.decline"),
        offer_id=offer.id,
        details={"decline_reason": payload.decline_reason},
    )
    db.commit()
    db.refresh(offer)
    _notify_safe(
        "notify_offer_accepted" if payload.accepted else "notify_offer_declined",
        offer_id=offer.id,
        actor_id=user.id,
    )
    return _serialize_offer(offer)


@router.post("/{offer_id}/mark-joined", response_model=OfferRead)
def mark_joined_endpoint(
    offer_id: int,
    payload: Optional[OfferActionRequest] = None,
    request: Request = None,  # type: ignore[assignment]
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_CREATE)),
) -> OfferRead:
    offer = _get_or_404(db, offer_id)
    try:
        offer_svc.mark_joined(
            db,
            offer=offer,
            actor=user,
            remarks=payload.remarks if payload else None,
        )
    except offer_svc.InvalidOfferTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _audit(db, user, request, action="hr.offer.mark_joined", offer_id=offer.id)
    db.commit()
    db.refresh(offer)
    _notify_safe("notify_offer_joined", offer_id=offer.id, actor_id=user.id)
    return _serialize_offer(offer)


@router.post("/{offer_id}/mark-not-joined", response_model=OfferRead)
def mark_not_joined_endpoint(
    offer_id: int,
    payload: OfferMarkNotJoinedRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_CREATE)),
) -> OfferRead:
    offer = _get_or_404(db, offer_id)
    try:
        offer_svc.mark_not_joined(db, offer=offer, actor=user, reason=payload.reason)
    except offer_svc.InvalidOfferTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _audit(
        db,
        user,
        request,
        action="hr.offer.mark_not_joined",
        offer_id=offer.id,
        details={"reason": payload.reason},
    )
    db.commit()
    db.refresh(offer)
    return _serialize_offer(offer)


@router.post("/{offer_id}/withdraw", response_model=OfferRead)
def withdraw_offer_endpoint(
    offer_id: int,
    payload: OfferRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_CREATE)),
) -> OfferRead:
    """Withdraw the offer at any non-terminal stage. Requires a remarks
    string (min 4 chars, enforced by OfferRejectRequest schema)."""
    offer = _get_or_404(db, offer_id)
    try:
        offer_svc.withdraw(db, offer=offer, actor=user, reason=payload.remarks)
    except offer_svc.InvalidOfferTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _audit(
        db,
        user,
        request,
        action="hr.offer.withdraw",
        offer_id=offer.id,
        details={"reason": payload.remarks},
    )
    db.commit()
    db.refresh(offer)
    return _serialize_offer(offer)


@router.delete("/{offer_id}", status_code=204)
def delete_offer_endpoint(
    offer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_OFFERS_DELETE)),
):
    """Delete an offer. Only allowed in draft / rejected-internal state
    — once issued (sent) or beyond, deleting would destroy the
    candidate-facing record. Withdraw instead."""
    offer = _get_or_404(db, offer_id)
    from app.models.hr_ats import OFFER_DRAFT

    if offer.status != OFFER_DRAFT:
        raise HTTPException(
            status_code=409,
            detail=(
                "Only draft offers can be deleted. To rescind an issued "
                "offer, use /withdraw instead."
            ),
        )
    _audit(db, user, request, action="hr.offer.delete", offer_id=offer.id)
    db.delete(offer)
    db.commit()

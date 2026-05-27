"""Offer lifecycle service (Phase 6).

State machine
=============

Lifecycle states (the ``status`` column on hr_offer_tracking):

    draft              - HR Admin drafted; not yet visible to manager
    pending_approval   - HR Admin submitted; awaiting HR Manager review
    approved           - HR Manager signed off; ready to issue
    sent               - issued to candidate (alias OFFER_SENT — kept
                         for back-compat). Candidate now sees it.
    accepted           - candidate said yes; joining tracker activates
    declined           - candidate said no (terminal)
    withdrawn          - HR withdrew the offer (terminal)
    joined             - candidate showed up (terminal)
    not_joined         - candidate didn't show up after accepting
                         (terminal)

Allowed transitions
-------------------

    draft              -> pending_approval, withdrawn
    pending_approval   -> approved, draft (request changes),
                          withdrawn
    approved           -> sent, withdrawn
    sent               -> accepted, declined, withdrawn
    accepted           -> joined, not_joined, withdrawn
    declined           -> (terminal)
    withdrawn          -> (terminal)
    joined             -> (terminal)
    not_joined         -> (terminal)

Each transition writes a row to hr_offer_status_history. ``joined`` /
``not_joined`` ALSO pushes the underlying CandidateJobApplication
status to STATUS_JOINED / STATUS_NOT_JOINED — this is the only place
in the codebase where the offer module mutates the recruitment
status, and it matches the master plan's explicit rule.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional, Set

from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.hr_ats import (
    OFFER_ACCEPTED,
    OFFER_APPROVAL_APPROVED,
    OFFER_APPROVAL_DRAFT,
    OFFER_APPROVAL_PENDING,
    OFFER_APPROVAL_REJECTED,
    OFFER_APPROVED,
    OFFER_DECLINED,
    OFFER_DRAFT,
    OFFER_JOINED,
    OFFER_JOINING_JOINED,
    OFFER_JOINING_NOT_JOINED,
    OFFER_JOINING_PENDING,
    OFFER_NOT_JOINED,
    OFFER_PENDING_APPROVAL,
    OFFER_SENT,
    OFFER_WITHDRAWN,
    STATUS_JOINED,
    STATUS_NOT_JOINED,
    STATUS_OFFER_SENT,
    STATUS_RECOMMENDED_FOR_OFFER,
    STATUS_SELECTED,
    CandidateJobApplication,
    CandidateStatusHistory,
    OfferStatusHistory,
    OfferTracking,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class OfferError(Exception):
    """Base class for offer-workflow violations."""


class InvalidOfferTransitionError(OfferError):
    """Raised when an action isn't allowed for the current status."""


class OfferPreconditionError(OfferError):
    """Raised when the candidate/application isn't in a state that
    permits offer creation (e.g. trying to create an offer for a CV-only
    candidate)."""


# ---------------------------------------------------------------------------
# Transition graph
# ---------------------------------------------------------------------------


ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    OFFER_DRAFT: {OFFER_PENDING_APPROVAL, OFFER_WITHDRAWN},
    # Manager can either approve, send back to draft (request changes), or withdraw.
    OFFER_PENDING_APPROVAL: {OFFER_APPROVED, OFFER_DRAFT, OFFER_WITHDRAWN},
    OFFER_APPROVED: {OFFER_SENT, OFFER_WITHDRAWN},
    OFFER_SENT: {OFFER_ACCEPTED, OFFER_DECLINED, OFFER_WITHDRAWN},
    OFFER_ACCEPTED: {OFFER_JOINED, OFFER_NOT_JOINED, OFFER_WITHDRAWN},
    # Terminal — no outbound transitions.
    OFFER_DECLINED: set(),
    OFFER_WITHDRAWN: set(),
    OFFER_JOINED: set(),
    OFFER_NOT_JOINED: set(),
}


# Applications whose recruitment status permits creating a new offer.
APPLICATION_STATUSES_PERMITTING_OFFER = (
    STATUS_RECOMMENDED_FOR_OFFER,
    STATUS_SELECTED,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _record_history(
    db: Session,
    *,
    offer: OfferTracking,
    action: str,
    actor: Optional[User],
    old_status: Optional[str],
    new_status: Optional[str],
    remarks: Optional[str] = None,
) -> OfferStatusHistory:
    entry = OfferStatusHistory(
        offer_id=offer.id,
        action=action,
        old_status=old_status,
        new_status=new_status,
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        remarks=remarks,
    )
    db.add(entry)
    db.flush()
    return entry


def _assert_transition(current: str, next_status: str) -> None:
    if next_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidOfferTransitionError(
            f"Cannot move offer from '{current}' to '{next_status}'."
        )


def _push_application_status(
    db: Session,
    *,
    application: CandidateJobApplication,
    target_status: str,
    actor: Optional[User],
    remarks: Optional[str] = None,
) -> None:
    """When the offer hits a terminal joining state, mirror that into
    the candidate's recruitment status — and record the change in
    hr_candidate_status_history so the candidate timeline stays in sync.

    Best-effort: if the candidate is already in that status (e.g. HR
    manually moved them ahead of the offer), this is a no-op.
    """
    if application.status == target_status:
        return
    old = application.status
    application.status = target_status
    db.add(
        CandidateStatusHistory(
            application_id=application.id,
            old_status=old,
            new_status=target_status,
            changed_by_id=actor.id if actor else None,
            remarks=remarks or "Status updated via offer workflow.",
        )
    )


def _gen_offer_letter_number(offer: OfferTracking) -> str:
    """Deterministic-ish letter number: YYYYMM-{offer_id:06d}-{rand4}."""
    today = date.today()
    suffix = secrets.token_hex(2)
    return f"OL-{today.strftime('%Y%m')}-{offer.id:06d}-{suffix}"


# ---------------------------------------------------------------------------
# Lifecycle API used by hr_offers.py endpoints
# ---------------------------------------------------------------------------


@dataclass
class OfferCreatePayload:
    """Shape passed by the endpoint after Pydantic validation."""

    position: Optional[str] = None
    salary_offered: Optional[int] = None
    allowances: Optional[str] = None
    joining_date: Optional[date] = None
    probation_period: Optional[str] = None
    reporting_manager: Optional[str] = None
    work_location: Optional[str] = None
    benefits_summary: Optional[str] = None
    remarks: Optional[str] = None


def create_offer(
    db: Session,
    *,
    application: CandidateJobApplication,
    actor: User,
    payload: OfferCreatePayload,
) -> OfferTracking:
    """Create a draft offer for an eligible application.

    Eligibility: the candidate's recruitment status must be in
    APPLICATION_STATUSES_PERMITTING_OFFER. One offer per application
    (enforced by the UNIQUE constraint on application_id).
    """
    if application.status not in APPLICATION_STATUSES_PERMITTING_OFFER:
        raise OfferPreconditionError(
            "Offer can only be drafted for candidates with status "
            f"in {APPLICATION_STATUSES_PERMITTING_OFFER}; current = "
            f"'{application.status}'."
        )
    if application.offer is not None:
        raise OfferPreconditionError(
            "An offer already exists for this application; edit it instead."
        )

    offer = OfferTracking(
        application_id=application.id,
        position=payload.position,
        salary_offered=payload.salary_offered,
        allowances=payload.allowances,
        joining_date=payload.joining_date,
        probation_period=payload.probation_period,
        reporting_manager=payload.reporting_manager,
        work_location=payload.work_location,
        benefits_summary=payload.benefits_summary,
        remarks=payload.remarks,
        status=OFFER_DRAFT,
        approval_status=OFFER_APPROVAL_DRAFT,
        created_by_id=actor.id,
    )
    db.add(offer)
    db.flush()
    _record_history(
        db,
        offer=offer,
        action="created",
        actor=actor,
        old_status=None,
        new_status=OFFER_DRAFT,
    )
    return offer


def update_draft(
    db: Session,
    *,
    offer: OfferTracking,
    actor: User,
    changes: Dict[str, Any],
) -> OfferTracking:
    """Edit a draft / pending_approval / approved offer's content.

    Once the offer is issued (sent) or in a terminal state the
    content is frozen.
    """
    if offer.status not in (OFFER_DRAFT, OFFER_PENDING_APPROVAL, OFFER_APPROVED):
        raise InvalidOfferTransitionError(
            f"Cannot edit offer content in '{offer.status}' status."
        )
    editable = {
        "position",
        "salary_offered",
        "allowances",
        "joining_date",
        "probation_period",
        "reporting_manager",
        "work_location",
        "benefits_summary",
        "offer_letter_number",
        "attachment_url",
        "remarks",
    }
    touched: list[str] = []
    for k, v in changes.items():
        if k not in editable:
            continue
        setattr(offer, k, v)
        touched.append(k)
    if touched:
        _record_history(
            db,
            offer=offer,
            action="edited",
            actor=actor,
            old_status=offer.status,
            new_status=offer.status,
            remarks=f"Fields updated: {', '.join(sorted(touched))}",
        )
    db.flush()
    return offer


def submit_for_approval(
    db: Session, *, offer: OfferTracking, actor: User, remarks: Optional[str] = None
) -> OfferTracking:
    _assert_transition(offer.status, OFFER_PENDING_APPROVAL)
    old = offer.status
    offer.status = OFFER_PENDING_APPROVAL
    offer.approval_status = OFFER_APPROVAL_PENDING
    _record_history(
        db,
        offer=offer,
        action="submit_approval",
        actor=actor,
        old_status=old,
        new_status=OFFER_PENDING_APPROVAL,
        remarks=remarks,
    )
    return offer


def approve(
    db: Session, *, offer: OfferTracking, actor: User, remarks: Optional[str] = None
) -> OfferTracking:
    _assert_transition(offer.status, OFFER_APPROVED)
    old = offer.status
    offer.status = OFFER_APPROVED
    offer.approval_status = OFFER_APPROVAL_APPROVED
    offer.approved_by_id = actor.id
    offer.approved_at = _utc_now()
    _record_history(
        db,
        offer=offer,
        action="approve",
        actor=actor,
        old_status=old,
        new_status=OFFER_APPROVED,
        remarks=remarks,
    )
    return offer


def reject_internal(
    db: Session,
    *,
    offer: OfferTracking,
    actor: User,
    reason: str,
) -> OfferTracking:
    """Internal rejection — manager refuses to approve. Sends the
    offer back to draft for HR to revise. NOT the same as candidate
    declining."""
    _assert_transition(offer.status, OFFER_DRAFT)
    old = offer.status
    offer.status = OFFER_DRAFT
    offer.approval_status = OFFER_APPROVAL_REJECTED
    offer.rejected_by_id = actor.id
    offer.rejected_at = _utc_now()
    offer.rejection_reason = reason
    _record_history(
        db,
        offer=offer,
        action="reject_internal",
        actor=actor,
        old_status=old,
        new_status=OFFER_DRAFT,
        remarks=reason,
    )
    return offer


def issue(
    db: Session,
    *,
    offer: OfferTracking,
    actor: User,
    remarks: Optional[str] = None,
) -> OfferTracking:
    """Send the approved offer to the candidate. Auto-assigns an offer
    letter number if HR hasn't set one. Mirrors application status to
    'offer_sent'."""
    _assert_transition(offer.status, OFFER_SENT)
    if not offer.offer_letter_number:
        offer.offer_letter_number = _gen_offer_letter_number(offer)
    old = offer.status
    offer.status = OFFER_SENT
    offer.issued_by_id = actor.id
    offer.issued_at = _utc_now()
    offer.sent_at = _utc_now()  # legacy alias
    _record_history(
        db,
        offer=offer,
        action="issue",
        actor=actor,
        old_status=old,
        new_status=OFFER_SENT,
        remarks=remarks,
    )
    # Recruitment status follows the offer — only push if not already there.
    _push_application_status(
        db,
        application=offer.application,
        target_status=STATUS_OFFER_SENT,
        actor=actor,
        remarks="Offer issued to candidate.",
    )
    return offer


def record_response(
    db: Session,
    *,
    offer: OfferTracking,
    actor: User,
    accepted: bool,
    decline_reason: Optional[str] = None,
) -> OfferTracking:
    """HR records the candidate's response."""
    next_status = OFFER_ACCEPTED if accepted else OFFER_DECLINED
    _assert_transition(offer.status, next_status)
    old = offer.status
    offer.status = next_status
    offer.responded_at = _utc_now()
    if accepted:
        offer.accepted_at = _utc_now()
        offer.joining_status = OFFER_JOINING_PENDING
    else:
        offer.declined_at = _utc_now()
        offer.decline_reason = decline_reason
    _record_history(
        db,
        offer=offer,
        action="accept" if accepted else "decline",
        actor=actor,
        old_status=old,
        new_status=next_status,
        remarks=decline_reason,
    )
    return offer


def mark_joined(
    db: Session,
    *,
    offer: OfferTracking,
    actor: User,
    remarks: Optional[str] = None,
) -> OfferTracking:
    _assert_transition(offer.status, OFFER_JOINED)
    old = offer.status
    offer.status = OFFER_JOINED
    offer.joining_status = OFFER_JOINING_JOINED
    offer.joined_at = _utc_now()
    _record_history(
        db,
        offer=offer,
        action="mark_joined",
        actor=actor,
        old_status=old,
        new_status=OFFER_JOINED,
        remarks=remarks,
    )
    _push_application_status(
        db,
        application=offer.application,
        target_status=STATUS_JOINED,
        actor=actor,
        remarks="Candidate joined.",
    )
    return offer


def mark_not_joined(
    db: Session,
    *,
    offer: OfferTracking,
    actor: User,
    reason: Optional[str] = None,
) -> OfferTracking:
    _assert_transition(offer.status, OFFER_NOT_JOINED)
    old = offer.status
    offer.status = OFFER_NOT_JOINED
    offer.joining_status = OFFER_JOINING_NOT_JOINED
    offer.not_joined_reason = reason
    _record_history(
        db,
        offer=offer,
        action="mark_not_joined",
        actor=actor,
        old_status=old,
        new_status=OFFER_NOT_JOINED,
        remarks=reason,
    )
    _push_application_status(
        db,
        application=offer.application,
        target_status=STATUS_NOT_JOINED,
        actor=actor,
        remarks=f"Candidate did not join. Reason: {reason or 'unspecified'}",
    )
    return offer


def withdraw(
    db: Session,
    *,
    offer: OfferTracking,
    actor: User,
    reason: str,
) -> OfferTracking:
    """HR rescinds the offer. Allowed from any non-terminal state."""
    _assert_transition(offer.status, OFFER_WITHDRAWN)
    old = offer.status
    offer.status = OFFER_WITHDRAWN
    offer.withdrawn_by_id = actor.id
    offer.withdrawn_at = _utc_now()
    offer.withdrawn_reason = reason
    _record_history(
        db,
        offer=offer,
        action="withdraw",
        actor=actor,
        old_status=old,
        new_status=OFFER_WITHDRAWN,
        remarks=reason,
    )
    return offer

"""HR offer-letter template CRUD + merge-field metadata.

Templates carry a body with ``{{token}}`` merge fields; HR applies one to
an offer (see ``POST /hr/offers/{id}/apply-template`` in
:mod:`app.api.endpoints.hr_offers`) which renders + stores the body.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_request_context,
    require_hr_admin,
    require_permission,
)
from app.auth.permissions import (
    PERM_HR_OFFERS_CREATE,
    PERM_HR_OFFERS_DELETE,
    PERM_HR_OFFERS_VIEW,
)
from app.core.database import get_db
from app.models.auth import User
from app.models.hr_ats import OfferLetterTemplate
from app.schemas.hr_ats import (
    MergeFieldInfo,
    OfferLetterTemplateCreate,
    OfferLetterTemplateRead,
    OfferLetterTemplateUpdate,
)
from app.services import offer_letters
from app.services.audit_log import record_audit


router = APIRouter(
    prefix="/hr/offer-templates",
    tags=["HR ATS - Offer letter templates"],
    dependencies=[Depends(require_hr_admin)],
)


def _audit(
    db: Session, actor: User, request: Request, *, action: str, target_id: str
) -> None:
    ctx = get_request_context(request)
    record_audit(
        db,
        action=action,
        actor_id=actor.id,
        actor_email=actor.email,
        scope="hr",
        target_type="offer_letter_template",
        target_id=target_id,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        commit=False,
    )


def _clear_other_defaults(db: Session, *, keep_id: Optional[int]) -> None:
    """At most one default template — drop the flag on every other row."""
    rows = db.execute(
        select(OfferLetterTemplate).where(OfferLetterTemplate.is_default.is_(True))
    ).scalars().all()
    for row in rows:
        if row.id != keep_id:
            row.is_default = False


@router.get("", response_model=List[OfferLetterTemplateRead])
def list_templates(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_HR_OFFERS_VIEW)),
) -> List[OfferLetterTemplate]:
    return list(
        db.execute(
            select(OfferLetterTemplate).order_by(
                OfferLetterTemplate.is_default.desc(),
                OfferLetterTemplate.name,
            )
        )
        .scalars()
        .all()
    )


@router.get("/tokens", response_model=List[MergeFieldInfo])
def list_merge_fields(
    _: User = Depends(require_permission(PERM_HR_OFFERS_VIEW)),
) -> List[MergeFieldInfo]:
    return [
        MergeFieldInfo(token=token, label=label)
        for token, label in offer_letters.available_merge_fields()
    ]


@router.get("/{template_id}", response_model=OfferLetterTemplateRead)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PERM_HR_OFFERS_VIEW)),
) -> OfferLetterTemplate:
    tpl = db.get(OfferLetterTemplate, template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.post("", response_model=OfferLetterTemplateRead, status_code=201)
def create_template(
    payload: OfferLetterTemplateCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_OFFERS_CREATE)),
) -> OfferLetterTemplate:
    tpl = OfferLetterTemplate(
        name=payload.name,
        description=payload.description,
        body=payload.body,
        is_active=payload.is_active,
        is_default=payload.is_default,
        created_by_id=actor.id,
    )
    db.add(tpl)
    db.flush()
    if tpl.is_default:
        _clear_other_defaults(db, keep_id=tpl.id)
    _audit(db, actor, request, action="hr.offer_template.create", target_id=str(tpl.id))
    db.commit()
    db.refresh(tpl)
    return tpl


@router.patch("/{template_id}", response_model=OfferLetterTemplateRead)
def update_template(
    template_id: int,
    payload: OfferLetterTemplateUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_OFFERS_CREATE)),
) -> OfferLetterTemplate:
    tpl = db.get(OfferLetterTemplate, template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(tpl, field, value)
    db.flush()
    if tpl.is_default:
        _clear_other_defaults(db, keep_id=tpl.id)
    _audit(db, actor, request, action="hr.offer_template.update", target_id=str(tpl.id))
    db.commit()
    db.refresh(tpl)
    return tpl


@router.delete("/{template_id}", status_code=204, response_class=Response)
def delete_template(
    template_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_OFFERS_DELETE)),
) -> Response:
    tpl = db.get(OfferLetterTemplate, template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(tpl)
    _audit(db, actor, request, action="hr.offer_template.delete", target_id=str(template_id))
    db.commit()
    return Response(status_code=204)

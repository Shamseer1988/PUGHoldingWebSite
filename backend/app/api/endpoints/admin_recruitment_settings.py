"""Admin recruitment-workflow settings (Super Admin only).

Exposes the global "require job approval" toggle. Per-role bypass is handled
by the ``hr:jobs:post_direct`` permission via the role matrix, not here.

Routes:

* ``GET /api/v1/admin/recruitment-settings`` — current config.
* ``PUT /api/v1/admin/recruitment-settings`` — update the toggle.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context, require_superuser
from app.core.database import get_db
from app.models.auth import SCOPE_SYSTEM, User
from app.models.email_settings import EmailSetting
from app.schemas.recruitment_settings import (
    RecruitmentSettingsRead,
    RecruitmentSettingsUpdate,
)
from app.services.audit_log import record_audit
from app.services.email import EmailService


router = APIRouter(
    prefix="/admin/recruitment-settings",
    tags=["Admin - Recruitment Settings"],
    dependencies=[Depends(require_superuser)],
)


def _to_read(setting: EmailSetting) -> RecruitmentSettingsRead:
    return RecruitmentSettingsRead(
        job_approval_required=setting.job_approval_required,
    )


@router.get("", response_model=RecruitmentSettingsRead)
def get_recruitment_settings(
    db: Session = Depends(get_db),
) -> RecruitmentSettingsRead:
    setting = EmailService.get_or_create_settings(db)
    return _to_read(setting)


@router.put("", response_model=RecruitmentSettingsRead)
def update_recruitment_settings(
    payload: RecruitmentSettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_superuser),
) -> RecruitmentSettingsRead:
    setting = EmailService.get_or_create_settings(db)
    updates = payload.model_dump(exclude_unset=True)

    changed: list[str] = []
    for field, value in updates.items():
        if getattr(setting, field) != value:
            setattr(setting, field, value)
            changed.append(field)

    if changed:
        ctx = get_request_context(request)
        record_audit(
            db,
            action="admin.recruitment_settings.update",
            actor_id=user.id,
            actor_email=user.email,
            scope=SCOPE_SYSTEM,
            target_type="recruitment_settings",
            target_id=str(setting.id),
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
            details={"fields": changed},
            commit=False,
        )
    db.commit()
    db.refresh(setting)
    return _to_read(setting)

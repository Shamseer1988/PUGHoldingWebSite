"""Admin endpoints for the system-scope AI configuration (Phase 13).

These endpoints back the AI Settings page in the admin panel. Only a
system-scope user (or superuser) can read/update the configuration so
that misconfiguring the model doesn't bleed across HR / website users.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.ai.candidate_review import resolve_config
from app.auth.dependencies import get_request_context, require_scope
from app.core.config import get_settings
from app.core.database import get_db
from app.models.auth import SCOPE_SYSTEM, User
from app.models.hr_ats import AI_MODES, AISetting
from app.schemas.hr_ats import AISettingsRead, AISettingsUpdate
from app.services.audit_log import record_audit


router = APIRouter(
    prefix="/admin/ai",
    tags=["Admin - AI Settings"],
    dependencies=[Depends(require_scope(SCOPE_SYSTEM))],
)


def _get_or_create_settings(db: Session) -> AISetting:
    setting = db.get(AISetting, 1)
    if setting is None:
        setting = AISetting(id=1)
        db.add(setting)
        db.flush()
    return setting


def _to_read(setting: AISetting) -> AISettingsRead:
    env = get_settings()
    resolved = resolve_config(setting)
    return AISettingsRead(
        id=setting.id,
        mode=setting.mode,
        azure_endpoint=setting.azure_endpoint,
        azure_deployment=setting.azure_deployment,
        azure_api_version=setting.azure_api_version,
        model_name=setting.model_name,
        temperature=setting.temperature,
        max_output_tokens=setting.max_output_tokens,
        request_timeout_seconds=setting.request_timeout_seconds,
        extra_system_prompt=setting.extra_system_prompt,
        updated_by_id=setting.updated_by_id,
        updated_at=setting.updated_at,
        has_azure_api_key=bool(env.azure_openai_api_key),
        effective_mode=resolved.mode,
    )


@router.get("/settings", response_model=AISettingsRead)
def get_ai_settings(db: Session = Depends(get_db)) -> AISettingsRead:
    return _to_read(_get_or_create_settings(db))


@router.patch("/settings", response_model=AISettingsRead)
def update_ai_settings(
    payload: AISettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_scope(SCOPE_SYSTEM)),
) -> AISettingsRead:
    setting = _get_or_create_settings(db)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return _to_read(setting)

    changed: list[str] = []
    for field, value in updates.items():
        if isinstance(value, str):
            value = value.strip() or None
        if getattr(setting, field) != value:
            setattr(setting, field, value)
            changed.append(field)

    if "mode" in updates and updates["mode"] not in AI_MODES:
        raise HTTPException(status_code=422, detail=f"Unknown AI mode: {updates['mode']!r}")

    if changed:
        setting.updated_by_id = user.id
        ctx = get_request_context(request)
        record_audit(
            db,
            action="admin.ai_settings.update",
            actor_id=user.id,
            actor_email=user.email,
            scope=SCOPE_SYSTEM,
            target_type="ai_settings",
            target_id=str(setting.id),
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
            details={"fields": changed, "mode": setting.mode},
            commit=False,
        )
    db.commit()
    db.refresh(setting)
    return _to_read(setting)

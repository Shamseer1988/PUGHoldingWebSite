"""Admin Email Configuration endpoints.

System-scope only. Mirrors the AI Settings pattern: a singleton row
holds non-secret config, the password is encrypted at rest and never
returned to the client, and updates are recorded in the audit log.

Routes:

* ``GET  /api/v1/admin/email-settings`` — current config (no password).
* ``PUT  /api/v1/admin/email-settings`` — update; blank password keeps
  the existing one.
* ``POST /api/v1/admin/email-settings/test`` — send a real test email
  using the saved config and return a structured result.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context, require_scope
from app.core.database import get_db
from app.models.auth import SCOPE_SYSTEM, User
from app.models.email_settings import EmailSetting
from app.schemas.email_settings import (
    EmailSettingsRead,
    EmailSettingsUpdate,
    EmailTestRequest,
    EmailTestResult,
    ImapTestRequest,
    ImapTestResult,
)
from app.services.audit_log import record_audit
from app.services.contact_inbound import (
    resolve_imap_config,
    test_imap_connection,
)
from app.services.email import EmailService, store_password


router = APIRouter(
    prefix="/admin/email-settings",
    tags=["Admin - Email Configuration"],
    dependencies=[Depends(require_scope(SCOPE_SYSTEM))],
)


def _to_read(db: Session, setting: EmailSetting) -> EmailSettingsRead:
    config = EmailService.get_config(db)
    imap_cfg = resolve_imap_config(db)
    imap_env_fallback = (
        not setting.imap_host
        and not setting.imap_username
        and not setting.imap_password_encrypted
        and bool(imap_cfg.host or imap_cfg.username or imap_cfg.password)
    )
    return EmailSettingsRead(
        id=setting.id,
        email_enabled=setting.email_enabled,
        smtp_host=setting.smtp_host,
        smtp_port=setting.smtp_port,
        smtp_username=setting.smtp_username,
        has_smtp_password=config.has_password,
        smtp_use_tls=setting.smtp_use_tls,
        smtp_use_ssl=setting.smtp_use_ssl,
        email_from=setting.email_from,
        email_from_name=setting.email_from_name,
        email_reply_to=setting.email_reply_to,
        test_email_to=setting.test_email_to,
        notification_email=setting.notification_email,
        hr_notification_emails=setting.hr_notification_emails or [],
        candidate_email_enabled=setting.candidate_email_enabled,
        interview_email_enabled=setting.interview_email_enabled,
        job_approval_email_enabled=setting.job_approval_email_enabled,
        brand_logo_url=setting.brand_logo_url,
        email_footer_text=setting.email_footer_text,
        last_test_status=setting.last_test_status,
        last_test_message=setting.last_test_message,
        last_test_at=setting.last_test_at,
        updated_by_id=setting.updated_by_id,
        updated_at=setting.updated_at,
        env_fallback_active=config.env_fallback_active,
        imap_enabled=setting.imap_enabled,
        imap_host=setting.imap_host,
        imap_port=setting.imap_port,
        imap_username=setting.imap_username,
        has_imap_password=bool(imap_cfg.password),
        imap_use_ssl=setting.imap_use_ssl,
        imap_folder=setting.imap_folder,
        imap_processed_folder=setting.imap_processed_folder,
        imap_error_folder=setting.imap_error_folder,
        imap_poll_interval_minutes=setting.imap_poll_interval_minutes,
        imap_create_new_tickets=setting.imap_create_new_tickets,
        last_imap_test_status=setting.last_imap_test_status,
        last_imap_test_message=setting.last_imap_test_message,
        last_imap_test_at=setting.last_imap_test_at,
        imap_env_fallback_active=imap_env_fallback,
        imap_auth_method=setting.imap_auth_method or "password",
        imap_oauth_tenant_id=setting.imap_oauth_tenant_id,
        imap_oauth_client_id=setting.imap_oauth_client_id,
        has_imap_oauth_client_secret=bool(
            setting.imap_oauth_client_secret_encrypted
        ),
    )


@router.get("", response_model=EmailSettingsRead)
def get_email_settings(db: Session = Depends(get_db)) -> EmailSettingsRead:
    setting = EmailService.get_or_create_settings(db)
    return _to_read(db, setting)


@router.put("", response_model=EmailSettingsRead)
def update_email_settings(
    payload: EmailSettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_scope(SCOPE_SYSTEM)),
) -> EmailSettingsRead:
    setting = EmailService.get_or_create_settings(db)
    updates = payload.model_dump(exclude_unset=True)
    new_password = updates.pop("smtp_password", None)
    new_imap_password = updates.pop("imap_password", None)
    new_oauth_secret = updates.pop("imap_oauth_client_secret", None)

    changed: list[str] = []
    for field, value in updates.items():
        if getattr(setting, field) != value:
            setattr(setting, field, value)
            changed.append(field)

    if store_password(setting, new_password):
        changed.append("smtp_password")

    # IMAP password — same Fernet pattern as SMTP. Blank/None keeps
    # the existing token so the admin can save other fields without
    # re-typing the password.
    if new_imap_password is not None and new_imap_password.strip():
        from app.core.crypto import encrypt_secret

        setting.imap_password_encrypted = encrypt_secret(new_imap_password)
        changed.append("imap_password")

    # IMAP OAuth2 client secret — same Fernet pattern again. Rotating
    # the secret invalidates the cached token; the next poll fetches
    # a fresh one from Microsoft.
    if new_oauth_secret is not None and new_oauth_secret.strip():
        from app.core.crypto import encrypt_secret
        from app.services.m365_oauth import clear_cache

        setting.imap_oauth_client_secret_encrypted = encrypt_secret(
            new_oauth_secret
        )
        clear_cache()
        changed.append("imap_oauth_client_secret")

    if changed:
        setting.updated_by_id = user.id
        ctx = get_request_context(request)
        record_audit(
            db,
            action="admin.email_settings.update",
            actor_id=user.id,
            actor_email=user.email,
            scope=SCOPE_SYSTEM,
            target_type="email_settings",
            target_id=str(setting.id),
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
            details={"fields": changed},
            commit=False,
        )
    db.commit()
    db.refresh(setting)
    return _to_read(db, setting)


@router.post("/test", response_model=EmailTestResult)
def send_test_email(
    payload: EmailTestRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_scope(SCOPE_SYSTEM)),
) -> EmailTestResult:
    result = EmailService.send_test_email(db, to_email=payload.to_email)

    ctx = get_request_context(request)
    record_audit(
        db,
        action="admin.email_settings.test",
        actor_id=user.id,
        actor_email=user.email,
        scope=SCOPE_SYSTEM,
        target_type="email_settings",
        target_id="1",
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "to_email": payload.to_email,
            "success": result.success,
            # Trim any provider response to keep audit rows compact.
            "message": result.message[:200],
        },
        commit=False,
    )
    db.commit()
    return EmailTestResult(
        success=result.success,
        message=result.message,
        sent_at=result.sent_at or (datetime.now(timezone.utc) if result.success else None),
    )


@router.post("/imap-test", response_model=ImapTestResult)
def test_imap_settings(
    payload: ImapTestRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_scope(SCOPE_SYSTEM)),
) -> ImapTestResult:
    """Open a real IMAP connection using the saved (or just-typed)
    credentials and return a structured diagnostic.

    Updates ``last_imap_test_status`` / ``message`` / ``at`` on the
    row so the admin page can show a "tested OK / failed Xm ago"
    badge without re-running the test on every load.
    """
    outcome = test_imap_connection(
        db,
        override_password=payload.imap_password,
        override_oauth_tenant_id=payload.imap_oauth_tenant_id,
        override_oauth_client_id=payload.imap_oauth_client_id,
        override_oauth_client_secret=payload.imap_oauth_client_secret,
        override_auth_method=payload.imap_auth_method,
    )

    setting = EmailService.get_or_create_settings(db)
    setting.last_imap_test_status = (
        "success" if outcome.success else "failed"
    )
    setting.last_imap_test_message = outcome.message[:1000]
    setting.last_imap_test_at = outcome.tested_at

    ctx = get_request_context(request)
    record_audit(
        db,
        action="admin.email_settings.imap_test",
        actor_id=user.id,
        actor_email=user.email,
        scope=SCOPE_SYSTEM,
        target_type="email_settings",
        target_id="1",
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "success": outcome.success,
            "message": outcome.message[:200],
            "folder_count": len(outcome.folders_sampled),
        },
        commit=False,
    )
    db.commit()
    return ImapTestResult(
        success=outcome.success,
        message=outcome.message,
        folders_sampled=outcome.folders_sampled,
        server_greeting=outcome.server_greeting,
        selected_message_count=outcome.selected_message_count,
        tested_at=outcome.tested_at,
    )

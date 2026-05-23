"""Helpers for writing entries to the audit_logs table.

Phase 2 only writes login/logout/failed-login entries; later phases reuse
the same helpers for CRUD audits across the website admin and HR ATS
surfaces.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.auth import AuditLog


# Common action keys (kept lowercase + dotted so they're easy to filter on).
ACTION_LOGIN_SUCCESS = "auth.login.success"
ACTION_LOGIN_FAILED = "auth.login.failed"
ACTION_LOGIN_WRONG_SCOPE = "auth.login.wrong_scope"
ACTION_LOGOUT = "auth.logout"


def record_audit(
    db: Session,
    *,
    action: str,
    actor_id: Optional[int] = None,
    actor_email: Optional[str] = None,
    scope: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    commit: bool = True,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        actor_id=actor_id,
        actor_email=actor_email,
        scope=scope,
        target_type=target_type,
        target_id=target_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    return entry

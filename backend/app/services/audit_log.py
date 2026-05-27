"""Helpers for writing entries to the audit_logs table.

Phase 2 only writes login/logout/failed-login entries; later phases reuse
the same helpers for CRUD audits across the website admin and HR ATS
surfaces.

The ``details`` dict is serialized to JSON and stored verbatim, so it's
a tempting place for a developer to accidentally log a password hash or
API token. ``_sanitize_details`` walks the dict and redacts anything
that looks sensitive *before* the row hits the database — defense in
depth against the audit table itself becoming a credential leak vector.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.auth import AuditLog


# Common action keys (kept lowercase + dotted so they're easy to filter on).
ACTION_LOGIN_SUCCESS = "auth.login.success"
ACTION_LOGIN_FAILED = "auth.login.failed"
ACTION_LOGIN_WRONG_SCOPE = "auth.login.wrong_scope"
ACTION_LOGOUT = "auth.logout"

# Substrings that, if they appear in a details-dict key, indicate a
# field whose value must NOT be persisted in the audit log. Matched
# case-insensitively. ``file_hash`` is deliberately allowed (it's a
# content-addressed identifier, not a secret) — only the literal word
# "password" or "secret" etc. triggers redaction.
_SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|secret|api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|authorization|bearer|cookie|"
    r"private[_-]?key|client[_-]?secret)",
    re.IGNORECASE,
)
_REDACTED = "<redacted>"


def _sanitize_details(value: Any) -> Any:
    """Recursively walk a details payload, replacing any value whose key
    matches the sensitive-name pattern with ``"<redacted>"``.

    Lists, tuples and nested dicts are descended into. Non-container
    leaf values are returned unchanged. The caller's input is never
    mutated — we always return a fresh structure.
    """
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and _SENSITIVE_KEY_RE.search(k):
                out[k] = _REDACTED
            else:
                out[k] = _sanitize_details(v)
        return out
    if isinstance(value, list):
        return [_sanitize_details(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_details(item) for item in value)
    return value


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
    sanitized = _sanitize_details(details) if details is not None else None
    entry = AuditLog(
        action=action,
        actor_id=actor_id,
        actor_email=actor_email,
        scope=scope,
        target_type=target_type,
        target_id=target_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=sanitized,
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    return entry


__all__ = [
    "ACTION_LOGIN_SUCCESS",
    "ACTION_LOGIN_FAILED",
    "ACTION_LOGIN_WRONG_SCOPE",
    "ACTION_LOGOUT",
    "record_audit",
    "_sanitize_details",  # exported for tests
]

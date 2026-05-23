"""Authentication services.

Encapsulates the login flow (user lookup, password verification, scope
check, audit logging) so the API endpoints stay thin.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
)
from app.core.config import get_settings
from app.models.auth import User
from app.schemas.auth import LoginResponse, UserRead
from app.services.audit_log import (
    ACTION_LOGIN_FAILED,
    ACTION_LOGIN_SUCCESS,
    ACTION_LOGIN_WRONG_SCOPE,
    record_audit,
)


class AuthError(Exception):
    """Raised when authentication cannot proceed.

    Carries a stable ``code`` so endpoints can map it to the right HTTP
    status, plus a human-readable ``message`` for the API response.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class RequestMeta:
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    normalized = email.strip().lower()
    stmt = select(User).where(User.email == normalized)
    return db.execute(stmt).scalar_one_or_none()


def authenticate(
    db: Session,
    *,
    email: str,
    password: str,
    required_scope: str,
    meta: RequestMeta,
) -> LoginResponse:
    """Validate credentials and issue tokens for the given scope.

    Audit log entries are written for every outcome (failed credentials,
    wrong scope, success).
    """
    user = get_user_by_email(db, email)

    if user is None or not verify_password(password, user.password_hash):
        record_audit(
            db,
            action=ACTION_LOGIN_FAILED,
            actor_id=user.id if user else None,
            actor_email=email.strip().lower(),
            scope=required_scope,
            ip_address=meta.ip_address,
            user_agent=meta.user_agent,
            details={"reason": "invalid_credentials"},
        )
        raise AuthError("invalid_credentials", "Invalid email or password")

    if not user.is_active:
        record_audit(
            db,
            action=ACTION_LOGIN_FAILED,
            actor_id=user.id,
            actor_email=user.email,
            scope=required_scope,
            ip_address=meta.ip_address,
            user_agent=meta.user_agent,
            details={"reason": "inactive"},
        )
        raise AuthError("inactive", "Account is disabled")

    if not user.has_scope(required_scope):
        record_audit(
            db,
            action=ACTION_LOGIN_WRONG_SCOPE,
            actor_id=user.id,
            actor_email=user.email,
            scope=required_scope,
            ip_address=meta.ip_address,
            user_agent=meta.user_agent,
            details={
                "reason": "wrong_scope",
                "user_scopes": sorted(user.scopes),
            },
        )
        raise AuthError(
            "wrong_scope",
            "This account does not have access to this portal",
        )

    settings = get_settings()
    user.last_login_at = datetime.now(timezone.utc)

    access_token = create_access_token(
        subject=user.id,
        scopes=sorted(user.scopes),
    )
    refresh_token = create_refresh_token(subject=user.id)

    record_audit(
        db,
        action=ACTION_LOGIN_SUCCESS,
        actor_id=user.id,
        actor_email=user.email,
        scope=required_scope,
        ip_address=meta.ip_address,
        user_agent=meta.user_agent,
        commit=False,  # commit at the end with the last_login_at update
    )
    db.commit()
    db.refresh(user)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=_user_to_read(user),
    )


def _user_to_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        last_login_at=user.last_login_at,
        roles=[
            {
                "id": role.id,
                "name": role.name,
                "scope": role.scope,
                "description": role.description,
                "permissions": [
                    {
                        "id": perm.id,
                        "key": perm.key,
                        "scope": perm.scope,
                        "description": perm.description,
                    }
                    for perm in role.permissions
                ],
            }
            for role in user.roles
        ],
        scopes=sorted(user.scopes),
        permissions=sorted(user.permission_keys),
    )


def user_to_read(user: User) -> UserRead:
    """Public wrapper around the internal serializer."""
    return _user_to_read(user)

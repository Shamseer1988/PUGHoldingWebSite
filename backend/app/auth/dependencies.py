"""FastAPI auth dependencies: current user resolution + scope/permission guards."""
from __future__ import annotations

from typing import Callable, Iterable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import (
    TOKEN_TYPE_ACCESS,
    JWTError,
    decode_token,
)
from app.core.database import get_db
from app.models.auth import SCOPE_HR, SCOPE_SYSTEM, SCOPE_WEBSITE, User


bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str = "Insufficient permissions") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the ``Authorization`` bearer token."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized()

    try:
        payload = decode_token(credentials.credentials)
    except JWTError as exc:
        raise _unauthorized(f"Invalid or expired token: {exc}") from exc

    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise _unauthorized("Wrong token type")

    sub = payload.get("sub")
    if sub is None:
        raise _unauthorized("Token missing subject")

    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise _unauthorized("Token subject is not a user id") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive")

    return user


def require_scope(scope: str) -> Callable[[User], User]:
    """Dependency factory: ensure the current user has access to ``scope``."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_scope(scope):
            raise _forbidden(f"This area requires '{scope}' access")
        return user

    return _checker


def require_any_scope(scopes: Iterable[str]) -> Callable[[User], User]:
    """Dependency factory: require at least one of the given scopes."""
    scopes_set = set(scopes)

    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.is_superuser or SCOPE_SYSTEM in user.scopes:
            return user
        if not (scopes_set & user.scopes):
            raise _forbidden(
                f"This area requires one of: {', '.join(sorted(scopes_set))}"
            )
        return user

    return _checker


def require_permission(permission_key: str) -> Callable[[User], User]:
    """Dependency factory: require a specific permission key."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_permission(permission_key):
            raise _forbidden(f"Missing permission '{permission_key}'")
        return user

    return _checker


def require_any_permission(
    *permission_keys: str,
) -> Callable[[User], User]:
    """Dependency factory: require at least one of the listed permission keys.

    Useful when an endpoint serves multiple roles with overlapping needs
    — e.g. interview listing is open to anyone with view_all OR view_mine,
    and the endpoint then filters rows based on which they have.
    """
    keys = tuple(permission_keys)
    if not keys:
        raise ValueError("require_any_permission needs at least one key")

    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.is_superuser:
            return user
        for key in keys:
            if user.has_permission(key):
                return user
        raise _forbidden(
            f"Requires one of: {', '.join(sorted(keys))}"
        )

    return _checker


def require_all_permissions(
    *permission_keys: str,
) -> Callable[[User], User]:
    """Dependency factory: require every listed permission key."""
    keys = tuple(permission_keys)
    if not keys:
        raise ValueError("require_all_permissions needs at least one key")

    def _checker(user: User = Depends(get_current_user)) -> User:
        if user.is_superuser:
            return user
        missing = [k for k in keys if not user.has_permission(k)]
        if missing:
            raise _forbidden(
                f"Missing permissions: {', '.join(missing)}"
            )
        return user

    return _checker


# Convenience pre-built dependencies for the two main surfaces.
require_website_admin = require_scope(SCOPE_WEBSITE)
require_hr_admin = require_scope(SCOPE_HR)


def require_superuser(user: User = Depends(get_current_user)) -> User:
    """Dependency: only ``is_superuser`` accounts pass.

    Stricter than ``require_scope(SCOPE_SYSTEM)`` because a system-scope
    role can be assigned to non-founder admins (e.g. Email-config admin)
    while ``is_superuser`` is the small set of operator-tier accounts.
    Used for irrecoverable actions such as full-database backup +
    restore where a misclick could wipe production data.
    """
    if not user.is_superuser:
        raise _forbidden("Superuser privileges required for this action")
    return user


def get_request_context(request: Request) -> dict[str, str | None]:
    """Extract IP + user-agent for audit logging."""
    client_host = request.client.host if request.client else None
    forwarded_for = request.headers.get("x-forwarded-for")
    return {
        "ip_address": (forwarded_for.split(",")[0].strip() if forwarded_for else client_host),
        "user_agent": request.headers.get("user-agent"),
    }

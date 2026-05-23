"""Password hashing and JWT helpers shared by the admin and HR auth flows."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings


# bcrypt rejects passwords longer than 72 bytes. We sidestep that limit by
# pre-hashing the password with SHA-256 (a stable, deterministic transform)
# before handing it to bcrypt. This is the same pattern used by Django and
# other mainstream stacks.
def _prepare(password: str) -> bytes:
    return hashlib.sha256(password.encode("utf-8")).digest()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

# Token "type" claim values – kept distinct so a refresh token can never be
# accepted as an access token.
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    *,
    subject: str | int,
    scopes: list[str],
    extra_claims: Optional[dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Issue a short-lived access token."""
    settings = get_settings()
    expire_delta = expires_delta or timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return _encode(
        {
            "sub": str(subject),
            "scopes": scopes,
            "type": TOKEN_TYPE_ACCESS,
            **(extra_claims or {}),
        },
        expire_delta,
    )


def create_refresh_token(
    *,
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Issue a long-lived refresh token (subject only, no scopes)."""
    settings = get_settings()
    expire_delta = expires_delta or timedelta(
        days=settings.refresh_token_expire_days
    )
    return _encode(
        {"sub": str(subject), "type": TOKEN_TYPE_REFRESH},
        expire_delta,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, raising ``JWTError`` on failure."""
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def _encode(payload: dict[str, Any], expires_delta: timedelta) -> str:
    settings = get_settings()
    now = _now_utc()
    to_encode = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


__all__ = [
    "TOKEN_TYPE_ACCESS",
    "TOKEN_TYPE_REFRESH",
    "JWTError",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "verify_password",
]

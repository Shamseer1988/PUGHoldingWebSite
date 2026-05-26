"""Symmetric encryption helper for at-rest secrets in the database.

Used by :mod:`app.services.email` to store the SMTP password on
``email_settings.smtp_password_encrypted`` without ever round-tripping
it to the admin UI. The key is deterministically derived from
``Settings.secret_key`` so the same deployment can decrypt rows it
wrote on a previous boot.

Important rules:

  * Never log decrypted values.
  * Never include decrypted values in API responses or audit log
    ``details``.
  * If the secret_key ever changes, previously-encrypted columns will
    fail to decrypt — callers must treat the missing value the same as
    "no password configured" and fall back to env.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _derive_key(secret_key: str) -> bytes:
    """Turn the application secret into a Fernet-compatible 32-byte key."""
    digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(_derive_key(get_settings().secret_key))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a short secret (e.g. SMTP password) for DB storage."""
    if not plaintext:
        raise ValueError("encrypt_secret requires a non-empty value")
    token = _fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt_secret(token: Optional[str]) -> Optional[str]:
    """Decrypt a stored secret. Returns None for empty / unreadable tokens."""
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        # secret_key rotated or value corrupted — treat as "no password".
        return None

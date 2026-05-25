"""Unit tests for password hashing and JWT helpers."""
from __future__ import annotations

import pytest
from jose import JWTError

from app.auth.security import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_roundtrip():
    h = hash_password("hello123")
    assert verify_password("hello123", h) is True
    assert verify_password("wrong", h) is False


def test_access_token_contains_subject_and_scopes():
    token = create_access_token(subject=42, scopes=["website", "hr"])
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == TOKEN_TYPE_ACCESS
    assert payload["scopes"] == ["website", "hr"]
    assert payload["exp"] > payload["iat"]


def test_refresh_token_has_correct_type():
    token = create_refresh_token(subject=7)
    payload = decode_token(token)
    assert payload["sub"] == "7"
    assert payload["type"] == TOKEN_TYPE_REFRESH


def test_invalid_token_raises():
    with pytest.raises(JWTError):
        decode_token("not.a.real.jwt")

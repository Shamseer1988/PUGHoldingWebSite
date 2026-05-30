"""Pydantic schemas for the URL Shortener feature."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Slug rules:
#  * Lowercase letters, digits, hyphen, underscore.
#  * 3-32 chars (3 = "abc" — enough room for one or two character
#    collisions; 32 = comfortably under the 64-char column.)
#  * Reserved words below are blocked at the API layer so an admin
#    can't shadow a real route like ``/go/admin`` or ``/go/api``.
SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{1,30}[a-z0-9])?$")

RESERVED_SLUGS = frozenset(
    {
        "admin",
        "api",
        "go",
        "health",
        "login",
        "logout",
        "robots",
        "settings",
        "sitemap",
        "static",
        "uploads",
        "www",
    }
)


def _validate_slug(value: str) -> str:
    """Normalise + validate a slug. Raises ValueError on invalid input."""
    if value is None:
        raise ValueError("slug is required")
    normalised = value.strip().lower()
    if not SLUG_PATTERN.match(normalised):
        raise ValueError(
            "Slug must be 3-32 characters, lowercase letters, digits, "
            "hyphens or underscores. Must start and end with a letter or digit."
        )
    if normalised in RESERVED_SLUGS:
        raise ValueError(f"'{normalised}' is reserved and cannot be used as a slug.")
    return normalised


def _validate_target_url(value: str) -> str:
    """Reject obvious nonsense + force http/https scheme."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("target_url is required")
    if len(cleaned) > 2048:
        raise ValueError("target_url is too long (max 2048 characters)")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("target_url must start with http:// or https://")
    if not parsed.netloc:
        raise ValueError("target_url must include a hostname")
    return cleaned


class ShortUrlCreate(BaseModel):
    """Admin → POST /admin/marketing/short-urls payload.

    ``slug`` is optional; the endpoint auto-generates a 7-char random
    slug when it's omitted. ``title`` is purely organisational — it
    shows up in the admin list and isn't exposed publicly.
    """

    model_config = ConfigDict(extra="forbid")

    target_url: str = Field(..., max_length=2048)
    slug: Optional[str] = Field(default=None, max_length=64)
    title: Optional[str] = Field(default=None, max_length=200)
    is_active: bool = True
    expires_at: Optional[datetime] = None

    @field_validator("target_url")
    @classmethod
    def _check_target(cls, v: str) -> str:
        return _validate_target_url(v)

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        return _validate_slug(v)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


class ShortUrlUpdate(BaseModel):
    """Admin → PATCH /admin/marketing/short-urls/{id} payload.

    Slug is deliberately NOT editable — changing it would invalidate
    every printed/posted asset that uses the old slug. To re-point a
    link we update ``target_url``; to retire one we set ``is_active =
    false`` (history + click count preserved).
    """

    model_config = ConfigDict(extra="forbid")

    target_url: Optional[str] = Field(default=None, max_length=2048)
    title: Optional[str] = Field(default=None, max_length=200)
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None

    @field_validator("target_url")
    @classmethod
    def _check_target(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _validate_target_url(v)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None


class ShortUrlRead(BaseModel):
    """One row in the admin list / detail view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    target_url: str
    title: Optional[str]
    is_active: bool
    expires_at: Optional[datetime]
    click_count: int
    last_click_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ShortUrlListResponse(BaseModel):
    """Paginated list payload."""

    model_config = ConfigDict(extra="forbid")

    items: list[ShortUrlRead]
    total: int


__all__ = [
    "RESERVED_SLUGS",
    "SLUG_PATTERN",
    "ShortUrlCreate",
    "ShortUrlListResponse",
    "ShortUrlRead",
    "ShortUrlUpdate",
]

"""Pydantic schemas for per-division QR codes (Marketing → QR Codes).

The load-bearing detail in this module is what ``QrCodeUpdate`` does
*not* contain: there is no ``slug`` field. A QR slug is baked into
printed signage, so making it structurally impossible to PATCH is
worth more than any validation rule. Same reasoning as
``ShortUrlUpdate``, but stricter — a short link can be reprinted in an
email, a wall-mounted code cannot.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.marketing_qr import QR_TARGET_KINDS, QR_TARGET_OTHER


# Slug rules mirror the URL shortener's: lowercase, 3-64 chars, must
# start and end alphanumeric. Wider than the shortener's 32-char cap
# because QR slugs are readable branch names ("al-atiyah-shelf-talker")
# rather than random codes, and nobody hand-types them off signage.
SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{1,62}[a-z0-9])?$")

# Blocked so an admin can't mint a QR slug that shadows a real route
# under ``/q/`` or collides with the frontend's top-level paths.
RESERVED_SLUGS = frozenset(
    {
        "admin",
        "api",
        "go",
        "health",
        "login",
        "logout",
        "new",
        "offers",
        "q",
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
            "Slug must be 3-64 characters, lowercase letters, digits, "
            "hyphens or underscores, starting and ending with a letter "
            "or digit."
        )
    if normalised in RESERVED_SLUGS:
        raise ValueError(f"'{normalised}' is reserved and cannot be used as a slug.")
    return normalised


def _validate_url(value: str) -> str:
    """Reject obvious nonsense + force an http/https scheme.

    Anything else (``javascript:``, ``data:``) would turn a scan into
    a script execution on whatever browser the shopper is using, so
    the scheme allow-list is a security control, not tidiness.
    """
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("URL is required")
    if len(cleaned) > 2048:
        raise ValueError("URL is too long (max 2048 characters)")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must start with http:// or https://")
    if not parsed.netloc:
        raise ValueError("URL must include a hostname")
    return cleaned


def _optional_url(value: Optional[str]) -> Optional[str]:
    """``None`` / blank passes through; anything else is validated.

    Blank-to-``None`` matters for the admin UI: clearing a text input
    submits ``""``, and the operator means "remove this", not "store
    an empty string".
    """
    if value is None:
        return None
    if not value.strip():
        return None
    return _validate_url(value)


def _strip_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


# ---------------------------------------------------------------------------
# Divisions
# ---------------------------------------------------------------------------


class DivisionCreate(BaseModel):
    """Admin → POST /admin/marketing/divisions.

    ``slug`` is optional — omitted, it's derived from ``name``
    ("Paris Hyper Market Al Khor" → ``paris-hyper-market-al-khor``).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=200)
    slug: Optional[str] = Field(default=None, max_length=120)
    city: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = None
    logo_url: Optional[str] = Field(default=None, max_length=500)
    fallback_url: Optional[str] = Field(default=None, max_length=2048)
    is_active: bool = True
    sort_order: int = 0

    # Auto-create the division's first QR code. Defaults on so the
    # common "one code per branch" flow is a single form submit.
    create_primary_qr: bool = True

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("Name must be at least 2 characters")
        return stripped

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        return _validate_slug(v)

    @field_validator("city", "description")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        return _strip_optional(v)

    @field_validator("fallback_url")
    @classmethod
    def _check_fallback(cls, v: Optional[str]) -> Optional[str]:
        return _optional_url(v)


class DivisionUpdate(BaseModel):
    """Admin → PATCH /admin/marketing/divisions/{id}.

    The division slug *is* editable — unlike a QR slug it appears
    nowhere in printed artwork; it only seeds new QR slugs at creation
    time. Renaming a division therefore never disturbs codes already
    in the field.
    """

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    slug: Optional[str] = Field(default=None, max_length=120)
    city: Optional[str] = Field(default=None, max_length=120)
    description: Optional[str] = None
    logo_url: Optional[str] = Field(default=None, max_length=500)
    fallback_url: Optional[str] = Field(default=None, max_length=2048)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("Name must be at least 2 characters")
        return stripped

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        return _validate_slug(v)

    @field_validator("city", "description")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        return _strip_optional(v)

    @field_validator("fallback_url")
    @classmethod
    def _check_fallback(cls, v: Optional[str]) -> Optional[str]:
        return _optional_url(v)


# ---------------------------------------------------------------------------
# QR codes
# ---------------------------------------------------------------------------


class QrCodeCreate(BaseModel):
    """Admin → POST /admin/marketing/divisions/{id}/qr-codes.

    ``target_url`` is optional so a code can be generated and sent to
    the printer before marketing has settled on a destination.
    """

    model_config = ConfigDict(extra="forbid")

    label: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = Field(default=None, max_length=64)
    target_url: Optional[str] = Field(default=None, max_length=2048)
    target_kind: str = QR_TARGET_OTHER
    fallback_url: Optional[str] = Field(default=None, max_length=2048)
    is_active: bool = True
    sort_order: int = 0

    @field_validator("label")
    @classmethod
    def _check_label(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Label is required")
        return stripped

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        return _validate_slug(v)

    @field_validator("target_url", "fallback_url")
    @classmethod
    def _check_urls(cls, v: Optional[str]) -> Optional[str]:
        return _optional_url(v)

    @field_validator("target_kind")
    @classmethod
    def _check_kind(cls, v: str) -> str:
        cleaned = (v or "").strip().lower()
        if cleaned not in QR_TARGET_KINDS:
            raise ValueError(
                f"target_kind must be one of: {', '.join(QR_TARGET_KINDS)}"
            )
        return cleaned


class QrCodeUpdate(BaseModel):
    """Admin → PATCH /admin/marketing/qr-codes/{id}.

    Deliberately has NO ``slug`` field. The QR image encodes
    ``/q/{slug}``; once that artwork is printed on signage the slug is
    a physical constant. Re-pointing a code means changing
    ``target_url``; retiring one means ``is_active = false`` (which
    routes scans to the fallback chain rather than 404ing, so the
    printed code degrades gracefully instead of dead-ending).

    ``extra="forbid"`` means a stray ``{"slug": "..."}`` in a request
    body is a 422, not a silent no-op — the failure is loud.
    """

    model_config = ConfigDict(extra="forbid")

    label: Optional[str] = Field(default=None, min_length=1, max_length=200)
    target_url: Optional[str] = Field(default=None, max_length=2048)
    target_kind: Optional[str] = None
    fallback_url: Optional[str] = Field(default=None, max_length=2048)
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

    @field_validator("label")
    @classmethod
    def _check_label(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("Label cannot be blank")
        return stripped

    @field_validator("target_url", "fallback_url")
    @classmethod
    def _check_urls(cls, v: Optional[str]) -> Optional[str]:
        return _optional_url(v)

    @field_validator("target_kind")
    @classmethod
    def _check_kind(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip().lower()
        if cleaned not in QR_TARGET_KINDS:
            raise ValueError(
                f"target_kind must be one of: {', '.join(QR_TARGET_KINDS)}"
            )
        return cleaned


# ---------------------------------------------------------------------------
# Read models
# ---------------------------------------------------------------------------


class QrCodeRead(BaseModel):
    """One QR code in the admin list / detail view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    division_id: int
    slug: str
    label: str
    target_url: Optional[str]
    target_kind: str
    fallback_url: Optional[str]
    is_active: bool
    sort_order: int
    scan_count: int
    last_scan_at: Optional[datetime]
    target_updated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class DivisionRead(BaseModel):
    """One division, with its QR codes nested."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    city: Optional[str]
    description: Optional[str]
    logo_url: Optional[str]
    fallback_url: Optional[str]
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime
    qr_codes: List[QrCodeRead] = []


class DivisionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[DivisionRead]
    total: int


class QrCodeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[QrCodeRead]
    total: int


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class QrScanDailyPoint(BaseModel):
    """One day in the scan trend."""

    model_config = ConfigDict(extra="forbid")

    day: str  # ISO date — "2026-08-04"
    scans: int


class QrDeviceBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device: str
    scans: int


class QrTargetHistoryEntry(BaseModel):
    """One target change, reconstructed from the audit log."""

    model_config = ConfigDict(extra="forbid")

    changed_at: datetime
    actor_email: Optional[str]
    from_url: Optional[str]
    to_url: Optional[str]


class QrCodeAnalytics(BaseModel):
    """Payload for the per-QR analytics panel."""

    model_config = ConfigDict(extra="forbid")

    qr_code_id: int
    total_scans: int
    scans_last_30_days: int
    last_scan_at: Optional[datetime]
    daily: List[QrScanDailyPoint]
    devices: List[QrDeviceBreakdown]
    target_history: List[QrTargetHistoryEntry]


class QrScanLog(BaseModel):
    """Public → optional beacon body posted by the interstitial.

    Unused today (the redirect logs server-side), but kept so a future
    interstitial page can enrich a scan with a device bucket without
    a schema change.
    """

    model_config = ConfigDict(extra="forbid")

    session_hash: Optional[str] = Field(default=None, max_length=128)
    device: Optional[str] = Field(default=None, max_length=16)


__all__ = [
    "RESERVED_SLUGS",
    "SLUG_PATTERN",
    "DivisionCreate",
    "DivisionListResponse",
    "DivisionRead",
    "DivisionUpdate",
    "QrCodeAnalytics",
    "QrCodeCreate",
    "QrCodeListResponse",
    "QrCodeRead",
    "QrCodeUpdate",
    "QrDeviceBreakdown",
    "QrScanDailyPoint",
    "QrScanLog",
    "QrTargetHistoryEntry",
]

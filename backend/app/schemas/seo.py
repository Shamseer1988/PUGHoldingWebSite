"""Pydantic schemas for the SEO Configuration module (Phase 1).

Mirrors :mod:`app.models.seo`. Three groups:

  * Global settings (read + partial-update).
  * Verification records (create + update + read).
  * Tracking integrations (upsert by provider + read).

Plus a few read-only payloads used by the admin dashboard tab.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.seo import (
    PLACEMENTS,
    PLACEMENT_HEAD,
    TRACKING_PROVIDERS,
    VERIFICATION_PROVIDERS,
    VERIFICATION_STATUSES,
    VERIFICATION_STATUS_PENDING,
    VERIFICATION_TYPES,
)


# ---------------------------------------------------------------------------
# Provider-ID validation regexes
# ---------------------------------------------------------------------------
GTM_ID_RE = re.compile(r"^GTM-[A-Z0-9]{4,12}$", re.IGNORECASE)
GA4_ID_RE = re.compile(r"^G-[A-Z0-9]{6,12}$", re.IGNORECASE)
META_PIXEL_ID_RE = re.compile(r"^\d{8,20}$")
CLARITY_ID_RE = re.compile(r"^[a-z0-9]{6,15}$", re.IGNORECASE)
LINKEDIN_ID_RE = re.compile(r"^\d{4,12}$")
TIKTOK_ID_RE = re.compile(r"^[A-Z0-9]{15,30}$")
X_ID_RE = re.compile(r"^[a-z0-9]{4,15}$", re.IGNORECASE)

# HTML verification filenames: only the well-known shapes search
# engines actually request. Anything else falls through to a 404.
HTML_VERIFICATION_FILENAME_RE = re.compile(
    r"^("
    r"google[a-zA-Z0-9_-]{4,64}\.html|"
    r"BingSiteAuth\.xml|"
    r"pinterest-[a-zA-Z0-9_-]{4,64}\.html|"
    r"yandex_[a-zA-Z0-9_-]{4,64}\.html|"
    r"[a-zA-Z0-9_-]{3,40}-(verification|site-verification)\.html"
    r")$"
)

CHANGEFREQS = {"always", "hourly", "daily", "weekly", "monthly", "yearly", "never"}


# ---------------------------------------------------------------------------
# Global SEO settings
# ---------------------------------------------------------------------------


class SeoSettingRead(BaseModel):
    """Full singleton SEO-settings row as read by admin + public clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    site_name: Optional[str] = None
    default_meta_title: Optional[str] = None
    default_meta_description: Optional[str] = None
    default_meta_keywords: Optional[str] = None
    canonical_base_url: Optional[str] = None
    default_language: Optional[str] = None
    default_country: Optional[str] = None
    default_og_image: Optional[str] = None
    default_twitter_image: Optional[str] = None

    enable_sitemap: bool = True
    enable_robots: bool = True
    enable_open_graph: bool = True
    enable_twitter_cards: bool = True
    enable_json_ld: bool = True
    enable_canonical: bool = True
    enable_hreflang: bool = False
    enable_breadcrumb_schema: bool = True

    sitemap_default_changefreq: Optional[str] = None
    sitemap_default_priority: Optional[float] = None
    sitemap_include_static: bool = True
    sitemap_include_companies: bool = True
    sitemap_include_cms_pages: bool = True
    sitemap_include_news: bool = True

    robots_use_default: bool = True
    robots_custom_content: Optional[str] = None
    robots_extra_disallows: Optional[str] = None

    updated_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class SeoSettingUpdate(BaseModel):
    """Partial update — every field optional so the admin form can PATCH any subset."""

    site_name: Optional[str] = Field(default=None, max_length=255)
    default_meta_title: Optional[str] = Field(default=None, max_length=255)
    default_meta_description: Optional[str] = Field(default=None, max_length=500)
    default_meta_keywords: Optional[str] = Field(default=None, max_length=500)
    canonical_base_url: Optional[str] = Field(default=None, max_length=500)
    default_language: Optional[str] = Field(default=None, max_length=16)
    default_country: Optional[str] = Field(default=None, max_length=16)
    default_og_image: Optional[str] = Field(default=None, max_length=500)
    default_twitter_image: Optional[str] = Field(default=None, max_length=500)

    enable_sitemap: Optional[bool] = None
    enable_robots: Optional[bool] = None
    enable_open_graph: Optional[bool] = None
    enable_twitter_cards: Optional[bool] = None
    enable_json_ld: Optional[bool] = None
    enable_canonical: Optional[bool] = None
    enable_hreflang: Optional[bool] = None
    enable_breadcrumb_schema: Optional[bool] = None

    sitemap_default_changefreq: Optional[str] = None
    sitemap_default_priority: Optional[float] = None
    sitemap_include_static: Optional[bool] = None
    sitemap_include_companies: Optional[bool] = None
    sitemap_include_cms_pages: Optional[bool] = None
    sitemap_include_news: Optional[bool] = None

    robots_use_default: Optional[bool] = None
    robots_custom_content: Optional[str] = None
    robots_extra_disallows: Optional[str] = None

    @field_validator("canonical_base_url")
    @classmethod
    def _validate_canonical(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        if not v.lower().startswith("https://"):
            raise ValueError("Canonical Base URL must start with https://")
        return v.rstrip("/")

    @field_validator("sitemap_default_changefreq")
    @classmethod
    def _validate_changefreq(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, ""):
            return None
        normalised = v.lower()
        if normalised not in CHANGEFREQS:
            raise ValueError(
                f"changefreq must be one of: {', '.join(sorted(CHANGEFREQS))}"
            )
        return normalised

    @field_validator("sitemap_default_priority")
    @classmethod
    def _validate_priority(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if v < 0.0 or v > 1.0:
            raise ValueError("Priority must be between 0.0 and 1.0")
        return round(v, 2)


# ---------------------------------------------------------------------------
# Verification records
# ---------------------------------------------------------------------------


class SeoVerificationBase(BaseModel):
    provider: str = Field(min_length=2, max_length=40)
    verification_type: str = Field(min_length=3, max_length=20)
    verification_name: Optional[str] = Field(default=None, max_length=120)
    verification_content: Optional[str] = Field(default=None, max_length=500)
    full_meta_tag: Optional[str] = None
    html_filename: Optional[str] = Field(default=None, max_length=255)
    html_file_content: Optional[str] = None
    dns_txt_value: Optional[str] = Field(default=None, max_length=500)
    status: str = VERIFICATION_STATUS_PENDING
    is_active: bool = True
    notes: Optional[str] = None

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, v: str) -> str:
        key = v.strip().lower()
        if key not in VERIFICATION_PROVIDERS:
            raise ValueError(
                f"provider must be one of: {', '.join(sorted(VERIFICATION_PROVIDERS))}"
            )
        return key

    @field_validator("verification_type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        key = v.strip().lower()
        if key not in VERIFICATION_TYPES:
            raise ValueError(
                f"verification_type must be one of: {', '.join(sorted(VERIFICATION_TYPES))}"
            )
        return key

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        key = v.strip().lower()
        if key not in VERIFICATION_STATUSES:
            raise ValueError(
                f"status must be one of: {', '.join(sorted(VERIFICATION_STATUSES))}"
            )
        return key

    @field_validator("html_filename")
    @classmethod
    def _validate_filename(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, ""):
            return None
        name = v.strip()
        # Path traversal + slashes are an absolute no.
        if "/" in name or "\\" in name or ".." in name:
            raise ValueError("Filename may not contain slashes or traversal sequences")
        if not HTML_VERIFICATION_FILENAME_RE.match(name):
            raise ValueError(
                "Filename must match a known verification pattern "
                "(e.g. googleXXXX.html, BingSiteAuth.xml, pinterest-XXXX.html)"
            )
        return name


class SeoVerificationCreate(SeoVerificationBase):
    pass


class SeoVerificationUpdate(BaseModel):
    provider: Optional[str] = None
    verification_type: Optional[str] = None
    verification_name: Optional[str] = Field(default=None, max_length=120)
    verification_content: Optional[str] = Field(default=None, max_length=500)
    full_meta_tag: Optional[str] = None
    html_filename: Optional[str] = Field(default=None, max_length=255)
    html_file_content: Optional[str] = None
    dns_txt_value: Optional[str] = Field(default=None, max_length=500)
    status: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

    _validate_provider = field_validator("provider")(
        SeoVerificationBase._validate_provider.__func__  # type: ignore[attr-defined]
    )
    _validate_type = field_validator("verification_type")(
        SeoVerificationBase._validate_type.__func__  # type: ignore[attr-defined]
    )
    _validate_status = field_validator("status")(
        SeoVerificationBase._validate_status.__func__  # type: ignore[attr-defined]
    )
    _validate_filename = field_validator("html_filename")(
        SeoVerificationBase._validate_filename.__func__  # type: ignore[attr-defined]
    )


class SeoVerificationRead(SeoVerificationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by_id: Optional[int] = None
    updated_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Tracking integrations
# ---------------------------------------------------------------------------


class TrackingIntegrationUpsert(BaseModel):
    """Upsert payload — admin saves a row by provider key."""

    provider: str
    tracking_id: Optional[str] = Field(default=None, max_length=120)
    secondary_id: Optional[str] = Field(default=None, max_length=120)
    data_layer_name: Optional[str] = Field(default=None, max_length=60)
    placement: Optional[str] = None
    enable_noscript: Optional[bool] = None
    consent_mode_enabled: Optional[bool] = None
    debug_mode: Optional[bool] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("provider")
    @classmethod
    def _validate_provider(cls, v: str) -> str:
        key = v.strip().lower()
        if key not in TRACKING_PROVIDERS:
            raise ValueError(
                f"provider must be one of: {', '.join(sorted(TRACKING_PROVIDERS))}"
            )
        return key

    @field_validator("placement")
    @classmethod
    def _validate_placement(cls, v: Optional[str]) -> Optional[str]:
        if v in (None, ""):
            return PLACEMENT_HEAD
        key = v.strip().lower()
        if key not in PLACEMENTS:
            raise ValueError(
                f"placement must be one of: {', '.join(sorted(PLACEMENTS))}"
            )
        return key


class TrackingIntegrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    tracking_id: Optional[str] = None
    secondary_id: Optional[str] = None
    data_layer_name: str = "dataLayer"
    placement: str = PLACEMENT_HEAD
    enable_noscript: bool = True
    consent_mode_enabled: bool = False
    debug_mode: bool = False
    is_active: bool = True
    notes: Optional[str] = None
    created_by_id: Optional[int] = None
    updated_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Aggregate dashboard payload
# ---------------------------------------------------------------------------


class SeoDashboardRead(BaseModel):
    """Admin dashboard summary surfaced under the SEO → Dashboard tab."""

    canonical_base_url: Optional[str] = None
    sitemap_enabled: bool
    robots_enabled: bool
    gtm_active: bool
    gtm_id: Optional[str] = None
    ga4_active: bool
    ga4_id: Optional[str] = None
    meta_pixel_active: bool
    meta_pixel_id: Optional[str] = None
    clarity_active: bool
    clarity_id: Optional[str] = None
    google_verification_active: bool
    bing_verification_active: bool
    meta_verification_active: bool
    active_integrations: List[str]
    active_verifications: List[str]
    duplicate_tracking_warning: Optional[str] = None
    last_updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Public head feed
# ---------------------------------------------------------------------------


class PublicVerificationMeta(BaseModel):
    """Single meta tag the public layout should inject into `<head>`."""

    name: Optional[str] = None
    property: Optional[str] = None
    content: str


class PublicTrackingIntegration(BaseModel):
    """Active integration as exposed to the public renderer."""

    provider: str
    tracking_id: str
    data_layer_name: str = "dataLayer"
    placement: str = PLACEMENT_HEAD
    enable_noscript: bool = True
    consent_mode_enabled: bool = False
    debug_mode: bool = False


class PublicSeoHeadFeed(BaseModel):
    """Bundle of everything the public layout needs to render the SEO `<head>`."""

    site_name: Optional[str] = None
    default_meta_title: Optional[str] = None
    default_meta_description: Optional[str] = None
    canonical_base_url: Optional[str] = None
    default_language: Optional[str] = None
    enable_canonical: bool = True
    enable_open_graph: bool = True
    enable_twitter_cards: bool = True
    default_og_image: Optional[str] = None
    default_twitter_image: Optional[str] = None
    # Sitemap toggles — consumed by `app/sitemap.ts`.
    enable_sitemap: bool = True
    sitemap_include_static: bool = True
    sitemap_include_companies: bool = True
    sitemap_include_cms_pages: bool = True
    sitemap_include_news: bool = True
    sitemap_default_changefreq: Optional[str] = None
    sitemap_default_priority: Optional[float] = None
    verification_metas: List[PublicVerificationMeta] = Field(default_factory=list)
    integrations: List[PublicTrackingIntegration] = Field(default_factory=list)

"""ORM models for the SEO Configuration module (Phase 1).

Three tables:

  * :class:`SeoSetting` — singleton row holding the global SEO knobs
    that drive `<head>` rendering, the dynamic ``/sitemap.xml`` route,
    and the dynamic ``/robots.txt`` route.

  * :class:`SeoVerification` — one row per domain-verification record.
    Four shapes are supported (``meta_tag``, ``full_meta_tag``,
    ``html_file``, ``dns_txt``) — see the column docs below.

  * :class:`TrackingIntegration` — one row per analytics / marketing
    integration. Phase 1 supports Google Tag Manager (preferred hub),
    Google Analytics 4, Meta Pixel, Microsoft Clarity, LinkedIn
    Insight, TikTok Pixel, X Pixel, and a generic ``custom`` slot.

All three tables track ``created_at``/``updated_at`` plus the user
ID that last touched the row, mirroring the audit pattern used in
``cms.SiteSetting``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# ---------------------------------------------------------------------------
# Verification provider / type constants (kept in Python so the API + admin
# UI agree on the same vocabulary)
# ---------------------------------------------------------------------------
VERIFICATION_TYPE_META = "meta_tag"
VERIFICATION_TYPE_FULL_META = "full_meta_tag"
VERIFICATION_TYPE_HTML_FILE = "html_file"
VERIFICATION_TYPE_DNS_TXT = "dns_txt"
VERIFICATION_TYPES = {
    VERIFICATION_TYPE_META,
    VERIFICATION_TYPE_FULL_META,
    VERIFICATION_TYPE_HTML_FILE,
    VERIFICATION_TYPE_DNS_TXT,
}

VERIFICATION_STATUS_PENDING = "pending"
VERIFICATION_STATUS_VERIFIED = "verified_manually"
VERIFICATION_STATUS_FAILED = "failed"
VERIFICATION_STATUS_DNS_REQUIRED = "dns_required"
VERIFICATION_STATUSES = {
    VERIFICATION_STATUS_PENDING,
    VERIFICATION_STATUS_VERIFIED,
    VERIFICATION_STATUS_FAILED,
    VERIFICATION_STATUS_DNS_REQUIRED,
}

VERIFICATION_PROVIDERS = {
    "google",
    "bing",
    "meta",
    "pinterest",
    "yandex",
    "linkedin",
    "tiktok",
    "microsoft_ads",
    "custom",
}


# Tracking provider keys. The admin UI shows one card per provider.
PROVIDER_GTM = "google_tag_manager"
PROVIDER_GA4 = "google_analytics_ga4"
PROVIDER_META_PIXEL = "meta_pixel"
PROVIDER_CLARITY = "microsoft_clarity"
PROVIDER_LINKEDIN = "linkedin_insight"
PROVIDER_TIKTOK = "tiktok_pixel"
PROVIDER_X = "twitter_pixel"
PROVIDER_CUSTOM = "custom"
TRACKING_PROVIDERS = {
    PROVIDER_GTM,
    PROVIDER_GA4,
    PROVIDER_META_PIXEL,
    PROVIDER_CLARITY,
    PROVIDER_LINKEDIN,
    PROVIDER_TIKTOK,
    PROVIDER_X,
    PROVIDER_CUSTOM,
}

PLACEMENT_HEAD = "head"
PLACEMENT_BODY_START = "body_start"
PLACEMENT_BODY_END = "body_end"
PLACEMENTS = {PLACEMENT_HEAD, PLACEMENT_BODY_START, PLACEMENT_BODY_END}


class SeoSetting(Base):
    """Singleton row holding global SEO defaults + feature toggles."""

    __tablename__ = "seo_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    site_name: Mapped[Optional[str]] = mapped_column(String(255))
    default_meta_title: Mapped[Optional[str]] = mapped_column(String(255))
    default_meta_description: Mapped[Optional[str]] = mapped_column(String(500))
    default_meta_keywords: Mapped[Optional[str]] = mapped_column(String(500))
    canonical_base_url: Mapped[Optional[str]] = mapped_column(String(500))
    default_language: Mapped[Optional[str]] = mapped_column(String(16))
    default_country: Mapped[Optional[str]] = mapped_column(String(16))
    default_og_image: Mapped[Optional[str]] = mapped_column(String(500))
    default_twitter_image: Mapped[Optional[str]] = mapped_column(String(500))

    enable_sitemap: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    enable_robots: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    enable_open_graph: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    enable_twitter_cards: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    enable_json_ld: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    enable_canonical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    enable_hreflang: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    enable_breadcrumb_schema: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    sitemap_default_changefreq: Mapped[Optional[str]] = mapped_column(String(20))
    sitemap_default_priority: Mapped[Optional[float]] = mapped_column(Float())
    sitemap_include_static: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    sitemap_include_companies: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    sitemap_include_cms_pages: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    sitemap_include_news: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    robots_use_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    robots_custom_content: Mapped[Optional[str]] = mapped_column(Text)
    robots_extra_disallows: Mapped[Optional[str]] = mapped_column(Text)

    updated_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SeoVerification(Base):
    """One domain-verification record (Google Search Console, Bing, etc.)."""

    __tablename__ = "seo_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    verification_type: Mapped[str] = mapped_column(String(20), nullable=False)
    verification_name: Mapped[Optional[str]] = mapped_column(String(120))
    verification_content: Mapped[Optional[str]] = mapped_column(String(500))
    full_meta_tag: Mapped[Optional[str]] = mapped_column(Text)
    html_filename: Mapped[Optional[str]] = mapped_column(String(255))
    html_file_content: Mapped[Optional[str]] = mapped_column(Text)
    dns_txt_value: Mapped[Optional[str]] = mapped_column(String(500))

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=VERIFICATION_STATUS_PENDING,
        server_default=VERIFICATION_STATUS_PENDING,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TrackingIntegration(Base):
    """One analytics / marketing integration row.

    The unique constraint on ``provider`` enforces at-most-one row per
    provider. Admins re-edit the row rather than creating duplicates,
    which keeps the public renderer simple (one ID per provider).
    """

    __tablename__ = "tracking_integrations"
    __table_args__ = (
        UniqueConstraint("provider", name="uq_tracking_integration_provider"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    tracking_id: Mapped[Optional[str]] = mapped_column(String(120))
    secondary_id: Mapped[Optional[str]] = mapped_column(String(120))
    data_layer_name: Mapped[str] = mapped_column(
        String(60), nullable=False, default="dataLayer", server_default="dataLayer"
    )
    placement: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PLACEMENT_HEAD, server_default=PLACEMENT_HEAD
    )
    enable_noscript: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    consent_mode_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    debug_mode: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    created_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

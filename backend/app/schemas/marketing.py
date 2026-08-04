"""Pydantic schemas for the Digital Offers & Catalogue module."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


# ---------------------------------------------------------------------------
# Campaign
# ---------------------------------------------------------------------------


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=8000)
    banner_image_url: Optional[str] = Field(default=None, max_length=500)
    theme_color: Optional[str] = Field(default=None, max_length=16)
    # Structured branch targeting. ``None`` = all branches — the
    # campaign appears on every branch's storefront. ``branch`` below
    # is the legacy free-text label, retained so existing rows and
    # integrations keep working; new writes should set division_id.
    division_id: Optional[int] = None
    branch: Optional[str] = Field(default=None, max_length=120)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: bool = True
    is_featured: bool = False
    is_killer_offer: bool = False
    is_flash_sale: bool = False
    sort_order: int = Field(default=0, ge=-10000, le=10000)
    meta_title: Optional[str] = Field(default=None, max_length=200)
    meta_description: Optional[str] = Field(default=None, max_length=500)

    @field_validator("slug")
    @classmethod
    def _slug_shape(cls, v: str) -> str:
        v = v.strip().lower()
        if not SLUG_RE.match(v):
            raise ValueError(
                "slug must be lowercase letters/digits/hyphens, not start/end with a hyphen"
            )
        return v

    @field_validator("theme_color")
    @classmethod
    def _hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if not HEX_RE.match(v):
            raise ValueError("theme_color must be a hex string like #17382f")
        return v


class CampaignUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: Optional[str] = Field(default=None, min_length=1, max_length=200)
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=8000)
    banner_image_url: Optional[str] = Field(default=None, max_length=500)
    theme_color: Optional[str] = Field(default=None, max_length=16)
    # See CampaignCreate.division_id. Sentinel note: because this is a
    # PATCH schema, ``None`` means "unchanged" for every other field —
    # to move a campaign back to all-branches the endpoint accepts
    # ``division_id: 0`` and maps it to NULL.
    division_id: Optional[int] = None
    branch: Optional[str] = Field(default=None, max_length=120)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    is_killer_offer: Optional[bool] = None
    is_flash_sale: Optional[bool] = None
    sort_order: Optional[int] = Field(default=None, ge=-10000, le=10000)
    meta_title: Optional[str] = Field(default=None, max_length=200)
    meta_description: Optional[str] = Field(default=None, max_length=500)

    @field_validator("slug")
    @classmethod
    def _slug_shape(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if not SLUG_RE.match(v):
            raise ValueError("invalid slug")
        return v

    @field_validator("theme_color")
    @classmethod
    def _hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if not HEX_RE.match(v):
            raise ValueError("theme_color must be a hex string like #17382f")
        return v


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: Optional[str]
    banner_image_url: Optional[str]
    theme_color: Optional[str]
    division_id: Optional[int] = None
    # Resolved from the FK by the endpoint so list rows can print the
    # branch name without the client joining anything.
    division_name: Optional[str] = None
    branch: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    is_active: bool
    is_featured: bool
    is_killer_offer: bool
    is_flash_sale: bool
    sort_order: int
    meta_title: Optional[str]
    meta_description: Optional[str]
    view_count: int
    catalogue_count: int = 0
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


class CatalogueCreate(BaseModel):
    """Form fields sent alongside the PDF in the upload multipart."""

    model_config = ConfigDict(extra="ignore")

    slug: str
    title: str
    description: Optional[str] = None
    campaign_id: Optional[int] = None
    # Branch targeting independent of the campaign — same campaign can
    # run group-wide while each branch gets its own flyer.
    division_id: Optional[int] = None
    is_active: bool = True
    is_featured: bool = False
    sort_order: int = 0
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


class CatalogueUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    campaign_id: Optional[int] = None
    # See CatalogueCreate.division_id. ``0`` clears it to all-branches.
    division_id: Optional[int] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    sort_order: Optional[int] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    qr_logo_url: Optional[str] = None


class CataloguePageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page_number: int
    image_url: str
    thumbnail_url: str
    width: int
    height: int


class CatalogueRead(BaseModel):
    """Compact catalogue summary used in lists + campaign-detail."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: Optional[int]
    division_id: Optional[int] = None
    division_name: Optional[str] = None
    slug: str
    title: str
    description: Optional[str]
    cover_image_url: Optional[str]
    qr_logo_url: Optional[str] = None
    pdf_url: Optional[str]
    page_count: int
    processing_status: str
    processing_error: Optional[str]
    is_active: bool
    is_featured: bool
    sort_order: int
    view_count: int
    download_count: int
    file_size_bytes: Optional[int]
    meta_title: Optional[str]
    meta_description: Optional[str]
    created_at: datetime
    updated_at: datetime


class CatalogueDetail(CatalogueRead):
    """Full catalogue including every page — used by the viewer."""

    pages: List[CataloguePageRead] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Public-side aggregates
# ---------------------------------------------------------------------------


class BranchSummary(BaseModel):
    """One entry in the public branch picker."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    city: Optional[str] = None


class BranchSocialLinks(BaseModel):
    """Only the populated links — the footer renders what it's given."""

    model_config = ConfigDict(extra="forbid")

    facebook: Optional[str] = None
    instagram: Optional[str] = None
    tiktok: Optional[str] = None
    youtube: Optional[str] = None
    snapchat: Optional[str] = None
    x: Optional[str] = None


class OffersIndexCampaign(BaseModel):
    """One row in the public /offers landing list — campaign card."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    description: Optional[str]
    banner_image_url: Optional[str]
    theme_color: Optional[str]
    branch: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    is_featured: bool
    is_killer_offer: bool
    is_flash_sale: bool
    # ``True`` when ``end_date`` is in the past. Surfaced on the
    # public landing so historical campaigns render with an
    # "EXPIRED" badge instead of being hidden entirely — the
    # operator can still review past assets and customers don't
    # land on a 404 when following an old social-share link.
    is_expired: bool = False
    catalogue_count: int
    cover_image_url: Optional[str]


class OffersIndexCatalogue(BaseModel):
    """One catalogue tile on the landing / branch page.

    Rendered for every active + ready catalogue, whether or not it's
    attached to a campaign — an unattached flyer is still a flyer, and
    hiding it was what left the landing looking empty.
    """

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    description: Optional[str]
    cover_image_url: Optional[str]
    page_count: int
    # Branch label for the tile's chip. ``None`` = all branches.
    branch_name: Optional[str] = None
    is_featured: bool = False
    # Drives the "NEW" badge — the client compares against its own
    # clock rather than the server pre-computing a boolean that would
    # go stale in the CDN cache.
    created_at: Optional[datetime] = None


class OffersIndex(BaseModel):
    """Whole landing-page payload — everything the /offers page needs
    in one round-trip."""

    featured: List[OffersIndexCampaign] = Field(default_factory=list)
    killer_offers: List[OffersIndexCampaign] = Field(default_factory=list)
    flash_sales: List[OffersIndexCampaign] = Field(default_factory=list)
    all_campaigns: List[OffersIndexCampaign] = Field(default_factory=list)
    # Every active+ready catalogue, regardless of campaign attachment.
    # The landing renders this as a "Catalogues" section so a flyer
    # always shows up — even if its parent campaign is inactive, has
    # the wrong date range, or wasn't created at all.
    all_catalogues: List[OffersIndexCatalogue] = Field(default_factory=list)
    branches: List[BranchSummary] = Field(default_factory=list)


class CampaignPublicDetail(BaseModel):
    """Full payload for /offers/{slug} — campaign + every active catalogue."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    description: Optional[str]
    banner_image_url: Optional[str]
    theme_color: Optional[str]
    branch: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    # See ``OffersIndexCampaign.is_expired`` — same semantics. The
    # detail page surfaces this with a prominent banner notice so
    # someone who lands here via an old share link sees that the
    # promotion has ended.
    is_expired: bool = False
    meta_title: Optional[str]
    meta_description: Optional[str]
    catalogues: List[CatalogueRead] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class CatalogueViewLog(BaseModel):
    """Body of the public "I opened the viewer" beacon."""

    model_config = ConfigDict(extra="forbid")

    session_hash: Optional[str] = Field(default=None, max_length=64)
    device: Optional[str] = Field(default=None, max_length=16)
    duration_seconds: Optional[int] = Field(default=None, ge=0, le=86400)


class CatalogueAnalytics(BaseModel):
    catalogue_id: int
    total_views: int
    unique_sessions: int
    by_device: dict[str, int]
    last_7_days: list[dict]  # [{"date": "...", "views": N}, ...]


# ---------------------------------------------------------------------------
# Marketing dashboard — admin landing
# ---------------------------------------------------------------------------


class MarketingDashboardKpis(BaseModel):
    """Top-of-page KPI tiles.

    Period-scoped values (``*_period``) reflect the selected lookback
    window; ``*_all_time`` ignores it so the operator can see lifetime
    totals alongside recent activity.
    """

    campaigns_total: int
    campaigns_active: int
    catalogues_total: int
    catalogues_ready: int
    catalogues_processing: int
    catalogues_failed: int
    total_pages: int
    total_views_period: int
    total_views_all_time: int
    unique_sessions_period: int
    total_downloads_all_time: int
    avg_session_duration_sec: int


class MarketingDashboardSeriesPoint(BaseModel):
    date: date  # day bucket (UTC)
    views: int


class MarketingDashboardTopCatalogue(BaseModel):
    id: int
    slug: str
    title: str
    campaign_id: Optional[int] = None
    campaign_title: Optional[str] = None
    views: int
    downloads: int


class MarketingDashboardTopCampaign(BaseModel):
    id: int
    slug: str
    title: str
    branch: Optional[str] = None
    catalogue_count: int
    views: int


class MarketingDashboardRecentView(BaseModel):
    catalogue_id: int
    catalogue_title: str
    catalogue_slug: str
    device: Optional[str] = None
    duration_seconds: Optional[int] = None
    viewed_at: datetime


class MarketingDashboard(BaseModel):
    """Full payload powering the admin Marketing → Dashboard page."""

    period_days: int
    period_label: str
    generated_at: datetime
    kpis: MarketingDashboardKpis
    views_over_time: list[MarketingDashboardSeriesPoint]
    top_catalogues: list[MarketingDashboardTopCatalogue]
    top_campaigns: list[MarketingDashboardTopCampaign]
    by_device: dict[str, int]
    recent_views: list[MarketingDashboardRecentView]


class ReconcileCountersResult(BaseModel):
    """Outcome of resyncing ``catalogue.view_count`` from events."""

    catalogues_inspected: int
    catalogues_updated: int
    total_view_count_before: int
    total_view_count_after: int

# ---------------------------------------------------------------------------
# Branch storefronts (public /offers/{branch-slug})
# ---------------------------------------------------------------------------


class BranchPage(BaseModel):
    """Payload for ``/offers/{branch-slug}`` — the storefront page.

    Carries the branch identity (header), its contact block (footer),
    and every campaign + catalogue targeted at it. "Targeted at it"
    deliberately includes all-branch content: a shopper standing in Al
    Khor should see the group-wide flyer as well as the Al Khor one.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    city: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    hero_image_url: Optional[str] = None

    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    opening_hours: Optional[str] = None
    maps_url: Optional[str] = None
    social: BranchSocialLinks = Field(default_factory=BranchSocialLinks)

    campaigns: List[OffersIndexCampaign] = Field(default_factory=list)
    catalogues: List[OffersIndexCatalogue] = Field(default_factory=list)
    # Sibling branches, so the storefront can offer a "switch branch"
    # control without a second request.
    other_branches: List[BranchSummary] = Field(default_factory=list)


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
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    sort_order: Optional[int] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


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
    slug: str
    title: str
    description: Optional[str]
    cover_image_url: Optional[str]
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
    catalogue_count: int
    cover_image_url: Optional[str]


class OffersIndexCatalogue(BaseModel):
    """One row in the public /offers landing list — catalogue card,
    rendered for active+ready catalogues that aren't attached to any
    campaign yet (so they don't disappear from the public surface)."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    description: Optional[str]
    cover_image_url: Optional[str]
    page_count: int


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
    branches: List[str] = Field(default_factory=list)


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

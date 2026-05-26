"""Pydantic schemas for the Phase 5 CMS endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


def _normalise_url_value(value: Any) -> Any:
    """Replace Windows-style backslashes in URL strings.

    Admins occasionally paste a local Windows file path
    (e.g. ``\\images\\foo\\bar.webp``) into a URL field. That value
    survives the form unchanged and the public site renders a 404.
    Treating any backslash as a forward slash on write keeps the data
    clean without making the field's type any more restrictive — the
    admin can still type whatever they want, but a stray backslash
    won't silently break the live image.
    """
    if isinstance(value, str) and "\\" in value:
        return value.replace("\\", "/").strip()
    return value


def _normalise_url_fields(values: Any) -> Any:
    """``model_validator(mode='before')`` helper.

    Walks the input dict and applies :func:`_normalise_url_value` to any
    key whose name ends with ``_url`` — covers every URL-shaped field
    on every schema in this module (hero slide, company, leadership,
    news, site settings, …) without enumerating them.
    """
    if isinstance(values, dict):
        for key, value in list(values.items()):
            if key.endswith("_url"):
                values[key] = _normalise_url_value(value)
    return values


# ---------------------------------------------------------------------------
# Hero slides
# ---------------------------------------------------------------------------


class HeroSlideBase(BaseModel):
    eyebrow: Optional[str] = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    cta_label: Optional[str] = Field(default=None, max_length=120)
    cta_href: Optional[str] = Field(default=None, max_length=255)
    secondary_cta_label: Optional[str] = Field(default=None, max_length=120)
    secondary_cta_href: Optional[str] = Field(default=None, max_length=255)
    background_image_url: Optional[str] = Field(default=None, max_length=500)
    background_video_url: Optional[str] = Field(default=None, max_length=500)
    gradient: str = Field(
        default="from-pug-green-700 via-pug-green-500 to-pug-gold-500",
        max_length=255,
    )
    display_order: int = 0
    is_active: bool = True


class HeroSlideCreate(HeroSlideBase):
    pass


class HeroSlideUpdate(BaseModel):
    eyebrow: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    cta_label: Optional[str] = None
    cta_href: Optional[str] = None
    secondary_cta_label: Optional[str] = None
    secondary_cta_href: Optional[str] = None
    background_image_url: Optional[str] = None
    background_video_url: Optional[str] = None
    gradient: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class HeroSlideRead(HeroSlideBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Navigation menu (Phase 5 follow-up)
# ---------------------------------------------------------------------------


class NavigationItemBase(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    href: str = Field(min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=255)
    mega_kind: Optional[str] = Field(default=None, pattern=r"^(companies)$")
    open_in_new_tab: bool = False
    display_order: int = 0
    is_active: bool = True


class NavigationItemCreate(NavigationItemBase):
    parent_id: Optional[int] = None


class NavigationItemUpdate(BaseModel):
    label: Optional[str] = Field(default=None, min_length=1, max_length=120)
    href: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = None
    mega_kind: Optional[str] = Field(default=None, pattern=r"^(companies)$")
    open_in_new_tab: Optional[bool] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None
    parent_id: Optional[int] = None


class NavigationItemRead(NavigationItemBase):
    """Single navigation node (without children) used inside admin lists."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: Optional[int] = None


class NavigationItemTreeRead(NavigationItemRead):
    """Tree-shaped payload returned by the public + admin GET endpoints."""

    children: List["NavigationItemTreeRead"] = Field(default_factory=list)


NavigationItemTreeRead.model_rebuild()


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------


class CompanyServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_order: int = 0


class CompanyBrandLogoRead(BaseModel):
    """Logo image displayed inside the Group Companies marquee."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    name: Optional[str] = None
    link_url: Optional[str] = None
    display_order: int = 0


class CompanyBrandLogoInput(BaseModel):
    """Admin-side payload — `id` is omitted because the relation is
    replaced wholesale on every save (same pattern as ``services``)."""

    image_url: str = Field(min_length=1, max_length=500)
    name: Optional[str] = Field(default=None, max_length=120)
    link_url: Optional[str] = Field(default=None, max_length=500)
    display_order: int = 0


class CompanyBase(BaseModel):
    # Normalise any *_url field on write so a stray backslash from an
    # admin paste never reaches the database. See _normalise_url_fields
    # at the top of this module for the rationale.
    _normalise_urls = model_validator(mode="before")(
        classmethod(lambda cls, v: _normalise_url_fields(v))
    )

    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(pattern=r"^(distribution|retail|services)$")
    short_description: Optional[str] = Field(default=None, max_length=500)
    long_description: Optional[str] = None
    # Homepage Group Companies overrides — see model docstring.
    homepage_highlight_description: Optional[str] = None
    homepage_highlight_points: Optional[str] = None
    # Phase 18 follow-up — richer Group Companies homepage card + video.
    homepage_group_highlight: Optional[str] = None
    homepage_group_stat_line: Optional[str] = Field(default=None, max_length=255)
    homepage_group_video_url: Optional[str] = Field(default=None, max_length=500)
    homepage_group_video_poster_url: Optional[str] = Field(
        default=None, max_length=500
    )
    branches: Optional[str] = Field(default=None, max_length=255)
    accent: str = Field(
        default="from-pug-green-500 to-pug-gold-500", max_length=255
    )
    initials: str = Field(min_length=1, max_length=8)
    brand_logo_url: Optional[str] = Field(default=None, max_length=500)
    phone: Optional[str] = Field(default=None, max_length=40)
    email: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = Field(default=None, max_length=500)
    website: Optional[str] = Field(default=None, max_length=255)
    featured_image_url: Optional[str] = Field(default=None, max_length=500)
    cta_label: Optional[str] = Field(default=None, max_length=120)
    cta_url: Optional[str] = Field(default=None, max_length=500)
    is_highlighted: bool = False
    display_order: int = 0
    is_active: bool = True


class CompanyCreate(CompanyBase):
    services: List[str] = Field(default_factory=list)
    brand_logos: List[CompanyBrandLogoInput] = Field(default_factory=list)


class CompanyUpdate(BaseModel):
    _normalise_urls = model_validator(mode="before")(
        classmethod(lambda cls, v: _normalise_url_fields(v))
    )

    slug: Optional[str] = Field(default=None, pattern=r"^[a-z0-9-]+$")
    name: Optional[str] = None
    category: Optional[str] = Field(
        default=None, pattern=r"^(distribution|retail|services)$"
    )
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    homepage_highlight_description: Optional[str] = None
    homepage_highlight_points: Optional[str] = None
    homepage_group_highlight: Optional[str] = None
    homepage_group_stat_line: Optional[str] = None
    homepage_group_video_url: Optional[str] = None
    homepage_group_video_poster_url: Optional[str] = None
    branches: Optional[str] = None
    accent: Optional[str] = None
    initials: Optional[str] = None
    brand_logo_url: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    featured_image_url: Optional[str] = None
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    is_highlighted: Optional[bool] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None
    services: Optional[List[str]] = None
    brand_logos: Optional[List[CompanyBrandLogoInput]] = None


class CompanyRead(CompanyBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    services: List[CompanyServiceRead] = Field(default_factory=list)
    brand_logos: List[CompanyBrandLogoRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Leadership
# ---------------------------------------------------------------------------


class LeadershipBase(BaseModel):
    _normalise_urls = model_validator(mode="before")(
        classmethod(lambda cls, v: _normalise_url_fields(v))
    )

    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    name: str
    role: str
    short_message: Optional[str] = Field(default=None, max_length=500)
    full_message: Optional[str] = None
    accent: str = Field(
        default="from-pug-green-600 to-pug-gold-500", max_length=255
    )
    initials: str = Field(min_length=1, max_length=8)
    photo_url: Optional[str] = Field(default=None, max_length=500)
    signature: Optional[str] = None
    # Unified homepage Leadership Messages fields
    role_label: Optional[str] = Field(default=None, max_length=120)
    message_paragraph_1: Optional[str] = None
    message_paragraph_2: Optional[str] = None
    highlight_quote: Optional[str] = None
    signature_image_url: Optional[str] = Field(default=None, max_length=500)
    cta_label: Optional[str] = Field(default=None, max_length=120)
    cta_url: Optional[str] = Field(default=None, max_length=500)
    is_homepage_featured: bool = False
    display_order: int = 0
    is_active: bool = True


class LeadershipCreate(LeadershipBase):
    pass


class LeadershipUpdate(BaseModel):
    _normalise_urls = model_validator(mode="before")(
        classmethod(lambda cls, v: _normalise_url_fields(v))
    )

    slug: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    short_message: Optional[str] = None
    full_message: Optional[str] = None
    accent: Optional[str] = None
    initials: Optional[str] = None
    photo_url: Optional[str] = None
    signature: Optional[str] = None
    role_label: Optional[str] = None
    message_paragraph_1: Optional[str] = None
    message_paragraph_2: Optional[str] = None
    highlight_quote: Optional[str] = None
    signature_image_url: Optional[str] = None
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    is_homepage_featured: Optional[bool] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class LeadershipRead(LeadershipBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------


class NewsBase(BaseModel):
    slug: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=1, max_length=255)
    summary: Optional[str] = Field(default=None, max_length=500)
    body: Optional[str] = None
    category: str = Field(pattern=r"^(company|event|press|csr)$")
    author: Optional[str] = Field(default=None, max_length=120)
    cover: str = Field(
        default="from-pug-green-600 to-pug-gold-500", max_length=255
    )
    cover_image_url: Optional[str] = Field(default=None, max_length=500)
    published_at: Optional[datetime] = None
    is_featured: bool = False
    is_published: bool = True


class NewsCreate(NewsBase):
    pass


class NewsUpdate(BaseModel):
    slug: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = Field(
        default=None, pattern=r"^(company|event|press|csr)$"
    )
    author: Optional[str] = None
    cover: Optional[str] = None
    cover_image_url: Optional[str] = None
    published_at: Optional[datetime] = None
    is_featured: Optional[bool] = None
    is_published: Optional[bool] = None


class NewsRead(NewsBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Contact + newsletter (public submission + admin read/reply)
# ---------------------------------------------------------------------------


class ContactSubmit(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=40)
    department: Optional[str] = Field(default=None, max_length=64)
    subject: Optional[str] = Field(default=None, max_length=255)
    message: str = Field(min_length=1)


class ContactReply(BaseModel):
    reply_body: str = Field(min_length=1)


class ContactReplyRead(BaseModel):
    """One bubble in the contact-inbox chat thread."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_message_id: int
    direction: str
    admin_user_id: Optional[int] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    recipient_email: Optional[str] = None
    subject: Optional[str] = None
    body: str
    email_status: str
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ContactMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    phone: Optional[str] = None
    department: Optional[str] = None
    subject: Optional[str] = None
    message: str
    is_read: bool
    is_replied: bool
    is_archived: bool
    reply_body: Optional[str] = None
    replied_by_id: Optional[int] = None
    replied_at: Optional[datetime] = None
    created_at: datetime


class ContactMessageDetail(ContactMessageRead):
    """Contact message + every reply in the thread, oldest first."""

    replies: List[ContactReplyRead] = Field(default_factory=list)


class NewsletterSubscribe(BaseModel):
    email: EmailStr


class NewsletterSubscriberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Site settings
# ---------------------------------------------------------------------------


class SiteSettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site_name: str
    tagline: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    contact_address: Optional[str] = None
    contact_map_embed: Optional[str] = None
    whatsapp_number: Optional[str] = None
    social_linkedin: Optional[str] = None
    social_instagram: Optional[str] = None
    social_facebook: Optional[str] = None
    social_youtube: Optional[str] = None
    seo_default_title: Optional[str] = None
    seo_default_description: Optional[str] = None
    seo_keywords: Optional[str] = None

    featured_companies_enabled: bool = True
    featured_companies_eyebrow: Optional[str] = None
    featured_companies_title: Optional[str] = None
    featured_companies_subtitle: Optional[str] = None
    featured_companies_cta_label: Optional[str] = None
    featured_companies_cta_url: Optional[str] = None
    featured_companies_animation_enabled: bool = True

    # Page banners
    about_banner_image_url: Optional[str] = None
    about_banner_video_url: Optional[str] = None
    careers_banner_image_url: Optional[str] = None
    careers_banner_mobile_url: Optional[str] = None
    contact_banner_image_url: Optional[str] = None
    contact_banner_mobile_url: Optional[str] = None
    news_banner_image_url: Optional[str] = None
    news_banner_mobile_url: Optional[str] = None
    media_banner_image_url: Optional[str] = None
    media_banner_mobile_url: Optional[str] = None

    # Homepage extras
    home_about_image_url: Optional[str] = None
    home_about_title: Optional[str] = None
    home_about_body: Optional[str] = None
    home_founder_image_url: Optional[str] = None
    home_founder_name: Optional[str] = None
    home_founder_role: Optional[str] = None
    home_founder_message: Optional[str] = None

    # Trusted brands
    home_brand_logos: Optional[str] = None
    home_brand_strip_title: Optional[str] = None
    # Upgraded Trusted Brands section
    home_brand_section_enabled: bool = True
    home_brand_eyebrow: Optional[str] = None
    home_brand_title: Optional[str] = None
    home_brand_subtitle: Optional[str] = None
    home_brand_animation_enabled: bool = True
    home_brand_layout_mode: str = "marquee"

    # Unified Leadership Messages section
    home_leadership_section_enabled: bool = True
    home_leadership_section_eyebrow: Optional[str] = None
    home_leadership_section_title: Optional[str] = None
    home_leadership_section_subtitle: Optional[str] = None
    home_leadership_animation_enabled: bool = True

    # Theme settings (Phase 5 follow-up)
    theme_primary_hex: Optional[str] = Field(default=None, max_length=9)
    theme_accent_hex: Optional[str] = Field(default=None, max_length=9)
    theme_heading_font: Optional[str] = Field(default=None, max_length=120)
    theme_body_font: Optional[str] = Field(default=None, max_length=120)

    # Maintenance / Under-construction mode
    maintenance_mode_enabled: bool = False
    maintenance_message: Optional[str] = None
    maintenance_eta: Optional[str] = Field(default=None, max_length=120)


class SiteSettingUpdate(BaseModel):
    site_name: Optional[str] = None
    tagline: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    contact_address: Optional[str] = None
    contact_map_embed: Optional[str] = None
    whatsapp_number: Optional[str] = None
    social_linkedin: Optional[str] = None
    social_instagram: Optional[str] = None
    social_facebook: Optional[str] = None
    social_youtube: Optional[str] = None
    seo_default_title: Optional[str] = None
    seo_default_description: Optional[str] = None
    seo_keywords: Optional[str] = None

    featured_companies_enabled: Optional[bool] = None
    featured_companies_eyebrow: Optional[str] = None
    featured_companies_title: Optional[str] = None
    featured_companies_subtitle: Optional[str] = None
    featured_companies_cta_label: Optional[str] = None
    featured_companies_cta_url: Optional[str] = None
    featured_companies_animation_enabled: Optional[bool] = None

    about_banner_image_url: Optional[str] = None
    about_banner_video_url: Optional[str] = None
    careers_banner_image_url: Optional[str] = None
    careers_banner_mobile_url: Optional[str] = None
    contact_banner_image_url: Optional[str] = None
    contact_banner_mobile_url: Optional[str] = None
    news_banner_image_url: Optional[str] = None
    news_banner_mobile_url: Optional[str] = None
    media_banner_image_url: Optional[str] = None
    media_banner_mobile_url: Optional[str] = None

    home_about_image_url: Optional[str] = None
    home_about_title: Optional[str] = None
    home_about_body: Optional[str] = None
    home_founder_image_url: Optional[str] = None
    home_founder_name: Optional[str] = None
    home_founder_role: Optional[str] = None
    home_founder_message: Optional[str] = None

    home_brand_logos: Optional[str] = None
    home_brand_strip_title: Optional[str] = None
    home_brand_section_enabled: Optional[bool] = None
    home_brand_eyebrow: Optional[str] = None
    home_brand_title: Optional[str] = None
    home_brand_subtitle: Optional[str] = None
    home_brand_animation_enabled: Optional[bool] = None
    home_brand_layout_mode: Optional[str] = None

    home_leadership_section_enabled: Optional[bool] = None
    home_leadership_section_eyebrow: Optional[str] = None
    home_leadership_section_title: Optional[str] = None
    home_leadership_section_subtitle: Optional[str] = None
    home_leadership_animation_enabled: Optional[bool] = None

    theme_primary_hex: Optional[str] = None
    theme_accent_hex: Optional[str] = None
    theme_heading_font: Optional[str] = None
    theme_body_font: Optional[str] = None

    # Maintenance / Under-construction mode
    maintenance_mode_enabled: Optional[bool] = None
    maintenance_message: Optional[str] = None
    maintenance_eta: Optional[str] = Field(default=None, max_length=120)


# ---------------------------------------------------------------------------
# Homepage Leadership Messages (public)
# ---------------------------------------------------------------------------


class LeadershipMessageCardRead(BaseModel):
    """A single leader rendered inside the homepage Leadership Messages section."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    role_type: str
    role_label: Optional[str] = None
    name: str
    role: str
    designation: Optional[str] = None
    initials: str
    accent: str
    photo_url: Optional[str] = None
    signature_image_url: Optional[str] = None
    signature: Optional[str] = None
    highlight_quote: Optional[str] = None
    message_paragraph_1: Optional[str] = None
    message_paragraph_2: Optional[str] = None
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    display_order: int = 0
    is_active: bool = True


class HomepageLeadershipResponse(BaseModel):
    enabled: bool
    eyebrow: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    animation_enabled: bool
    messages: List[LeadershipMessageCardRead] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Featured-companies section (public)
# ---------------------------------------------------------------------------


class FeaturedSection(BaseModel):
    enabled: bool
    eyebrow: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    animation_enabled: bool = True


class FeaturedCompaniesSectionResponse(BaseModel):
    section: FeaturedSection
    companies: List[CompanyRead]


# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    url: str
    filename: str
    size: int
    mime_type: str


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


class DashboardStat(BaseModel):
    key: str
    label: str
    value: int


class MonthlyCount(BaseModel):
    month: str  # YYYY-MM
    count: int


class DashboardSummary(BaseModel):
    stats: List[DashboardStat]
    contact_messages_per_month: List[MonthlyCount]
    news_per_month: List[MonthlyCount]
    latest_contact_messages: List[ContactMessageRead]
    latest_news: List[NewsRead]


# ---------------------------------------------------------------------------
# Media gallery (Phase 5 follow-up)
# ---------------------------------------------------------------------------


MEDIA_KIND_PATTERN = r"^(image|video)$"


class MediaAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    filename: str
    original_name: Optional[str] = None
    url: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[int] = None
    title: Optional[str] = None
    alt_text: Optional[str] = None
    tags: Optional[str] = None
    is_public: bool = True
    # Resized WebP + JPEG URLs keyed by variant name. Shape:
    # {"webp": {"thumb": ..., "medium": ..., "large": ...},
    #  "jpg":  {"thumb": ..., "medium": ..., "large": ...}}
    # NULL when optimization was skipped (videos, SVG, broken files).
    variants: Optional[dict] = None
    uploaded_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class MediaAssetUpdate(BaseModel):
    """Manual metadata edit by an admin (does not touch the underlying file)."""

    title: Optional[str] = Field(default=None, max_length=255)
    alt_text: Optional[str] = Field(default=None, max_length=500)
    tags: Optional[str] = Field(default=None, max_length=500)
    is_public: Optional[bool] = None


class MediaUploadResult(BaseModel):
    """Returned by POST /admin/cms/media/upload — extends UploadResponse."""

    asset: MediaAssetRead
    deduped: bool = False


# ---------------------------------------------------------------------------
# Free-form CMS pages (Phase 5 follow-up)
# ---------------------------------------------------------------------------


SLUG_PATTERN = r"^[a-z0-9-]+$"


class CMSPageBase(BaseModel):
    slug: str = Field(min_length=1, max_length=160, pattern=SLUG_PATTERN)
    title: str = Field(min_length=1, max_length=255)
    eyebrow: Optional[str] = Field(default=None, max_length=120)
    summary: Optional[str] = Field(default=None, max_length=500)
    body: Optional[str] = None
    banner_image_url: Optional[str] = Field(default=None, max_length=500)
    banner_mobile_url: Optional[str] = Field(default=None, max_length=500)
    seo_title: Optional[str] = Field(default=None, max_length=255)
    seo_description: Optional[str] = Field(default=None, max_length=500)
    seo_keywords: Optional[str] = Field(default=None, max_length=500)
    is_published: bool = False
    display_order: int = 0


class CMSPageCreate(CMSPageBase):
    pass


class CMSPageUpdate(BaseModel):
    slug: Optional[str] = Field(default=None, pattern=SLUG_PATTERN)
    title: Optional[str] = Field(default=None, max_length=255)
    eyebrow: Optional[str] = Field(default=None, max_length=120)
    summary: Optional[str] = Field(default=None, max_length=500)
    body: Optional[str] = None
    banner_image_url: Optional[str] = Field(default=None, max_length=500)
    banner_mobile_url: Optional[str] = Field(default=None, max_length=500)
    seo_title: Optional[str] = Field(default=None, max_length=255)
    seo_description: Optional[str] = Field(default=None, max_length=500)
    seo_keywords: Optional[str] = Field(default=None, max_length=500)
    is_published: Optional[bool] = None
    display_order: Optional[int] = None


class CMSPageRead(CMSPageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    published_at: Optional[datetime] = None
    updated_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class CMSPageListItem(BaseModel):
    """Compact row for the admin pages table."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    summary: Optional[str] = None
    is_published: bool
    display_order: int
    published_at: Optional[datetime] = None
    updated_at: datetime


# ---------------------------------------------------------------------------
# Trusted Brands showcase
# ---------------------------------------------------------------------------


_ALLOWED_BRAND_LAYOUTS = {"marquee", "grid", "carousel"}


class TrustedBrandBase(BaseModel):
    """Shared admin fields for a brand row."""

    brand_name: str = Field(min_length=1, max_length=160)
    logo_url: str = Field(min_length=1, max_length=500)
    logo_url_alt: Optional[str] = Field(default=None, max_length=500)
    link_url: Optional[str] = Field(default=None, max_length=500)
    category: Optional[str] = Field(default=None, max_length=80)
    is_highlight: bool = False
    display_order: int = 0
    is_active: bool = True


class TrustedBrandCreate(TrustedBrandBase):
    pass


class TrustedBrandUpdate(BaseModel):
    brand_name: Optional[str] = Field(default=None, max_length=160)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    logo_url_alt: Optional[str] = Field(default=None, max_length=500)
    link_url: Optional[str] = Field(default=None, max_length=500)
    category: Optional[str] = Field(default=None, max_length=80)
    is_highlight: Optional[bool] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class TrustedBrandRead(TrustedBrandBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class HomepageTrustedBrand(BaseModel):
    """Brand projection consumed by the public homepage."""

    id: int
    brand_name: str
    logo_url: Optional[str] = None
    logo_url_alt: Optional[str] = None
    link_url: Optional[str] = None
    category: Optional[str] = None
    is_highlight: bool = False
    display_order: int = 0
    is_active: bool = True


class HomepageTrustedBrandsResponse(BaseModel):
    enabled: bool
    eyebrow: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    animation_enabled: bool = True
    layout_mode: str = "marquee"
    brands: List[HomepageTrustedBrand] = Field(default_factory=list)

    @field_validator("layout_mode")
    @classmethod
    def _validate_layout(cls, v: str) -> str:
        key = (v or "marquee").strip().lower()
        if key not in _ALLOWED_BRAND_LAYOUTS:
            return "marquee"
        return key


# ---------------------------------------------------------------------------
# Predefined site pages (About, Companies, Careers, Contact, News, Media)
# ---------------------------------------------------------------------------


class SitePageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    page_key: str
    hero_eyebrow: Optional[str] = None
    hero_title: Optional[str] = None
    hero_description: Optional[str] = None
    banner_image_url: Optional[str] = None
    banner_mobile_url: Optional[str] = None
    banner_video_url: Optional[str] = None
    sections: dict = Field(default_factory=dict)
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    seo_keywords: Optional[str] = None
    updated_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class SitePageUpdate(BaseModel):
    """Upsert payload — every field optional so a partial save just
    patches what the admin actually touched."""

    hero_eyebrow: Optional[str] = Field(default=None, max_length=120)
    hero_title: Optional[str] = Field(default=None, max_length=255)
    hero_description: Optional[str] = None
    banner_image_url: Optional[str] = Field(default=None, max_length=500)
    banner_mobile_url: Optional[str] = Field(default=None, max_length=500)
    banner_video_url: Optional[str] = Field(default=None, max_length=500)
    sections: Optional[dict] = None
    seo_title: Optional[str] = Field(default=None, max_length=255)
    seo_description: Optional[str] = Field(default=None, max_length=500)
    seo_keywords: Optional[str] = Field(default=None, max_length=500)

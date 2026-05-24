"""CMS models used by the Phase 5 Website Admin and consumed by the
public site from Phase 6 onward.

Tables introduced:
- hero_slides
- companies
- company_services
- leadership_messages
- news_items
- contact_messages
- newsletter_subscribers
- site_settings (single-row table)
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


# ---------------------------------------------------------------------------
# Hero slides (Home page rotating banner)
# ---------------------------------------------------------------------------


class HeroSlide(Base, TimestampMixin):
    __tablename__ = "hero_slides"

    id: Mapped[int] = mapped_column(primary_key=True)
    eyebrow: Mapped[Optional[str]] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    cta_label: Mapped[Optional[str]] = mapped_column(String(120))
    cta_href: Mapped[Optional[str]] = mapped_column(String(255))
    secondary_cta_label: Mapped[Optional[str]] = mapped_column(String(120))
    secondary_cta_href: Mapped[Optional[str]] = mapped_column(String(255))
    background_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    background_video_url: Mapped[Optional[str]] = mapped_column(String(500))
    gradient: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="from-pug-green-700 via-pug-green-500 to-pug-gold-500",
        server_default="from-pug-green-700 via-pug-green-500 to-pug-gold-500",
    )
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


# ---------------------------------------------------------------------------
# Companies (group portfolio)
# ---------------------------------------------------------------------------


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    short_description: Mapped[Optional[str]] = mapped_column(String(500))
    long_description: Mapped[Optional[str]] = mapped_column(Text)
    branches: Mapped[Optional[str]] = mapped_column(String(255))
    accent: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="from-pug-green-500 to-pug-gold-500",
        server_default="from-pug-green-500 to-pug-gold-500",
    )
    initials: Mapped[str] = mapped_column(String(8), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(40))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    address: Mapped[Optional[str]] = mapped_column(String(500))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    featured_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    cta_label: Mapped[Optional[str]] = mapped_column(String(120))
    cta_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_highlighted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    services: Mapped[List["CompanyService"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CompanyService.display_order",
    )


class CompanyService(Base):
    __tablename__ = "company_services"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    company: Mapped[Company] = relationship(back_populates="services")


# ---------------------------------------------------------------------------
# Leadership messages
# ---------------------------------------------------------------------------


class LeadershipMessage(Base, TimestampMixin):
    __tablename__ = "leadership_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    short_message: Mapped[Optional[str]] = mapped_column(String(500))
    full_message: Mapped[Optional[str]] = mapped_column(Text)
    accent: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="from-pug-green-600 to-pug-gold-500",
        server_default="from-pug-green-600 to-pug-gold-500",
    )
    initials: Mapped[str] = mapped_column(String(8), nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    signature: Mapped[Optional[str]] = mapped_column(String(120))
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


# ---------------------------------------------------------------------------
# News & events
# ---------------------------------------------------------------------------


class NewsItem(Base, TimestampMixin):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(String(500))
    body: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    author: Mapped[Optional[str]] = mapped_column(String(120))
    cover: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="from-pug-green-600 to-pug-gold-500",
        server_default="from-pug-green-600 to-pug-gold-500",
    )
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


# ---------------------------------------------------------------------------
# Contact messages
# ---------------------------------------------------------------------------


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40))
    department: Mapped[Optional[str]] = mapped_column(String(64))
    subject: Mapped[Optional[str]] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    is_replied: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    reply_body: Mapped[Optional[str]] = mapped_column(Text)
    replied_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    replied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


# ---------------------------------------------------------------------------
# Newsletter subscribers
# ---------------------------------------------------------------------------


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("email", name="uq_newsletter_email"),)


# ---------------------------------------------------------------------------
# Site settings (single-row table — id is always 1)
# ---------------------------------------------------------------------------


class SiteSetting(Base, TimestampMixin):
    __tablename__ = "site_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Paris United Group Holding",
        server_default="Paris United Group Holding",
    )
    tagline: Mapped[Optional[str]] = mapped_column(String(255))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(40))
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    contact_address: Mapped[Optional[str]] = mapped_column(String(500))
    whatsapp_number: Mapped[Optional[str]] = mapped_column(String(40))
    social_linkedin: Mapped[Optional[str]] = mapped_column(String(255))
    social_instagram: Mapped[Optional[str]] = mapped_column(String(255))
    social_facebook: Mapped[Optional[str]] = mapped_column(String(255))
    social_youtube: Mapped[Optional[str]] = mapped_column(String(255))
    seo_default_title: Mapped[Optional[str]] = mapped_column(String(255))
    seo_default_description: Mapped[Optional[str]] = mapped_column(String(500))
    seo_keywords: Mapped[Optional[str]] = mapped_column(String(500))

    # Homepage "Featured Companies" section settings.
    featured_companies_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    featured_companies_eyebrow: Mapped[Optional[str]] = mapped_column(String(120))
    featured_companies_title: Mapped[Optional[str]] = mapped_column(String(255))
    featured_companies_subtitle: Mapped[Optional[str]] = mapped_column(String(500))
    featured_companies_cta_label: Mapped[Optional[str]] = mapped_column(String(120))
    featured_companies_cta_url: Mapped[Optional[str]] = mapped_column(String(500))
    featured_companies_animation_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # Page banner imagery -------------------------------------------------
    about_banner_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    about_banner_video_url: Mapped[Optional[str]] = mapped_column(String(500))
    careers_banner_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    careers_banner_mobile_url: Mapped[Optional[str]] = mapped_column(String(500))
    contact_banner_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    contact_banner_mobile_url: Mapped[Optional[str]] = mapped_column(String(500))
    news_banner_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    news_banner_mobile_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Homepage "About" + "Founder" sections -------------------------------
    home_about_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    home_about_title: Mapped[Optional[str]] = mapped_column(String(255))
    home_about_body: Mapped[Optional[str]] = mapped_column(Text)
    home_founder_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    home_founder_name: Mapped[Optional[str]] = mapped_column(String(255))
    home_founder_role: Mapped[Optional[str]] = mapped_column(String(255))
    home_founder_message: Mapped[Optional[str]] = mapped_column(Text)

    # Trusted-brands strip -------------------------------------------------
    home_brand_logos: Mapped[Optional[str]] = mapped_column(Text)
    home_brand_strip_title: Mapped[Optional[str]] = mapped_column(String(255))


# ---------------------------------------------------------------------------
# Media gallery (Phase 5 follow-up)
# ---------------------------------------------------------------------------


MEDIA_KIND_IMAGE = "image"
MEDIA_KIND_VIDEO = "video"
MEDIA_KINDS = (MEDIA_KIND_IMAGE, MEDIA_KIND_VIDEO)


class MediaAsset(Base, TimestampMixin):
    """A single asset stored in the CMS media gallery.

    A row is created automatically when an image or video is uploaded
    through the admin upload endpoints. Beyond browsing, the row carries
    optional metadata (title, alt text, tags) so HR / website admins can
    organise files even after upload.
    """

    __tablename__ = "cms_media_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default=MEDIA_KIND_IMAGE, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[Optional[str]] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    title: Mapped[Optional[str]] = mapped_column(String(255))
    alt_text: Mapped[Optional[str]] = mapped_column(String(500))
    # Comma-separated free-form tags (kept simple — no relation table).
    tags: Mapped[Optional[str]] = mapped_column(String(500))

    uploaded_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


# ---------------------------------------------------------------------------
# Free-form CMS pages (Phase 5 follow-up)
# ---------------------------------------------------------------------------


class CMSPage(Base, TimestampMixin):
    """A free-form CMS page.

    Used for ad-hoc content like "About us", "Privacy policy", etc. that
    doesn't belong in a typed model. The ``body`` is plain text or
    markdown — the frontend renders it inside a Tailwind ``prose``
    container, so basic markdown formatting works out of the box.
    """

    __tablename__ = "cms_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(
        String(160), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    eyebrow: Mapped[Optional[str]] = mapped_column(String(120))
    summary: Mapped[Optional[str]] = mapped_column(String(500))
    body: Mapped[Optional[str]] = mapped_column(Text)
    banner_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    banner_mobile_url: Mapped[Optional[str]] = mapped_column(String(500))

    seo_title: Mapped[Optional[str]] = mapped_column(String(255))
    seo_description: Mapped[Optional[str]] = mapped_column(String(500))
    seo_keywords: Mapped[Optional[str]] = mapped_column(String(500))

    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

"""Digital Offers + Catalogue models.

Three tables:

* ``offer_campaigns`` — a marketing campaign that groups one or more
  catalogues. Has its own banner, theme color, branch targeting,
  start/end window, and feature/active toggles. The campaign slug
  becomes the public URL ``/offers/{slug}``.

* ``catalogues`` — one uploaded PDF. After upload the
  ``catalogue_processor`` service renders every page to WebP and
  populates ``page_count`` + ``catalogue_pages`` rows. The
  ``processing_status`` column tracks progress so the admin UI can
  surface "uploading", "rendering", "ready", or "failed" states
  without polling the file system.

* ``catalogue_pages`` — one row per rendered page. Stores the WebP
  full-size + thumbnail URLs and original-PDF dimensions so the
  viewer can size pages without first downloading them.

* ``catalogue_view_events`` — lightweight analytics. Anonymised
  device + session hash; no PII.

Permissions to manage these live in
``app.auth.permissions.PERM_MARKETING_*``.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
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


# Processing-status enum for ``catalogues.processing_status``.
CATALOGUE_PENDING = "pending"
CATALOGUE_PROCESSING = "processing"
CATALOGUE_READY = "ready"
CATALOGUE_FAILED = "failed"
CATALOGUE_STATUSES = (
    CATALOGUE_PENDING,
    CATALOGUE_PROCESSING,
    CATALOGUE_READY,
    CATALOGUE_FAILED,
)


class OfferCampaign(Base):
    """A marketing campaign that groups one or more catalogues.

    The public ``/offers/{slug}`` route renders the campaign banner +
    description + every active catalogue inside it. ``branch`` is a
    free-text label ("Doha", "Lusail", "All branches") because the
    site doesn't yet have a normalised branches table — when it does
    this can become an FK.
    """

    __tablename__ = "offer_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Visual chrome
    banner_image_url: Mapped[Optional[str]] = mapped_column(String(500))
    theme_color: Mapped[Optional[str]] = mapped_column(String(16))  # "#17382f"

    # Targeting
    branch: Mapped[Optional[str]] = mapped_column(String(120), index=True)

    # Active-window
    start_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, index=True)

    # Toggles + sort
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    is_killer_offer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_flash_sale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # SEO
    meta_title: Mapped[Optional[str]] = mapped_column(String(200))
    meta_description: Mapped[Optional[str]] = mapped_column(String(500))

    # Bookkeeping
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    catalogues: Mapped[List["Catalogue"]] = relationship(
        "Catalogue",
        back_populates="campaign",
        order_by="Catalogue.sort_order.asc(), Catalogue.created_at.desc()",
    )


class Catalogue(Base):
    """One uploaded PDF that the viewer renders page-by-page.

    The original PDF stays on disk as a downloadable artifact; the
    rendered WebP page images live in ``catalogue_pages``. A catalogue
    can exist without a campaign (one-off seasonal flyer) — the FK is
    SET NULL on campaign delete so editing campaigns doesn't blow
    away catalogue content.
    """

    __tablename__ = "catalogues"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("offer_campaigns.id", ondelete="SET NULL"), index=True
    )
    slug: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Source PDF
    pdf_url: Mapped[Optional[str]] = mapped_column(String(500))
    pdf_original_filename: Mapped[Optional[str]] = mapped_column(String(500))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)

    # Rendered cover (first page thumbnail) for inbox cards
    cover_image_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Brand logo stamped into the centre of the catalogue's QR code.
    # Optional — when unset, the QR endpoint falls back to a generic
    # "PUG" monogram. Each branch typically uploads its own logo
    # (Lulu, Ansar Gallery, etc.) so the share asset reads as theirs
    # rather than the parent group's.
    qr_logo_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Processing
    page_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    processing_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CATALOGUE_PENDING,
        server_default=CATALOGUE_PENDING,
        index=True,
    )
    processing_error: Mapped[Optional[str]] = mapped_column(Text)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Toggles + sort
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # SEO
    meta_title: Mapped[Optional[str]] = mapped_column(String(200))
    meta_description: Mapped[Optional[str]] = mapped_column(String(500))

    # Counters
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    download_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    campaign: Mapped[Optional["OfferCampaign"]] = relationship(
        "OfferCampaign", back_populates="catalogues"
    )
    pages: Mapped[List["CataloguePage"]] = relationship(
        "CataloguePage",
        back_populates="catalogue",
        cascade="all, delete-orphan",
        order_by="CataloguePage.page_number.asc()",
    )


class CataloguePage(Base):
    """One rendered WebP page within a catalogue."""

    __tablename__ = "catalogue_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    catalogue_id: Mapped[int] = mapped_column(
        ForeignKey("catalogues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[str] = mapped_column(String(500), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    catalogue: Mapped["Catalogue"] = relationship("Catalogue", back_populates="pages")

    __table_args__ = (
        UniqueConstraint(
            "catalogue_id", "page_number", name="uq_catalogue_pages_cat_page"
        ),
    )


class CatalogueViewEvent(Base):
    """Anonymised view-counter row used for the admin analytics card.

    No PII — only a one-way hash of the user-agent + IP so we can
    deduplicate "same visitor opened it twice in five minutes". The
    public viewer pings this endpoint on open and again on close
    with a duration.
    """

    __tablename__ = "catalogue_view_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    catalogue_id: Mapped[int] = mapped_column(
        ForeignKey("catalogues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_hash: Mapped[Optional[str]] = mapped_column(String(64))
    device: Mapped[Optional[str]] = mapped_column(String(16))  # mobile|tablet|desktop
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


__all__ = [
    "CATALOGUE_FAILED",
    "CATALOGUE_PENDING",
    "CATALOGUE_PROCESSING",
    "CATALOGUE_READY",
    "CATALOGUE_STATUSES",
    "Catalogue",
    "CataloguePage",
    "CatalogueViewEvent",
    "OfferCampaign",
]

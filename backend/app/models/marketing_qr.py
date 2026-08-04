"""Per-division (branch) QR-code models.

Powers Marketing → QR Codes. The problem this solves: a branch prints
a QR code on signage, flyers or shelf-talkers, and later wants that
code to point somewhere else (this week's catalogue, a campaign page,
a YouTube video, an Instagram post). Reprinting is not an option, so
the code itself must never change.

The mechanism:

* ``marketing_qr_codes.slug`` is written once at creation and is
  **immutable** — ``QrCodeUpdate`` has no ``slug`` field at all, so
  there is no code path that can rewrite it. The rendered QR encodes
  ``https://pug.qa/q/{slug}``, which is therefore stable for the life
  of the row.
* ``target_url`` is what admins edit. The public resolver
  (``GET /api/v1/q/{slug}``) reads it at scan time and 302s.

Three tables:

* ``marketing_divisions`` — a branch / division (Paris Hyper Market
  Al Atiyah, Al Khor, Al Wakra, Umm Salal…). This is the normalised
  branches table that ``OfferCampaign.branch``'s docstring anticipated;
  that column stays free-text for now so this migration remains
  additive.

* ``marketing_qr_codes`` — one printed code. A division may own
  several (a catalogue code on the flyer, an Instagram code by the
  till) but creating a division auto-creates its "Primary" code so
  the common one-code-per-branch case needs no extra steps.

* ``marketing_qr_scan_events`` — anonymised scan log. Mirrors
  ``CatalogueViewEvent``'s shape (one-way session hash, coarse device
  bucket, no PII) and additionally snapshots the URL that was live at
  scan time, so a scan recorded during Ramadan still reports the
  Ramadan catalogue after the target has moved on.

Permissions live in ``app.auth.permissions`` as
``PERM_MARKETING_QR_CODES_{READ,MANAGE}``.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ``marketing_qr_codes.target_kind`` — drives the icon in the admin
# list and lets scan analytics be grouped by destination type. Stored
# as a plain string (not a DB enum) so adding "whatsapp" later is a
# code change, not a migration.
QR_TARGET_CATALOGUE = "catalogue"
QR_TARGET_CAMPAIGN = "campaign"
QR_TARGET_YOUTUBE = "youtube"
QR_TARGET_INSTAGRAM = "instagram"
QR_TARGET_FACEBOOK = "facebook"
QR_TARGET_TIKTOK = "tiktok"
QR_TARGET_WEBSITE = "website"
QR_TARGET_OTHER = "other"
QR_TARGET_KINDS = (
    QR_TARGET_CATALOGUE,
    QR_TARGET_CAMPAIGN,
    QR_TARGET_YOUTUBE,
    QR_TARGET_INSTAGRAM,
    QR_TARGET_FACEBOOK,
    QR_TARGET_TIKTOK,
    QR_TARGET_WEBSITE,
    QR_TARGET_OTHER,
)


class MarketingDivision(Base):
    """One branch / division that owns its own QR codes.

    ``logo_url`` is stamped into the centre of every QR this division
    owns, so an Al Khor code carries the Al Khor mark rather than the
    parent group's. Falls back to the generic PUG monogram when unset
    (see ``services.qr_codes.build_catalogue_qr``).

    ``fallback_url`` is the safety net for printed material: when a
    QR under this division is disabled and carries no fallback of its
    own, scans land here instead of a 404. See
    ``MarketingQrCode.fallback_url``.
    """

    __tablename__ = "marketing_divisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(
        String(120), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(120))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Centre badge for this division's QR codes.
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Division-level dead-end guard — see class docstring.
    fallback_url: Mapped[Optional[str]] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    sort_order: Mapped[int] = mapped_column(
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

    qr_codes: Mapped[List["MarketingQrCode"]] = relationship(
        "MarketingQrCode",
        back_populates="division",
        cascade="all, delete-orphan",
        order_by="MarketingQrCode.sort_order.asc(), MarketingQrCode.created_at.asc()",
    )


class MarketingQrCode(Base):
    """One permanent QR code belonging to a division.

    ``slug`` is the immutable half and ``target_url`` the mutable
    half. Everything else is bookkeeping.

    ``target_url`` is nullable: a freshly created code (auto-created
    alongside its division) has nowhere to point yet. The resolver
    treats a null target exactly like a disabled row and walks the
    fallback chain, so a code can safely be printed before marketing
    has decided what it links to.
    """

    __tablename__ = "marketing_qr_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    division_id: Mapped[int] = mapped_column(
        ForeignKey("marketing_divisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Immutable once written — the printed artwork depends on it.
    slug: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    label: Mapped[str] = mapped_column(String(200), nullable=False)

    # The mutable half: where scans currently land.
    target_url: Mapped[Optional[str]] = mapped_column(Text)
    target_kind: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=QR_TARGET_OTHER,
        server_default=QR_TARGET_OTHER,
        index=True,
    )

    # Per-code dead-end guard, tried before the division's fallback.
    fallback_url: Mapped[Optional[str]] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # BigInteger for the same reason ``short_urls.click_count`` is —
    # in-store signage in front of daily footfall adds up fast, and
    # widening an INT32 column later is a locking migration.
    scan_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    last_scan_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # When the target last changed — surfaced in the admin list so an
    # operator can see at a glance which codes have gone stale.
    target_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
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

    division: Mapped["MarketingDivision"] = relationship(
        "MarketingDivision", back_populates="qr_codes"
    )


class MarketingQrScanEvent(Base):
    """One anonymised scan.

    ``resolved_url`` snapshots where the scan was sent. Without it,
    re-pointing a QR would retroactively rewrite the history of every
    scan it had already served, making "how did the Ramadan catalogue
    perform on the Al Khor code?" unanswerable.

    ``session_hash`` is a one-way SHA-256 of (client-supplied session
    marker | client IP) — same construction as
    ``CatalogueViewEvent``. The IP itself is never stored.
    """

    __tablename__ = "marketing_qr_scan_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    qr_code_id: Mapped[int] = mapped_column(
        ForeignKey("marketing_qr_codes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resolved_url: Mapped[Optional[str]] = mapped_column(Text)
    session_hash: Mapped[Optional[str]] = mapped_column(String(64))
    device: Mapped[Optional[str]] = mapped_column(String(16))  # mobile|tablet|desktop
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


__all__ = [
    "QR_TARGET_CAMPAIGN",
    "QR_TARGET_CATALOGUE",
    "QR_TARGET_FACEBOOK",
    "QR_TARGET_INSTAGRAM",
    "QR_TARGET_KINDS",
    "QR_TARGET_OTHER",
    "QR_TARGET_TIKTOK",
    "QR_TARGET_WEBSITE",
    "QR_TARGET_YOUTUBE",
    "MarketingDivision",
    "MarketingQrCode",
    "MarketingQrScanEvent",
]

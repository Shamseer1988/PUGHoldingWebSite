"""Branded short-URL model.

Powers the Marketing → Tools → URL Shortener feature. Each row maps a
short ``slug`` to a long ``target_url``; the public redirect endpoint
(``GET /api/v1/go/{slug}``) bumps ``click_count`` and 302s to the
target. Admins can disable a row (``is_active = false``) to break a
link without losing the click history, or set an ``expires_at`` so a
campaign asset stops resolving after a deadline.

Slugs are case-sensitive at the storage layer but the resolver
endpoint lower-cases the lookup to make hand-typed URLs forgiving.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ShortUrl(Base):
    """One short link.

    ``slug`` is stored lower-case (the API normalises before insert) so
    the public resolver can do a simple equality lookup. ``target_url``
    is stored as Text because campaign UTMs can push real URLs past
    the 500-char column we use elsewhere.
    """

    __tablename__ = "short_urls"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(200))

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True
    )

    # BigInteger because a single viral campaign can blow through INT32
    # in a long weekend — cheap to allocate, never have to migrate.
    click_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    last_click_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

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


__all__ = ["ShortUrl"]

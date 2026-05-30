"""Public redirect endpoint for the URL Shortener.

Route:

    GET /api/v1/go/{slug}    302 → target_url

The endpoint:

* Looks up the slug (case-insensitive — stored lower-case, lowered
  again at lookup time so hand-typed URLs are forgiving).
* Rejects rows where ``is_active = false`` OR ``expires_at`` is in
  the past with a plain 404 (we never reveal that a slug exists but
  has been disabled).
* Atomically bumps ``click_count`` + ``last_click_at`` in a single
  UPDATE so concurrent clicks can't drop counts.
* Returns 302 (Temporary Redirect). 301 caches at the browser, which
  would silently leak click traffic — every click should round-trip
  through us so the counter stays honest.

Nginx routes everything outside ``/api/`` to the Next.js frontend,
and ``next.config.mjs`` has a rewrite that proxies ``/go/{slug}`` to
this endpoint, so the public-facing URL is the bare
``https://parisunitedgroup.com/go/{slug}`` — no ``/api/v1/`` prefix
leaking through.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.models.short_url import ShortUrl
from app.schemas.short_url import SLUG_PATTERN


logger = get_logger(__name__)


router = APIRouter(prefix="/go", tags=["Public - Short URLs"])


@router.get("/{slug}")
def resolve_short_url(
    slug: str, db: Session = Depends(get_db)
) -> RedirectResponse:
    """Resolve ``slug`` → 302 to ``target_url``.

    Bumping the click counter is fire-and-forget; if the UPDATE fails
    for any reason (e.g. transient DB issue), we still serve the
    redirect — losing one count is preferable to making the public
    link 500 because the analytics layer hiccuped.
    """
    cleaned = (slug or "").strip().lower()
    # Cheap guard before hitting the DB — drop obviously bogus shapes
    # so scanner traffic doesn't churn the connection pool.
    if not SLUG_PATTERN.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found"
        )

    row = db.query(ShortUrl).filter(ShortUrl.slug == cleaned).first()
    if row is None or not row.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Short URL not found"
        )

    now = datetime.now(timezone.utc)
    expires_at = row.expires_at
    if expires_at is not None:
        # SQLite (used in tests) drops tzinfo on round-trip; coerce to
        # UTC so the comparison doesn't blow up. In Postgres this is a
        # no-op because the column is TIMESTAMP WITH TIME ZONE.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Short URL not found",
            )

    target = row.target_url

    try:
        db.execute(
            update(ShortUrl)
            .where(ShortUrl.id == row.id)
            .values(
                click_count=ShortUrl.click_count + 1,
                last_click_at=now,
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 — never let analytics break the redirect
        logger.exception("short_url click_count update failed", extra={"slug": cleaned})
        db.rollback()

    # 302 (Found) explicitly — 307 would re-issue the original method
    # on the target (POSTs would re-POST), which is the wrong shape
    # for a click-tracker.
    return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

"""Public resolver for branch QR codes.

Route:

    GET /api/v1/q/{slug}    302 → the code's current target

This is the endpoint every printed QR points at. The contract that
makes the feature work: ``slug`` is immutable (there is no admin code
path that rewrites it — see ``QrCodeUpdate``), so artwork printed once
keeps resolving forever, while ``target_url`` is free to change.

Dead-end policy — deliberately different from ``/go/{slug}``:

    A short link lives in an email; if it breaks, resend the email.
    A QR code lives on a wall, and 5,000 flyers can't be recalled. So
    a QR that is disabled, or has no target set yet, does NOT 404 —
    it walks a fallback chain:

        qr.target_url (when active)
          → qr.fallback_url
          → division.fallback_url
          → 404

    Only a slug that has never existed, or one whose row was hard-
    deleted, produces a 404.

Nginx routes everything outside ``/api/`` to Next.js, and
``next.config.mjs`` rewrites ``/q/{slug}`` to this endpoint, so the
printed URL is the bare ``https://pug.qa/q/al-atiyah``.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.models.marketing_qr import (
    MarketingDivision,
    MarketingQrCode,
    MarketingQrScanEvent,
)
from app.schemas.marketing_qr import SLUG_PATTERN


logger = get_logger(__name__)


router = APIRouter(prefix="/q", tags=["Public - Branch QR Codes"])


def _client_ip(request: Request) -> str:
    """Best-effort client IP, honouring the reverse proxy's header."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _device_bucket(user_agent: str) -> str:
    """Coarse mobile / tablet / desktop bucket from the UA string.

    Deliberately crude — this exists to answer "is our in-store
    signage mostly scanned on phones?", not to fingerprint anyone.
    Order matters: iPads report "Mobile" too, so tablets are checked
    before phones.
    """
    ua = (user_agent or "").lower()
    if not ua:
        return "unknown"
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        return "tablet"
    if "mobi" in ua or "iphone" in ua or "android" in ua:
        return "mobile"
    return "desktop"


def _branch_page_url(division: MarketingDivision) -> Optional[str]:
    """Public branch storefront URL — ``https://site/offers/{slug}``.

    Only when the branch is flagged public; a division that exists
    purely for QR routing has no page to land on.
    """
    if not division.is_public:
        return None
    from app.core.config import get_settings

    base = (get_settings().public_site_url or "").rstrip("/")
    if not base:
        return None
    return f"{base}/offers/{division.slug}"


def _resolve_destination(
    db: Session, row: MarketingQrCode
) -> Optional[str]:
    """Walk the fallback chain described in the module docstring.

    Returns ``None`` only when nothing anywhere is set, which is the
    one case that 404s. An inactive division disables its codes too —
    closing a branch shouldn't require disabling each of its codes by
    hand — but the division's own fallback still applies, so scans at
    a closed branch can be sent to a "this store has moved" page.

    The branch storefront sits at the end of the chain as an automatic
    last resort: a code with no link set lands the shopper on that
    branch's own offers page rather than a 404. That page is always
    relevant to whoever scanned it — they're standing in the store —
    so it's a better default than anything an admin would have to
    remember to configure.
    """
    division = db.get(MarketingDivision, row.division_id)
    division_active = division.is_active if division is not None else False

    if row.is_active and division_active and row.target_url:
        return row.target_url
    if row.fallback_url:
        return row.fallback_url
    if division is not None:
        if division.fallback_url:
            return division.fallback_url
        branch_page = _branch_page_url(division)
        if branch_page:
            return branch_page
    return None


@router.get("/{slug}")
def resolve_qr_code(
    slug: str, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    """Resolve ``slug`` → 302 to the code's current destination.

    Scan logging is fire-and-forget: if the counter UPDATE or the
    event INSERT fails, the shopper still gets their redirect. A
    dropped analytics row is a far cheaper failure than a QR code
    that appears broken to a customer standing in the store.
    """
    cleaned = (slug or "").strip().lower()
    # Cheap shape check before touching the DB so scanner/bot traffic
    # doesn't churn the connection pool.
    if not SLUG_PATTERN.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="QR code not found"
        )

    row = (
        db.query(MarketingQrCode).filter(MarketingQrCode.slug == cleaned).first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="QR code not found"
        )

    destination = _resolve_destination(db, row)
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="QR code not found"
        )

    now = datetime.now(timezone.utc)
    try:
        db.execute(
            update(MarketingQrCode)
            .where(MarketingQrCode.id == row.id)
            .values(
                scan_count=MarketingQrCode.scan_count + 1,
                last_scan_at=now,
            )
        )
        # Hash (session marker | client IP) one-way so repeat scans
        # from one device can be collapsed later without ever storing
        # the IP. Same construction as ``CatalogueViewEvent``.
        raw = f"{request.headers.get('user-agent', '')}|{_client_ip(request)}"
        db.add(
            MarketingQrScanEvent(
                qr_code_id=row.id,
                resolved_url=destination,
                session_hash=hashlib.sha256(raw.encode()).hexdigest(),
                device=_device_bucket(request.headers.get("user-agent", "")),
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 — never let analytics break the scan
        logger.exception("qr scan logging failed", extra={"slug": cleaned})
        db.rollback()

    # 302, not 301: a permanent redirect would be cached by the phone's
    # browser, so a later target change wouldn't take effect on devices
    # that had already scanned — exactly the behaviour this feature
    # exists to avoid.
    return RedirectResponse(url=destination, status_code=status.HTTP_302_FOUND)

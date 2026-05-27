"""Public Digital Offers & Catalogue endpoints.

GET /api/v1/offers                        landing list — featured / killer /
                                          flash / all + branch facets
GET /api/v1/offers/{slug}                 single campaign + its catalogues
GET /api/v1/offers/catalogues/{slug}      single catalogue with every page
POST /api/v1/offers/catalogues/{id}/view  analytics beacon (anonymous)
GET /api/v1/offers/catalogues/{id}/download
                                          serve the original PDF + count
                                          the download

The list endpoint is cacheable (the public-cache-headers middleware
already adds appropriate ``Cache-Control`` to public GETs).
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.models.marketing import (
    CATALOGUE_READY,
    Catalogue,
    CataloguePage,
    CatalogueViewEvent,
    OfferCampaign,
)
from app.schemas.marketing import (
    CampaignPublicDetail,
    CatalogueDetail,
    CatalogueViewLog,
    OffersIndex,
    OffersIndexCampaign,
)


router = APIRouter(prefix="/offers", tags=["Public - Offers & Catalogues"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _active_campaign_clause():
    """Filter for "campaign should currently appear in public listings"
    — active flag set and (no end_date OR end_date in the future)."""
    today = date.today()
    return and_(
        OfferCampaign.is_active.is_(True),
        or_(OfferCampaign.end_date.is_(None), OfferCampaign.end_date >= today),
        or_(
            OfferCampaign.start_date.is_(None),
            OfferCampaign.start_date <= today,
        ),
    )


def _ready_catalogue_count_lookup(
    db: Session, campaign_ids: list[int]
) -> dict[int, int]:
    """Return ``{campaign_id: count of ready+active catalogues}``."""
    if not campaign_ids:
        return {}
    rows = db.execute(
        select(Catalogue.campaign_id, func.count(Catalogue.id))
        .where(
            Catalogue.campaign_id.in_(campaign_ids),
            Catalogue.is_active.is_(True),
            Catalogue.processing_status == CATALOGUE_READY,
        )
        .group_by(Catalogue.campaign_id)
    ).all()
    return {cid: int(n) for cid, n in rows}


def _cover_image_lookup(
    db: Session, campaign_ids: list[int]
) -> dict[int, Optional[str]]:
    """Return ``{campaign_id: first-catalogue cover URL}``."""
    if not campaign_ids:
        return {}
    out: dict[int, Optional[str]] = {cid: None for cid in campaign_ids}
    rows = db.execute(
        select(
            Catalogue.campaign_id,
            Catalogue.cover_image_url,
            Catalogue.sort_order,
            Catalogue.created_at,
        )
        .where(
            Catalogue.campaign_id.in_(campaign_ids),
            Catalogue.is_active.is_(True),
            Catalogue.processing_status == CATALOGUE_READY,
            Catalogue.cover_image_url.is_not(None),
        )
        .order_by(Catalogue.sort_order.asc(), Catalogue.created_at.desc())
    ).all()
    for cid, cover, _so, _ca in rows:
        # First row wins per campaign (we iterate by sort+date).
        if out.get(cid) is None:
            out[cid] = cover
    return out


def _to_index_card(
    c: OfferCampaign, counts: dict[int, int], covers: dict[int, Optional[str]]
) -> OffersIndexCampaign:
    return OffersIndexCampaign(
        slug=c.slug,
        title=c.title,
        description=c.description,
        banner_image_url=c.banner_image_url,
        theme_color=c.theme_color,
        branch=c.branch,
        start_date=c.start_date,
        end_date=c.end_date,
        is_featured=c.is_featured,
        is_killer_offer=c.is_killer_offer,
        is_flash_sale=c.is_flash_sale,
        catalogue_count=counts.get(c.id, 0),
        cover_image_url=covers.get(c.id),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=OffersIndex)
def list_offers(
    db: Session = Depends(get_db),
    branch: Optional[str] = Query(default=None, max_length=120),
    q: Optional[str] = Query(default=None, max_length=200),
) -> OffersIndex:
    """Landing payload for the public ``/offers`` page.

    Returns four bucketed lists (featured, killer, flash, all) plus
    the distinct branch list for the filter chips. Inactive /
    expired campaigns are excluded.
    """
    stmt = (
        select(OfferCampaign)
        .where(_active_campaign_clause())
        .order_by(
            OfferCampaign.sort_order.asc(),
            desc(OfferCampaign.created_at),
        )
    )
    if branch:
        stmt = stmt.where(OfferCampaign.branch == branch)
    if q:
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(OfferCampaign.title).like(needle),
                func.lower(OfferCampaign.description).like(needle),
            )
        )

    campaigns = db.execute(stmt).scalars().all()
    ids = [c.id for c in campaigns]
    counts = _ready_catalogue_count_lookup(db, ids)
    covers = _cover_image_lookup(db, ids)

    cards = [_to_index_card(c, counts, covers) for c in campaigns]
    # Only surface campaigns that have at least one ready catalogue —
    # an empty campaign is a draft, not something the public should
    # land on. Admins can flip is_active=false to fully hide instead.
    cards = [c for c in cards if c.catalogue_count > 0]

    featured = [c for c in cards if c.is_featured]
    killer = [c for c in cards if c.is_killer_offer]
    flash = [c for c in cards if c.is_flash_sale]

    # Branch facet — pull every distinct branch from the surfaced
    # set so the filter only shows options that actually have content.
    branches = sorted({c.branch for c in cards if c.branch})

    return OffersIndex(
        featured=featured[:8],
        killer_offers=killer[:8],
        flash_sales=flash[:8],
        all_campaigns=cards,
        branches=branches,
    )


@router.get("/{slug}", response_model=CampaignPublicDetail)
def get_campaign_detail(
    slug: str,
    db: Session = Depends(get_db),
) -> CampaignPublicDetail:
    """Single campaign with every active+ready catalogue inside it."""
    campaign = db.execute(
        select(OfferCampaign).where(
            OfferCampaign.slug == slug.lower().strip(),
            OfferCampaign.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    catalogues = db.execute(
        select(Catalogue)
        .where(
            Catalogue.campaign_id == campaign.id,
            Catalogue.is_active.is_(True),
            Catalogue.processing_status == CATALOGUE_READY,
        )
        .order_by(Catalogue.sort_order.asc(), Catalogue.created_at.desc())
    ).scalars().all()

    # Increment view counter best-effort. No commit — the get_db
    # generator's autoflush + commit-on-success handles it.
    campaign.view_count += 1
    db.commit()
    db.refresh(campaign)

    return CampaignPublicDetail(
        slug=campaign.slug,
        title=campaign.title,
        description=campaign.description,
        banner_image_url=campaign.banner_image_url,
        theme_color=campaign.theme_color,
        branch=campaign.branch,
        start_date=campaign.start_date,
        end_date=campaign.end_date,
        meta_title=campaign.meta_title,
        meta_description=campaign.meta_description,
        catalogues=[_serialize_catalogue(c) for c in catalogues],
    )


@router.get("/catalogues/{slug}", response_model=CatalogueDetail)
def get_catalogue_detail(
    slug: str,
    db: Session = Depends(get_db),
) -> CatalogueDetail:
    """Single catalogue with every rendered page — the viewer endpoint."""
    catalogue = db.execute(
        select(Catalogue)
        .options(selectinload(Catalogue.pages))
        .where(
            Catalogue.slug == slug.lower().strip(),
            Catalogue.is_active.is_(True),
            Catalogue.processing_status == CATALOGUE_READY,
        )
    ).scalar_one_or_none()
    if catalogue is None:
        raise HTTPException(status_code=404, detail="Catalogue not found")
    return CatalogueDetail.model_validate(catalogue)


@router.post("/catalogues/{catalogue_id}/view")
def log_catalogue_view(
    catalogue_id: int,
    payload: CatalogueViewLog,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Anonymous analytics beacon. Called by the viewer when a user
    opens a catalogue (and optionally again on close with duration)."""
    catalogue = db.get(Catalogue, catalogue_id)
    if catalogue is None or not catalogue.is_active:
        raise HTTPException(status_code=404, detail="Catalogue not found")

    # Build a hash from the supplied session_hash + the client IP so
    # we can collapse duplicate "I opened it twice" hits without
    # storing the IP itself.
    raw = (payload.session_hash or "") + "|" + _client_ip(request)
    hashed = hashlib.sha256(raw.encode()).hexdigest()

    db.add(
        CatalogueViewEvent(
            catalogue_id=catalogue.id,
            session_hash=hashed,
            device=payload.device,
            duration_seconds=payload.duration_seconds,
        )
    )
    catalogue.view_count += 1
    db.commit()
    return {"ok": True}


@router.get("/catalogues/{catalogue_id}/download")
def download_catalogue_pdf(
    catalogue_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Stream the original PDF. Increments download_count."""
    catalogue = db.get(Catalogue, catalogue_id)
    if catalogue is None or not catalogue.is_active:
        raise HTTPException(status_code=404, detail="Catalogue not found")
    if not catalogue.pdf_url:
        raise HTTPException(
            status_code=404, detail="PDF not available for this catalogue."
        )

    # The pdf_url is a public URL like /api/v1/uploads/catalogues/<id>/source.pdf
    # — resolve it back to the on-disk path. The uploads mount is rooted
    # at settings.upload_dir.
    settings = get_settings()
    relative = catalogue.pdf_url.split("/api/v1/uploads/", 1)[-1]
    path = Path(settings.upload_dir) / relative
    if not path.exists():
        raise HTTPException(
            status_code=404, detail="PDF file missing on disk."
        )

    catalogue.download_count += 1
    db.commit()

    filename = catalogue.pdf_original_filename or f"{catalogue.slug}.pdf"
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=filename,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_catalogue(c: Catalogue):
    from app.schemas.marketing import CatalogueRead

    return CatalogueRead.model_validate(c)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        ip = fwd.split(",")[0].strip()
        if ip:
            return ip
    if request.client is None:
        return "unknown"
    return request.client.host or "unknown"


__all__ = ["router"]

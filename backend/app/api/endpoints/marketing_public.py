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
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.marketing_qr import MarketingDivision
from app.models.marketing import (
    CATALOGUE_READY,
    Catalogue,
    CataloguePage,
    CatalogueViewEvent,
    OfferCampaign,
)
from app.schemas.marketing import (
    BranchPage,
    BranchSocialLinks,
    BranchSummary,
    CampaignPublicDetail,
    CatalogueDetail,
    CatalogueViewLog,
    OffersIndex,
    OffersIndexCampaign,
    OffersIndexCatalogue,
)
from app.services.catalogue_processor import source_pdf_key
from app.services.storage import get_storage


router = APIRouter(prefix="/offers", tags=["Public - Offers & Catalogues"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _publishable_campaign_clause():
    """Filter for "campaign is publicly visible on the landing".

    Includes EXPIRED campaigns intentionally — the landing renders
    them with an "EXPIRED" badge so customers can still see past
    promotions (and old share links don't 404). We only exclude:

      * ``is_active = false`` — explicit admin hide.
      * ``start_date > today`` — campaigns scheduled but not yet
        live shouldn't leak before their reveal.

    Use :func:`_is_expired` to compute the badge state per row.
    """
    today = date.today()
    return and_(
        OfferCampaign.is_active.is_(True),
        or_(
            OfferCampaign.start_date.is_(None),
            OfferCampaign.start_date <= today,
        ),
    )


def _is_expired(campaign: OfferCampaign) -> bool:
    """``True`` when the campaign's end_date is strictly in the past."""
    return campaign.end_date is not None and campaign.end_date < date.today()


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
        is_expired=_is_expired(c),
        catalogue_count=counts.get(c.id, 0),
        cover_image_url=covers.get(c.id),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------



def _catalogue_card(c: Catalogue) -> OffersIndexCatalogue:
    """Map a Catalogue row to its public tile."""
    return OffersIndexCatalogue(
        slug=c.slug,
        title=c.title,
        description=c.description,
        cover_image_url=c.cover_image_url,
        page_count=c.page_count,
        branch_name=c.division_name,
        is_featured=c.is_featured,
        created_at=c.created_at,
    )


def _branch_options(db: Session) -> list[BranchSummary]:
    """Every publicly-visible branch, for the picker.

    Sourced from the divisions table rather than distinct campaign
    labels: the picker should list branches that *exist*, so a shopper
    can reach a branch page even in a week when that branch happens to
    have no campaign of its own.
    """
    rows = (
        db.execute(
            select(MarketingDivision)
            .where(
                MarketingDivision.is_active.is_(True),
                MarketingDivision.is_public.is_(True),
            )
            .order_by(
                MarketingDivision.sort_order.asc(),
                MarketingDivision.name.asc(),
            )
        )
        .scalars()
        .all()
    )
    return [
        BranchSummary(slug=d.slug, name=d.name, city=d.city) for d in rows
    ]


def _visible_to_branch(division_id: Optional[int]):
    """Rows targeted at ``division_id`` OR at all branches.

    The OR is the important half: a group-wide campaign belongs on
    every branch page. Filtering strictly by branch would hide the
    main weekly flyer from every store.
    """
    return or_(
        OfferCampaign.division_id == division_id,
        OfferCampaign.division_id.is_(None),
    )


def _catalogue_visible_to_branch(division_id: Optional[int]):
    """Catalogue equivalent of :func:`_visible_to_branch`."""
    return or_(
        Catalogue.division_id == division_id,
        Catalogue.division_id.is_(None),
    )


@router.get("", response_model=OffersIndex)
def list_offers(
    db: Session = Depends(get_db),
    branch: Optional[str] = Query(
        default=None,
        max_length=200,
        description="Branch slug (preferred) or legacy free-text branch label.",
    ),
    q: Optional[str] = Query(default=None, max_length=200),
    killer: bool = Query(default=False, description="Only killer offers"),
    featured: bool = Query(default=False, description="Only featured"),
    flash: bool = Query(default=False, description="Only flash sales"),
    include_expired: bool = Query(
        default=True, description="Set false to hide finished campaigns"
    ),
) -> OffersIndex:
    """Landing payload for the public ``/offers`` page.

    Returns the bucketed carousels (featured / killer / flash), the
    full campaign list, every ready catalogue, and the branch picker
    options.

    Expired campaigns are included by default and badged client-side —
    old share links shouldn't 404, and last month's flyer is still
    interesting. ``include_expired=false`` powers the "Active only"
    filter chip.
    """
    division = _lookup_branch(db, branch)

    stmt = (
        select(OfferCampaign)
        .where(_publishable_campaign_clause())
        .order_by(
            OfferCampaign.sort_order.asc(),
            desc(OfferCampaign.created_at),
        )
    )
    if branch:
        if division is not None:
            # Structured match, plus all-branch campaigns, plus the
            # legacy text label so pre-migration rows still filter.
            stmt = stmt.where(
                or_(
                    _visible_to_branch(division.id),
                    func.lower(OfferCampaign.branch) == division.name.lower(),
                )
            )
        else:
            stmt = stmt.where(OfferCampaign.branch == branch)
    if q:
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(OfferCampaign.title).like(needle),
                func.lower(OfferCampaign.description).like(needle),
            )
        )
    if killer:
        stmt = stmt.where(OfferCampaign.is_killer_offer.is_(True))
    if featured:
        stmt = stmt.where(OfferCampaign.is_featured.is_(True))
    if flash:
        stmt = stmt.where(OfferCampaign.is_flash_sale.is_(True))

    campaigns = db.execute(stmt).scalars().unique().all()
    ids = [c.id for c in campaigns]
    counts = _ready_catalogue_count_lookup(db, ids)
    covers = _cover_image_lookup(db, ids)

    cards = [_to_index_card(c, counts, covers) for c in campaigns]
    # A campaign with no rendered catalogue is a draft, not something
    # to land a customer on.
    cards = [c for c in cards if c.catalogue_count > 0]
    if not include_expired:
        cards = [c for c in cards if not c.is_expired]

    # Active first, expired at the bottom — keeps the first fold on
    # what's live without losing the archive.
    cards.sort(key=lambda c: (c.is_expired, 0))

    # Highlighted carousels are for CURRENT promos only; an expired
    # flash sale would mislead.
    featured_cards = [c for c in cards if c.is_featured and not c.is_expired]
    killer_cards = [c for c in cards if c.is_killer_offer and not c.is_expired]
    flash_cards = [c for c in cards if c.is_flash_sale and not c.is_expired]

    # Every active+ready catalogue, independent of campaign attachment.
    # This is what guarantees the landing has content whenever a flyer
    # has rendered — a catalogue with no campaign, or whose campaign
    # has the wrong date window, still reaches the customer.
    catalogue_stmt = (
        select(Catalogue)
        .where(
            Catalogue.is_active.is_(True),
            Catalogue.processing_status == CATALOGUE_READY,
        )
        .order_by(
            Catalogue.is_featured.desc(),
            Catalogue.sort_order.asc(),
            desc(Catalogue.created_at),
        )
        .limit(48)
    )
    if branch and division is not None:
        catalogue_stmt = catalogue_stmt.where(
            _catalogue_visible_to_branch(division.id)
        )
    if q:
        needle = f"%{q.strip().lower()}%"
        catalogue_stmt = catalogue_stmt.where(
            or_(
                func.lower(Catalogue.title).like(needle),
                func.lower(Catalogue.description).like(needle),
            )
        )
    all_catalogues = [
        _catalogue_card(c) for c in db.execute(catalogue_stmt).scalars().unique()
    ]

    return OffersIndex(
        featured=featured_cards[:8],
        killer_offers=killer_cards[:8],
        flash_sales=flash_cards[:8],
        all_campaigns=cards,
        all_catalogues=all_catalogues,
        branches=_branch_options(db),
    )


def _lookup_branch(
    db: Session, branch: Optional[str]
) -> Optional[MarketingDivision]:
    """Resolve a branch filter value to a division row, if it is one.

    Accepts the slug (what the picker sends) and falls back to a
    case-insensitive name match so a hand-typed or legacy label still
    resolves. ``None`` when the value matches no branch — the caller
    then treats it as a legacy free-text filter.
    """
    if not branch:
        return None
    cleaned = branch.strip().lower()
    return db.execute(
        select(MarketingDivision).where(
            or_(
                MarketingDivision.slug == cleaned,
                func.lower(MarketingDivision.name) == cleaned,
            )
        )
    ).scalars().first()


@router.get("/branches", response_model=list[BranchSummary])
def list_branches(db: Session = Depends(get_db)) -> list[BranchSummary]:
    """Public branch picker options.

    Declared before ``/{slug}`` so the literal path wins the route
    match — otherwise "branches" would be read as a campaign slug.
    """
    return _branch_options(db)


@router.get("/branch/{slug}", response_model=BranchPage)
def get_branch_page(slug: str, db: Session = Depends(get_db)) -> BranchPage:
    """Storefront payload for one branch.

    This is where a QR code with no target sends its scans, so it must
    always be worth landing on: it lists the branch's own campaigns
    AND the group-wide ones, so the page has content even for a branch
    that runs no exclusive promotions.
    """
    cleaned = (slug or "").strip().lower()
    division = db.execute(
        select(MarketingDivision).where(MarketingDivision.slug == cleaned)
    ).scalars().first()
    if division is None or not division.is_active or not division.is_public:
        raise HTTPException(status_code=404, detail="Branch not found")

    campaign_rows = (
        db.execute(
            select(OfferCampaign)
            .where(
                _publishable_campaign_clause(),
                or_(
                    _visible_to_branch(division.id),
                    func.lower(OfferCampaign.branch) == division.name.lower(),
                ),
            )
            .order_by(
                OfferCampaign.sort_order.asc(), desc(OfferCampaign.created_at)
            )
        )
        .scalars()
        .unique()
        .all()
    )
    ids = [c.id for c in campaign_rows]
    counts = _ready_catalogue_count_lookup(db, ids)
    covers = _cover_image_lookup(db, ids)
    cards = [_to_index_card(c, counts, covers) for c in campaign_rows]
    cards = [c for c in cards if c.catalogue_count > 0]
    cards.sort(key=lambda c: (c.is_expired, 0))

    catalogues = (
        db.execute(
            select(Catalogue)
            .where(
                Catalogue.is_active.is_(True),
                Catalogue.processing_status == CATALOGUE_READY,
                _catalogue_visible_to_branch(division.id),
            )
            .order_by(
                Catalogue.is_featured.desc(),
                Catalogue.sort_order.asc(),
                desc(Catalogue.created_at),
            )
            .limit(48)
        )
        .scalars()
        .unique()
        .all()
    )

    others = [b for b in _branch_options(db) if b.slug != division.slug]

    return BranchPage(
        slug=division.slug,
        name=division.name,
        city=division.city,
        description=division.description,
        logo_url=division.logo_url,
        hero_image_url=division.hero_image_url,
        address=division.address,
        phone=division.phone,
        email=division.email,
        whatsapp=division.whatsapp,
        opening_hours=division.opening_hours,
        maps_url=division.maps_url,
        social=BranchSocialLinks(
            facebook=division.facebook_url,
            instagram=division.instagram_url,
            tiktok=division.tiktok_url,
            youtube=division.youtube_url,
            snapchat=division.snapchat_url,
            x=division.x_url,
        ),
        campaigns=cards,
        catalogues=[_catalogue_card(c) for c in catalogues],
        other_branches=others,
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
        is_expired=_is_expired(campaign),
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
) -> Response:
    """Serve the original PDF and increment ``download_count``.

    Fetches the bytes via the storage backend under the same
    deterministic key the catalogue processor wrote to, so the
    endpoint works against R2 just as well as a local-disk install.
    Pre-R2 this did ``catalogue.pdf_url.split('/api/v1/uploads/')``
    + ``Path.read_bytes`` — which 404s as soon as ``pdf_url`` is an
    R2 ``https://…`` URL.
    """
    catalogue = db.get(Catalogue, catalogue_id)
    if catalogue is None or not catalogue.is_active:
        raise HTTPException(status_code=404, detail="Catalogue not found")
    if not catalogue.pdf_url:
        raise HTTPException(
            status_code=404, detail="PDF not available for this catalogue."
        )

    try:
        pdf_bytes = get_storage().download_sync(source_pdf_key(catalogue.id))
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="PDF file missing from storage."
        ) from exc

    catalogue.download_count += 1
    db.commit()

    # ``pdf_original_filename`` is the upload-time name, which the
    # admin chose; fall back to ``{slug}.pdf`` so the user-facing
    # save-as dialog always has something meaningful.
    raw_filename = catalogue.pdf_original_filename or f"{catalogue.slug}.pdf"
    # Strip control characters + double-quotes that would break the
    # ``Content-Disposition`` quoted-string. Replace anything outside
    # ASCII with an underscore so we never emit an invalid header
    # value — browsers tolerate the substitution and the user can
    # rename on save.
    safe_filename = "".join(
        ch if 32 <= ord(ch) < 127 and ch != '"' else "_"
        for ch in raw_filename
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
        },
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

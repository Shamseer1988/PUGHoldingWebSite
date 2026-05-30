"""Admin Digital Offers & Catalogue endpoints.

Routes (all prefixed ``/admin/marketing``):

  Campaigns
    GET    /campaigns                    list (filter: active/branch/search)
    POST   /campaigns                    create
    GET    /campaigns/{id}               detail
    PATCH  /campaigns/{id}               edit
    DELETE /campaigns/{id}               delete (sets catalogue.campaign_id=NULL)

  Catalogues
    GET    /catalogues                   list (filter: campaign/status/search)
    POST   /catalogues                   multipart upload — PDF + metadata,
                                          synchronously renders to WebP
    GET    /catalogues/{id}              detail (with all rendered pages)
    PATCH  /catalogues/{id}              edit metadata
    DELETE /catalogues/{id}              delete row + rendered files
    POST   /catalogues/{id}/reprocess    rerun PDF -> WebP rendering
    GET    /catalogues/{id}/analytics    view + device aggregates

All routes require ``require_website_admin`` (the existing
website-scope guard) AND one of the marketing permission keys.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

# Phase A-4: this file is one of the demonstration sites for the new
# structured-logging helper. Replace ``logging.getLogger`` with
# ``get_logger`` so every log line the marketing surface emits carries
# the structured fields the rest of the stack already does.
from app.core.logging_config import get_logger

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import (
    get_request_context,
    require_any_permission,
    require_permission,
    require_website_admin,
)
from app.auth.permissions import (
    PERM_MARKETING_CAMPAIGNS_MANAGE,
    PERM_MARKETING_CAMPAIGNS_READ,
    PERM_MARKETING_CATALOGUES_MANAGE,
    PERM_MARKETING_CATALOGUES_READ,
    PERM_MARKETING_DASHBOARD_VIEW,
)
from app.core.database import get_db
from app.models.auth import User
from app.models.marketing import (
    CATALOGUE_PENDING,
    Catalogue,
    CataloguePage,
    CatalogueViewEvent,
    OfferCampaign,
)
from app.schemas.marketing import (
    CampaignCreate,
    CampaignRead,
    CampaignUpdate,
    CatalogueAnalytics,
    CatalogueDetail,
    CatalogueRead,
    CatalogueUpdate,
    MarketingDashboard,
    MarketingDashboardKpis,
    MarketingDashboardRecentView,
    MarketingDashboardSeriesPoint,
    MarketingDashboardTopCampaign,
    MarketingDashboardTopCatalogue,
    ReconcileCountersResult,
)
# Dependency aliases — GETs accept either the manage key or the
# narrower read key so a "Marketing Viewer" role can browse without
# being granted write access. The dashboard accepts any marketing
# key (including dashboard:view) because analytics is the safest
# surface to expose to non-CRUD analysts.
_CAMPAIGNS_VIEWER = require_any_permission(
    PERM_MARKETING_CAMPAIGNS_READ, PERM_MARKETING_CAMPAIGNS_MANAGE
)
_CATALOGUES_VIEWER = require_any_permission(
    PERM_MARKETING_CATALOGUES_READ, PERM_MARKETING_CATALOGUES_MANAGE
)
_DASHBOARD_VIEWER = require_any_permission(
    PERM_MARKETING_DASHBOARD_VIEW,
    PERM_MARKETING_CAMPAIGNS_READ,
    PERM_MARKETING_CAMPAIGNS_MANAGE,
    PERM_MARKETING_CATALOGUES_READ,
    PERM_MARKETING_CATALOGUES_MANAGE,
)


from app.services.audit_log import record_audit
from app.services.catalogue_processor import (
    CatalogueProcessingError,
    delete_catalogue_assets,
    process_catalogue,
    source_pdf_key,
)


logger = get_logger(__name__)


router = APIRouter(
    prefix="/admin/marketing",
    tags=["Admin - Marketing"],
    dependencies=[Depends(require_website_admin)],
)


# Upload cap on the PDF itself. Hypermarket flyers are typically
# under 30 MB; bigger files are usually high-DPI master files that
# shouldn't be uploaded to the public viewer.
MAX_PDF_BYTES = 50 * 1024 * 1024  # 50 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _audit(
    db: Session,
    actor: User,
    request: Request,
    *,
    action: str,
    target_type: str,
    target_id: int,
    details: Optional[dict] = None,
) -> None:
    ctx = get_request_context(request)
    record_audit(
        db,
        action=action,
        actor_id=actor.id,
        actor_email=actor.email,
        scope="website",
        target_type=target_type,
        target_id=str(target_id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details=details,
        commit=False,
    )


def _campaign_or_404(db: Session, campaign_id: int) -> OfferCampaign:
    row = db.get(OfferCampaign, campaign_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return row


def _catalogue_or_404(db: Session, catalogue_id: int) -> Catalogue:
    row = db.get(Catalogue, catalogue_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Catalogue not found")
    return row


def _catalogue_counts(db: Session, campaign_ids: list[int]) -> dict[int, int]:
    if not campaign_ids:
        return {}
    rows = db.execute(
        select(Catalogue.campaign_id, func.count(Catalogue.id))
        .where(Catalogue.campaign_id.in_(campaign_ids))
        .group_by(Catalogue.campaign_id)
    ).all()
    return {cid: int(n) for cid, n in rows}


def _serialize_campaign(
    c: OfferCampaign, *, catalogue_counts: Optional[dict[int, int]] = None
) -> CampaignRead:
    return CampaignRead(
        id=c.id,
        slug=c.slug,
        title=c.title,
        description=c.description,
        banner_image_url=c.banner_image_url,
        theme_color=c.theme_color,
        branch=c.branch,
        start_date=c.start_date,
        end_date=c.end_date,
        is_active=c.is_active,
        is_featured=c.is_featured,
        is_killer_offer=c.is_killer_offer,
        is_flash_sale=c.is_flash_sale,
        sort_order=c.sort_order,
        meta_title=c.meta_title,
        meta_description=c.meta_description,
        view_count=c.view_count,
        catalogue_count=(catalogue_counts or {}).get(c.id, 0),
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


# ---------------------------------------------------------------------------
# Campaign CRUD
# ---------------------------------------------------------------------------


@router.get("/campaigns", response_model=List[CampaignRead])
def list_campaigns(
    db: Session = Depends(get_db),
    actor: User = Depends(_CAMPAIGNS_VIEWER),
    include_inactive: bool = Query(default=True),
    branch: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=200),
) -> list[CampaignRead]:
    stmt = select(OfferCampaign).order_by(
        OfferCampaign.sort_order.asc(), desc(OfferCampaign.created_at)
    )
    if not include_inactive:
        stmt = stmt.where(OfferCampaign.is_active.is_(True))
    if branch:
        stmt = stmt.where(OfferCampaign.branch == branch)
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(OfferCampaign.title).like(needle),
                func.lower(OfferCampaign.slug).like(needle),
                func.lower(OfferCampaign.description).like(needle),
            )
        )
    rows = db.execute(stmt).scalars().all()
    counts = _catalogue_counts(db, [r.id for r in rows])
    return [_serialize_campaign(r, catalogue_counts=counts) for r in rows]


@router.post(
    "/campaigns",
    response_model=CampaignRead,
    status_code=status.HTTP_201_CREATED,
)
def create_campaign(
    payload: CampaignCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_MARKETING_CAMPAIGNS_MANAGE)),
) -> CampaignRead:
    if db.execute(
        select(OfferCampaign).where(OfferCampaign.slug == payload.slug)
    ).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail=f"A campaign with slug '{payload.slug}' already exists."
        )

    row = OfferCampaign(
        slug=payload.slug,
        title=payload.title.strip(),
        description=(payload.description or "").strip() or None,
        banner_image_url=payload.banner_image_url or None,
        theme_color=payload.theme_color,
        branch=(payload.branch or "").strip() or None,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=payload.is_active,
        is_featured=payload.is_featured,
        is_killer_offer=payload.is_killer_offer,
        is_flash_sale=payload.is_flash_sale,
        sort_order=payload.sort_order,
        meta_title=payload.meta_title,
        meta_description=payload.meta_description,
        created_by_id=actor.id,
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        actor,
        request,
        action="marketing.campaign.create",
        target_type="offer_campaign",
        target_id=row.id,
        details={"slug": row.slug, "title": row.title},
    )
    db.commit()
    db.refresh(row)
    return _serialize_campaign(row)


@router.get("/campaigns/{campaign_id}", response_model=CampaignRead)
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(_CAMPAIGNS_VIEWER),
) -> CampaignRead:
    row = _campaign_or_404(db, campaign_id)
    counts = _catalogue_counts(db, [row.id])
    return _serialize_campaign(row, catalogue_counts=counts)


@router.patch("/campaigns/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_MARKETING_CAMPAIGNS_MANAGE)),
) -> CampaignRead:
    row = _campaign_or_404(db, campaign_id)
    updates = payload.model_dump(exclude_unset=True)

    # Slug uniqueness — only if changing.
    if "slug" in updates and updates["slug"] and updates["slug"] != row.slug:
        conflict = db.execute(
            select(OfferCampaign).where(
                OfferCampaign.slug == updates["slug"],
                OfferCampaign.id != row.id,
            )
        ).scalar_one_or_none()
        if conflict is not None:
            raise HTTPException(status_code=409, detail="Slug already in use.")

    changed: list[str] = []
    for key, value in updates.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed.append(key)
    if changed:
        _audit(
            db,
            actor,
            request,
            action="marketing.campaign.update",
            target_type="offer_campaign",
            target_id=row.id,
            details={"fields": changed},
        )
    db.commit()
    db.refresh(row)
    counts = _catalogue_counts(db, [row.id])
    return _serialize_campaign(row, catalogue_counts=counts)


@router.delete(
    "/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_campaign(
    campaign_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_MARKETING_CAMPAIGNS_MANAGE)),
) -> Response:
    row = _campaign_or_404(db, campaign_id)
    _audit(
        db,
        actor,
        request,
        action="marketing.campaign.delete",
        target_type="offer_campaign",
        target_id=row.id,
        details={"slug": row.slug},
    )
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Catalogue CRUD + upload
# ---------------------------------------------------------------------------


@router.get("/catalogues", response_model=List[CatalogueRead])
def list_catalogues(
    db: Session = Depends(get_db),
    actor: User = Depends(_CATALOGUES_VIEWER),
    campaign_id: Optional[int] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None, max_length=200),
    include_inactive: bool = Query(default=True),
) -> list[CatalogueRead]:
    stmt = select(Catalogue).order_by(
        Catalogue.sort_order.asc(), desc(Catalogue.created_at)
    )
    if campaign_id is not None:
        stmt = stmt.where(Catalogue.campaign_id == campaign_id)
    if status_filter:
        stmt = stmt.where(Catalogue.processing_status == status_filter)
    if not include_inactive:
        stmt = stmt.where(Catalogue.is_active.is_(True))
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Catalogue.title).like(needle),
                func.lower(Catalogue.slug).like(needle),
            )
        )
    return [CatalogueRead.model_validate(r) for r in db.execute(stmt).scalars()]


@router.post(
    "/catalogues",
    response_model=CatalogueDetail,
    status_code=status.HTTP_201_CREATED,
)
def upload_catalogue(
    request: Request,
    file: UploadFile = File(..., description="PDF source file"),
    slug: str = Form(...),
    title: str = Form(...),
    description: Optional[str] = Form(default=None),
    campaign_id: Optional[int] = Form(default=None),
    is_active: bool = Form(default=True),
    is_featured: bool = Form(default=False),
    sort_order: int = Form(default=0),
    meta_title: Optional[str] = Form(default=None),
    meta_description: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_MARKETING_CATALOGUES_MANAGE)),
) -> CatalogueDetail:
    """Create a Catalogue row + immediately render its PDF to WebP pages.

    Synchronous render — keeps the deploy simple (no broker / worker).
    For typical hypermarket flyers (under 30 pages) this returns
    inside 10-20 seconds. Large PDFs should be split before upload.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted (.pdf extension required).",
        )

    # Slug uniqueness up front so we don't waste a render on a row
    # we'll have to discard.
    slug_norm = slug.strip().lower()
    if db.execute(
        select(Catalogue).where(Catalogue.slug == slug_norm)
    ).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A catalogue with slug '{slug_norm}' already exists.",
        )
    if campaign_id is not None:
        _campaign_or_404(db, campaign_id)

    # Read the upload synchronously (this endpoint is ``def``, so
    # FastAPI runs it on the threadpool).
    pdf_bytes = file.file.read()
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds the {MAX_PDF_BYTES // (1024 * 1024)} MB upload cap.",
        )
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Empty PDF file.")

    row = Catalogue(
        campaign_id=campaign_id,
        slug=slug_norm,
        title=title.strip(),
        description=(description or "").strip() or None,
        pdf_original_filename=file.filename,
        file_size_bytes=len(pdf_bytes),
        processing_status=CATALOGUE_PENDING,
        is_active=is_active,
        is_featured=is_featured,
        sort_order=sort_order,
        meta_title=meta_title,
        meta_description=meta_description,
        created_by_id=actor.id,
    )
    db.add(row)
    db.flush()  # We need row.id before processing.

    try:
        result = process_catalogue(db, row, pdf_bytes)
    except CatalogueProcessingError as exc:
        # The row stays so the admin can re-upload via /reprocess and
        # the failure is visible in the catalogue list with a red badge.
        _audit(
            db,
            actor,
            request,
            action="marketing.catalogue.upload.failed",
            target_type="catalogue",
            target_id=row.id,
            details={"slug": row.slug, "error": str(exc)[:800]},
        )
        db.commit()
        raise HTTPException(status_code=500, detail=str(exc))

    _audit(
        db,
        actor,
        request,
        action="marketing.catalogue.create",
        target_type="catalogue",
        target_id=row.id,
        details={
            "slug": row.slug,
            "page_count": result.page_count,
            "bytes_written": result.bytes_written,
            "campaign_id": campaign_id,
        },
    )
    db.commit()
    db.refresh(row)
    return CatalogueDetail.model_validate(row)


@router.get("/catalogues/{catalogue_id}", response_model=CatalogueDetail)
def get_catalogue(
    catalogue_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(_CATALOGUES_VIEWER),
) -> CatalogueDetail:
    row = db.execute(
        select(Catalogue)
        .options(selectinload(Catalogue.pages))
        .where(Catalogue.id == catalogue_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Catalogue not found")
    return CatalogueDetail.model_validate(row)


@router.patch("/catalogues/{catalogue_id}", response_model=CatalogueRead)
def update_catalogue(
    catalogue_id: int,
    payload: CatalogueUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_MARKETING_CATALOGUES_MANAGE)),
) -> CatalogueRead:
    row = _catalogue_or_404(db, catalogue_id)
    updates = payload.model_dump(exclude_unset=True)
    if "slug" in updates and updates["slug"] and updates["slug"] != row.slug:
        slug_norm = updates["slug"].strip().lower()
        conflict = db.execute(
            select(Catalogue).where(
                Catalogue.slug == slug_norm, Catalogue.id != row.id
            )
        ).scalar_one_or_none()
        if conflict is not None:
            raise HTTPException(status_code=409, detail="Slug already in use.")
        updates["slug"] = slug_norm
    if "campaign_id" in updates and updates["campaign_id"] is not None:
        _campaign_or_404(db, updates["campaign_id"])

    changed: list[str] = []
    for key, value in updates.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed.append(key)
    if changed:
        _audit(
            db,
            actor,
            request,
            action="marketing.catalogue.update",
            target_type="catalogue",
            target_id=row.id,
            details={"fields": changed},
        )
    db.commit()
    db.refresh(row)
    return CatalogueRead.model_validate(row)


@router.delete(
    "/catalogues/{catalogue_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_catalogue(
    catalogue_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_MARKETING_CATALOGUES_MANAGE)),
) -> Response:
    row = _catalogue_or_404(db, catalogue_id)
    cid = row.id
    slug = row.slug
    # Capture the page count BEFORE we drop the row — once the cascade
    # fires we can't recover it, but the storage cleanup needs it to
    # know which page keys to walk.
    page_count = row.page_count
    _audit(
        db,
        actor,
        request,
        action="marketing.catalogue.delete",
        target_type="catalogue",
        target_id=row.id,
        details={"slug": slug, "page_count": page_count},
    )
    db.delete(row)
    db.commit()
    # Best-effort storage cleanup AFTER the row is gone — works for
    # both local-disk and R2 backends via deterministic keys.
    try:
        delete_catalogue_assets(cid, page_count)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to clean storage for catalogue %s: %s", cid, exc
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/catalogues/{catalogue_id}/reprocess", response_model=CatalogueDetail
)
def reprocess_catalogue(
    catalogue_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_MARKETING_CATALOGUES_MANAGE)),
) -> CatalogueDetail:
    """Re-render an existing catalogue's PDF.

    Pulls the stored source.pdf back from the storage backend (R2 or
    local disk) under the same deterministic key the processor wrote
    it to, then runs it through the processor again. Useful after
    tuning render quality or recovering a failed initial upload
    without re-uploading the file.
    """
    from app.services.storage import get_storage

    row = _catalogue_or_404(db, catalogue_id)
    try:
        pdf_bytes = get_storage().download_sync(source_pdf_key(row.id))
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "Original PDF is missing from storage — re-upload the catalogue."
            ),
        ) from exc

    try:
        result = process_catalogue(db, row, pdf_bytes)
    except CatalogueProcessingError as exc:
        _audit(
            db,
            actor,
            request,
            action="marketing.catalogue.reprocess.failed",
            target_type="catalogue",
            target_id=row.id,
            details={"error": str(exc)[:800]},
        )
        db.commit()
        raise HTTPException(status_code=500, detail=str(exc))

    _audit(
        db,
        actor,
        request,
        action="marketing.catalogue.reprocess",
        target_type="catalogue",
        target_id=row.id,
        details={"page_count": result.page_count},
    )
    db.commit()
    db.refresh(row)
    return CatalogueDetail.model_validate(row)


@router.get("/catalogues/{catalogue_id}/qr-code.png")
def catalogue_qr_code(
    catalogue_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(_CATALOGUES_VIEWER),
) -> Response:
    """Generate a branded PNG QR code for the catalogue's public URL.

    The code uses the highest error-correction level so the central
    brand badge doesn't break scannability. Returned as an inline
    PNG so the admin UI can either preview it directly or trigger a
    download via the Content-Disposition header.

    The encoded URL always points at the public Next.js viewer —
    never the backend's own host — so the QR resolves when scanned
    from a phone outside the local network.
    """
    from app.core.config import get_settings
    from app.services.qr_codes import build_catalogue_qr

    row = _catalogue_or_404(db, catalogue_id)
    settings = get_settings()
    site_url = settings.public_site_url.rstrip("/")
    public_url = f"{site_url}/offers/catalogues/{row.slug}"

    # Logo lookup order: per-catalogue upload (via storage backend)
    # → global brand logo on disk → "PUG" monogram fallback inside
    # the QR service.
    logo_bytes = _resolve_qr_logo_bytes(settings, row)
    png_bytes = build_catalogue_qr(public_url, logo_bytes=logo_bytes)

    safe_slug = "".join(
        ch if ch.isalnum() or ch in "-_" else "-" for ch in row.slug
    )
    filename = f"qr-{safe_slug}.png"

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=60",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


# Per-catalogue QR logo storage keys live under ``qr-logos/{id}{ext}``.
# We brute-force the same five extensions for cleanup so we never
# need a prefix-list call against R2 — at most five deletes per
# upload/delete operation.
_QR_LOGO_EXTENSIONS = (".png", ".jpg", ".jpeg", ".svg", ".webp")


def _qr_logo_storage_key(catalogue_id: int, ext: str) -> str:
    return f"qr-logos/{catalogue_id}{ext}"


def _qr_logo_key_from_url(url: str) -> Optional[str]:
    """Recover the storage key from whatever URL form the row carries.

    Works for both backend URL shapes:

        local : ``/api/v1/uploads/qr-logos/42.png``
        R2    : ``https://media.example.com/qr-logos/42.png``

    Returns ``None`` if the URL doesn't contain a ``/qr-logos/``
    segment — that means an old / unexpected layout and we'd rather
    skip the lookup than guess.
    """
    if not url:
        return None
    marker = "/qr-logos/"
    idx = url.find(marker)
    if idx < 0:
        return None
    return "qr-logos/" + url[idx + len(marker):]


def _resolve_qr_logo_bytes(settings, catalogue: Catalogue) -> Optional[bytes]:
    """Resolve which logo image, if any, to stamp into the QR centre.

    Preference order:
      1. ``catalogue.qr_logo_url`` (per-catalogue upload, fetched
         via the storage backend so R2-hosted logos work).
      2. ``uploads/brand-logo.png`` or ``uploads/logo.png`` (global
         operator fallback, always read off local disk because it's
         a deploy-time file rather than CMS content).
      3. ``None`` — the QR service falls back to a ``PUG`` text badge.
    """
    from pathlib import Path

    from app.services.storage import get_storage

    if catalogue.qr_logo_url:
        key = _qr_logo_key_from_url(catalogue.qr_logo_url)
        if key:
            try:
                return get_storage().download_sync(key)
            except FileNotFoundError:
                # Logo row carries a URL but the bytes are gone —
                # fall through to the global default rather than
                # 500ing the QR endpoint.
                logger.warning(
                    "qr_logo missing from storage", key=key, catalogue_id=catalogue.id
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "qr_logo fetch failed",
                    key=key,
                    catalogue_id=catalogue.id,
                    error=str(exc),
                )

    upload_dir = Path(settings.upload_dir)
    for name in ("brand-logo.png", "logo.png"):
        p = upload_dir / name
        if p.exists():
            try:
                return p.read_bytes()
            except OSError:
                continue
    return None


@router.post(
    "/catalogues/{catalogue_id}/qr-logo",
    response_model=CatalogueRead,
)
def upload_catalogue_qr_logo(
    catalogue_id: int,
    request: Request,
    file: UploadFile = File(..., description="Brand logo PNG/JPG/SVG"),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_MARKETING_CATALOGUES_MANAGE)),
) -> CatalogueRead:
    """Upload (or replace) the QR-centre brand logo for one catalogue.

    Accepts the common raster + vector formats. Stored via the
    pluggable storage backend under ``qr-logos/{catalogue_id}{ext}``
    so re-uploads overwrite deterministically and the same code path
    works for local-disk and R2 installs.
    """
    from pathlib import Path

    from app.services.storage import get_storage

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")
    ext = Path(file.filename).suffix.lower()
    if ext not in _QR_LOGO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Logo must be a PNG, JPG, SVG or WebP image.",
        )

    row = _catalogue_or_404(db, catalogue_id)

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty logo file.")
    if len(data) > 4 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Logo file exceeds the 4 MB cap.",
        )

    storage = get_storage()
    # A previous upload with a different extension would otherwise
    # linger as a storage orphan AND keep getting served via the old
    # URL until next overwrite. Brute-force-delete every known ext
    # — at most 5 round-trips, no list-objects required.
    for old_ext in _QR_LOGO_EXTENSIONS:
        if old_ext == ext:
            continue
        try:
            storage.delete_sync(_qr_logo_storage_key(row.id, old_ext))
        except Exception:  # noqa: BLE001
            pass

    content_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
    }[ext]
    try:
        logo_url = storage.upload_sync(
            _qr_logo_storage_key(row.id, ext), data, content_type
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail=f"Failed to upload logo to storage: {exc}",
        ) from exc

    row.qr_logo_url = logo_url
    _audit(
        db,
        actor,
        request,
        action="marketing.catalogue.qr_logo.upload",
        target_type="catalogue",
        target_id=row.id,
        details={"slug": row.slug, "bytes": len(data), "ext": ext},
    )
    db.commit()
    db.refresh(row)
    return CatalogueRead.model_validate(row)


@router.delete(
    "/catalogues/{catalogue_id}/qr-logo",
    response_model=CatalogueRead,
)
def delete_catalogue_qr_logo(
    catalogue_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_MARKETING_CATALOGUES_MANAGE)),
) -> CatalogueRead:
    """Remove the per-catalogue QR logo, falling back to the global one."""
    from app.services.storage import get_storage

    row = _catalogue_or_404(db, catalogue_id)
    if not row.qr_logo_url:
        return CatalogueRead.model_validate(row)

    storage = get_storage()
    # Drop the row's recorded key plus every other known extension —
    # belt-and-braces in case a prior upload left an orphan.
    keys_to_drop = set()
    primary = _qr_logo_key_from_url(row.qr_logo_url)
    if primary:
        keys_to_drop.add(primary)
    for ext in _QR_LOGO_EXTENSIONS:
        keys_to_drop.add(_qr_logo_storage_key(row.id, ext))
    for key in keys_to_drop:
        try:
            storage.delete_sync(key)
        except Exception:  # noqa: BLE001
            pass

    row.qr_logo_url = None
    _audit(
        db,
        actor,
        request,
        action="marketing.catalogue.qr_logo.delete",
        target_type="catalogue",
        target_id=row.id,
        details={"slug": row.slug},
    )
    db.commit()
    db.refresh(row)
    return CatalogueRead.model_validate(row)


@router.get(
    "/catalogues/{catalogue_id}/analytics", response_model=CatalogueAnalytics
)
def catalogue_analytics(
    catalogue_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(_CATALOGUES_VIEWER),
) -> CatalogueAnalytics:
    row = _catalogue_or_404(db, catalogue_id)
    total_views = int(
        db.execute(
            select(func.count())
            .select_from(CatalogueViewEvent)
            .where(CatalogueViewEvent.catalogue_id == row.id)
        ).scalar_one()
        or 0
    )
    unique_sessions = int(
        db.execute(
            select(func.count(func.distinct(CatalogueViewEvent.session_hash)))
            .where(
                CatalogueViewEvent.catalogue_id == row.id,
                CatalogueViewEvent.session_hash.is_not(None),
            )
        ).scalar_one()
        or 0
    )
    device_rows = db.execute(
        select(CatalogueViewEvent.device, func.count())
        .where(CatalogueViewEvent.catalogue_id == row.id)
        .group_by(CatalogueViewEvent.device)
    ).all()
    by_device = {(d or "unknown"): int(n) for d, n in device_rows}

    cutoff = datetime.now(timezone.utc) - timedelta(days=6)
    daily_rows = db.execute(
        select(
            func.date(CatalogueViewEvent.viewed_at).label("d"),
            func.count(),
        )
        .where(
            CatalogueViewEvent.catalogue_id == row.id,
            CatalogueViewEvent.viewed_at >= cutoff,
        )
        .group_by("d")
        .order_by("d")
    ).all()
    last_7 = [{"date": str(d), "views": int(n)} for d, n in daily_rows]

    return CatalogueAnalytics(
        catalogue_id=row.id,
        total_views=total_views,
        unique_sessions=unique_sessions,
        by_device=by_device,
        last_7_days=last_7,
    )


# ---------------------------------------------------------------------------
# PDF Compressor — admin utility
# ---------------------------------------------------------------------------

# Generous cap on the source PDF — much higher than the catalogue
# upload limit because the whole point of compression is to bring
# oversized originals back under that limit.
MAX_COMPRESS_INPUT_BYTES = 200 * 1024 * 1024  # 200 MB


@router.post("/pdf-compressor")
def compress_pdf_endpoint(
    file: UploadFile = File(..., description="PDF source to compress"),
    preset: str = Form(default="balanced"),
    actor: User = Depends(require_permission(PERM_MARKETING_CATALOGUES_MANAGE)),
) -> Response:
    """Compress an uploaded PDF and stream the result back.

    Preset = one of ``high`` / ``balanced`` / ``aggressive``
    (see ``app.services.pdf_compressor.PRESETS``). The compressed
    bytes never touch disk — they're built in memory and returned
    directly to the caller, who downloads the file to their local
    PC and re-uploads it via the regular catalogue upload flow.

    Surfaces three diagnostic headers so the frontend can show a
    "saved 73%" badge after the round-trip:

        X-Original-Size
        X-Compressed-Size
        X-Reduction-Pct      (0-100)
    """
    from app.services.pdf_compressor import (
        PRESETS,
        PdfCompressionError,
        compress_pdf,
    )

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted.",
        )
    chosen = PRESETS.get(preset.strip().lower())
    if chosen is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown preset '{preset}'. Use one of: {sorted(PRESETS)}",
        )

    pdf_bytes = file.file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty PDF.")
    if len(pdf_bytes) > MAX_COMPRESS_INPUT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Source PDF exceeds the "
                f"{MAX_COMPRESS_INPUT_BYTES // (1024 * 1024)} MB cap."
            ),
        )

    try:
        compressed, stats = compress_pdf(pdf_bytes, preset=chosen)
    except PdfCompressionError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    reduction_pct = max(0, round(stats.reduction_ratio * 100))
    out_name = _compressed_filename(file.filename)

    return Response(
        content=compressed,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{out_name}"',
            "Content-Length": str(len(compressed)),
            "X-Original-Size": str(stats.original_size_bytes),
            "X-Compressed-Size": str(stats.compressed_size_bytes),
            "X-Reduction-Pct": str(reduction_pct),
            "X-Page-Count": str(stats.page_count),
            "X-Preset": stats.preset_name,
            # CORS — expose the X-* headers so fetch can read them
            # client-side (they're hidden by default for cross-origin
            # responses).
            "Access-Control-Expose-Headers": (
                "X-Original-Size, X-Compressed-Size, X-Reduction-Pct, "
                "X-Page-Count, X-Preset, Content-Disposition"
            ),
            "Cache-Control": "no-store",
        },
    )


def _compressed_filename(original: str) -> str:
    """Produce a friendly output filename: 'flyer.pdf' -> 'flyer_compressed.pdf'."""
    base = original.strip()
    if base.lower().endswith(".pdf"):
        stem = base[:-4]
    else:
        stem = base
    return f"{stem}_compressed.pdf"


# ---------------------------------------------------------------------------
# Marketing dashboard
# ---------------------------------------------------------------------------


# Allowed period strings + their day count. ``all`` collapses to a very
# large lookback so we don't special-case the WHERE clause downstream.
_DASHBOARD_PERIODS: dict[str, tuple[int, str]] = {
    "7d": (7, "Last 7 days"),
    "30d": (30, "Last 30 days"),
    "90d": (90, "Last 90 days"),
    "all": (3650, "All time"),
}


@router.get("/dashboard", response_model=MarketingDashboard)
def marketing_dashboard(
    period: str = Query(
        default="30d",
        description="Lookback window: 7d, 30d, 90d, or all.",
    ),
    top_n: int = Query(default=5, ge=1, le=20),
    recent_n: int = Query(default=15, ge=1, le=50),
    actor: User = Depends(_DASHBOARD_VIEWER),
    db: Session = Depends(get_db),
) -> MarketingDashboard:
    """One-shot read-model for the admin Marketing → Dashboard page.

    Every aggregate is computed from ``catalogue_view_events`` (the
    authoritative source) rather than the denormalised
    ``catalogue.view_count`` / ``catalogue.download_count`` counters,
    because the counters can drift if events are ever inserted
    out-of-band. The dashboard is "what actually happened" — the row
    counters are still surfaced on the list page as a cheap summary.

    Returned in a single payload (rather than a fan-out of small
    endpoints) so the UI renders without intermediate spinners.
    """
    period_days, period_label = _DASHBOARD_PERIODS.get(
        period, _DASHBOARD_PERIODS["30d"]
    )
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=period_days)
    series_cutoff = now - timedelta(
        days=min(period_days, 90)
    )  # never chart > 90 buckets

    # ---------- KPIs ----------
    campaigns_total = int(
        db.execute(select(func.count()).select_from(OfferCampaign)).scalar_one()
        or 0
    )
    campaigns_active = int(
        db.execute(
            select(func.count())
            .select_from(OfferCampaign)
            .where(OfferCampaign.is_active.is_(True))
        ).scalar_one()
        or 0
    )
    catalogues_total = int(
        db.execute(select(func.count()).select_from(Catalogue)).scalar_one() or 0
    )
    by_status_rows = db.execute(
        select(Catalogue.processing_status, func.count())
        .group_by(Catalogue.processing_status)
    ).all()
    by_status = {s: int(n) for s, n in by_status_rows}
    catalogues_ready = by_status.get("ready", 0)
    catalogues_processing = (
        by_status.get("pending", 0) + by_status.get("processing", 0)
    )
    catalogues_failed = by_status.get("failed", 0)

    total_pages = int(
        db.execute(select(func.coalesce(func.sum(Catalogue.page_count), 0))).scalar_one()
        or 0
    )
    total_views_period = int(
        db.execute(
            select(func.count())
            .select_from(CatalogueViewEvent)
            .where(CatalogueViewEvent.viewed_at >= cutoff)
        ).scalar_one()
        or 0
    )
    total_views_all_time = int(
        db.execute(
            select(func.count()).select_from(CatalogueViewEvent)
        ).scalar_one()
        or 0
    )
    unique_sessions_period = int(
        db.execute(
            select(func.count(func.distinct(CatalogueViewEvent.session_hash)))
            .where(
                CatalogueViewEvent.viewed_at >= cutoff,
                CatalogueViewEvent.session_hash.is_not(None),
            )
        ).scalar_one()
        or 0
    )
    total_downloads_all_time = int(
        db.execute(
            select(func.coalesce(func.sum(Catalogue.download_count), 0))
        ).scalar_one()
        or 0
    )
    avg_duration = db.execute(
        select(func.avg(CatalogueViewEvent.duration_seconds))
        .where(
            CatalogueViewEvent.viewed_at >= cutoff,
            CatalogueViewEvent.duration_seconds.is_not(None),
            CatalogueViewEvent.duration_seconds > 0,
        )
    ).scalar_one()
    avg_session_duration_sec = int(avg_duration) if avg_duration else 0

    kpis = MarketingDashboardKpis(
        campaigns_total=campaigns_total,
        campaigns_active=campaigns_active,
        catalogues_total=catalogues_total,
        catalogues_ready=catalogues_ready,
        catalogues_processing=catalogues_processing,
        catalogues_failed=catalogues_failed,
        total_pages=total_pages,
        total_views_period=total_views_period,
        total_views_all_time=total_views_all_time,
        unique_sessions_period=unique_sessions_period,
        total_downloads_all_time=total_downloads_all_time,
        avg_session_duration_sec=avg_session_duration_sec,
    )

    # ---------- Daily series (zero-filled) ----------
    daily_rows = db.execute(
        select(
            func.date(CatalogueViewEvent.viewed_at).label("d"),
            func.count(),
        )
        .where(CatalogueViewEvent.viewed_at >= series_cutoff)
        .group_by("d")
        .order_by("d")
    ).all()
    daily_map: dict[date, int] = {}
    for d, n in daily_rows:
        # SQLite returns a str, Postgres a date — normalise.
        key = d if isinstance(d, date) else date.fromisoformat(str(d))
        daily_map[key] = int(n)
    series: list[MarketingDashboardSeriesPoint] = []
    bucket_days = (now.date() - series_cutoff.date()).days + 1
    for offset in range(bucket_days):
        bucket = series_cutoff.date() + timedelta(days=offset)
        series.append(
            MarketingDashboardSeriesPoint(
                date=bucket, views=daily_map.get(bucket, 0)
            )
        )

    # ---------- Top catalogues by views (period) ----------
    top_cat_rows = db.execute(
        select(
            Catalogue.id,
            Catalogue.slug,
            Catalogue.title,
            Catalogue.campaign_id,
            Catalogue.download_count,
            func.count(CatalogueViewEvent.id).label("views"),
        )
        .join(
            CatalogueViewEvent,
            (CatalogueViewEvent.catalogue_id == Catalogue.id)
            & (CatalogueViewEvent.viewed_at >= cutoff),
            isouter=True,
        )
        .group_by(
            Catalogue.id,
            Catalogue.slug,
            Catalogue.title,
            Catalogue.campaign_id,
            Catalogue.download_count,
        )
        .order_by(desc("views"))
        .limit(top_n)
    ).all()
    # Resolve campaign titles once.
    campaign_titles: dict[int, str] = {}
    if any(row.campaign_id for row in top_cat_rows):
        campaign_id_set = {
            row.campaign_id for row in top_cat_rows if row.campaign_id
        }
        for c in db.execute(
            select(OfferCampaign.id, OfferCampaign.title).where(
                OfferCampaign.id.in_(campaign_id_set)
            )
        ).all():
            campaign_titles[int(c.id)] = c.title
    top_catalogues = [
        MarketingDashboardTopCatalogue(
            id=int(row.id),
            slug=row.slug,
            title=row.title,
            campaign_id=row.campaign_id,
            campaign_title=campaign_titles.get(row.campaign_id) if row.campaign_id else None,
            views=int(row.views or 0),
            downloads=int(row.download_count or 0),
        )
        for row in top_cat_rows
    ]

    # ---------- Top campaigns by views (period) ----------
    # Sum views across each campaign's catalogues. Catalogues without
    # a campaign (standalone) are excluded — surfaced via top_catalogues.
    top_camp_rows = db.execute(
        select(
            OfferCampaign.id,
            OfferCampaign.slug,
            OfferCampaign.title,
            OfferCampaign.branch,
            func.count(func.distinct(Catalogue.id)).label("catalogue_count"),
            func.count(CatalogueViewEvent.id).label("views"),
        )
        .join(Catalogue, Catalogue.campaign_id == OfferCampaign.id, isouter=True)
        .join(
            CatalogueViewEvent,
            (CatalogueViewEvent.catalogue_id == Catalogue.id)
            & (CatalogueViewEvent.viewed_at >= cutoff),
            isouter=True,
        )
        .group_by(
            OfferCampaign.id,
            OfferCampaign.slug,
            OfferCampaign.title,
            OfferCampaign.branch,
        )
        .order_by(desc("views"))
        .limit(top_n)
    ).all()
    top_campaigns = [
        MarketingDashboardTopCampaign(
            id=int(row.id),
            slug=row.slug,
            title=row.title,
            branch=row.branch,
            catalogue_count=int(row.catalogue_count or 0),
            views=int(row.views or 0),
        )
        for row in top_camp_rows
    ]

    # ---------- Device mix (period) ----------
    device_rows = db.execute(
        select(CatalogueViewEvent.device, func.count())
        .where(CatalogueViewEvent.viewed_at >= cutoff)
        .group_by(CatalogueViewEvent.device)
    ).all()
    by_device = {(d or "unknown"): int(n) for d, n in device_rows}

    # ---------- Recent activity (live feed) ----------
    recent_rows = db.execute(
        select(
            CatalogueViewEvent.catalogue_id,
            CatalogueViewEvent.device,
            CatalogueViewEvent.duration_seconds,
            CatalogueViewEvent.viewed_at,
            Catalogue.title,
            Catalogue.slug,
        )
        .join(Catalogue, Catalogue.id == CatalogueViewEvent.catalogue_id)
        .order_by(desc(CatalogueViewEvent.viewed_at))
        .limit(recent_n)
    ).all()
    recent_views = [
        MarketingDashboardRecentView(
            catalogue_id=int(r.catalogue_id),
            catalogue_title=r.title,
            catalogue_slug=r.slug,
            device=r.device,
            duration_seconds=r.duration_seconds,
            viewed_at=r.viewed_at,
        )
        for r in recent_rows
    ]

    return MarketingDashboard(
        period_days=period_days,
        period_label=period_label,
        generated_at=now,
        kpis=kpis,
        views_over_time=series,
        top_catalogues=top_catalogues,
        top_campaigns=top_campaigns,
        by_device=by_device,
        recent_views=recent_views,
    )


@router.post(
    "/catalogues/reconcile-counters",
    response_model=ReconcileCountersResult,
)
def reconcile_view_counters(
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_MARKETING_CATALOGUES_MANAGE)),
) -> ReconcileCountersResult:
    """Recompute ``catalogue.view_count`` from the events table.

    The view counter on each row is bumped per request alongside the
    event insert, but if events are ever loaded out-of-band (test
    fixtures, manual SQL, a hot-fix migration) the counter can fall
    behind. This re-syncs every row to ``COUNT(events)``. Read-only
    on the events table, so safe to run any time.
    """
    before_total = int(
        db.execute(
            select(func.coalesce(func.sum(Catalogue.view_count), 0))
        ).scalar_one()
        or 0
    )
    event_counts = dict(
        db.execute(
            select(
                CatalogueViewEvent.catalogue_id,
                func.count(CatalogueViewEvent.id),
            ).group_by(CatalogueViewEvent.catalogue_id)
        ).all()
    )
    catalogues = db.execute(select(Catalogue)).scalars().all()
    updated = 0
    for c in catalogues:
        target = int(event_counts.get(c.id, 0))
        if c.view_count != target:
            c.view_count = target
            updated += 1
    after_total = sum(c.view_count for c in catalogues)
    _audit(
        db,
        actor,
        request,
        action="marketing.catalogues.reconcile_counters",
        target_type="catalogue",
        target_id=0,
        details={
            "inspected": len(catalogues),
            "updated": updated,
            "before_total": before_total,
            "after_total": after_total,
        },
    )
    db.commit()
    return ReconcileCountersResult(
        catalogues_inspected=len(catalogues),
        catalogues_updated=updated,
        total_view_count_before=before_total,
        total_view_count_after=after_total,
    )


__all__ = ["router"]

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

import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

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
    require_permission,
    require_website_admin,
)
from app.auth.permissions import (
    PERM_MARKETING_CAMPAIGNS_MANAGE,
    PERM_MARKETING_CATALOGUES_MANAGE,
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
)
from app.services.audit_log import record_audit
from app.services.catalogue_processor import (
    CatalogueProcessingError,
    delete_catalogue_files,
    process_catalogue,
)


logger = logging.getLogger(__name__)


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
    actor: User = Depends(require_permission(PERM_MARKETING_CAMPAIGNS_MANAGE)),
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
    actor: User = Depends(require_permission(PERM_MARKETING_CAMPAIGNS_MANAGE)),
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
    actor: User = Depends(require_permission(PERM_MARKETING_CATALOGUES_MANAGE)),
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
    actor: User = Depends(require_permission(PERM_MARKETING_CATALOGUES_MANAGE)),
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
    _audit(
        db,
        actor,
        request,
        action="marketing.catalogue.delete",
        target_type="catalogue",
        target_id=row.id,
        details={"slug": slug, "page_count": row.page_count},
    )
    db.delete(row)
    db.commit()
    # Best-effort filesystem cleanup AFTER the row is gone.
    try:
        delete_catalogue_files(cid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to clean files for catalogue %s: %s", cid, exc)
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

    Reads the stored source.pdf back from disk and runs it through
    the processor again — useful after tuning render quality or
    recovering a failed initial upload without re-uploading the file.
    """
    from pathlib import Path

    from app.core.config import get_settings

    row = _catalogue_or_404(db, catalogue_id)
    settings = get_settings()
    relative = (row.pdf_url or "").split("/api/v1/uploads/", 1)[-1]
    pdf_path = Path(settings.upload_dir) / relative if relative else None
    if pdf_path is None or not pdf_path.exists():
        raise HTTPException(
            status_code=400,
            detail=(
                "Original PDF is missing on disk — re-upload the catalogue."
            ),
        )

    try:
        result = process_catalogue(db, row, pdf_path.read_bytes())
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


@router.get(
    "/catalogues/{catalogue_id}/analytics", response_model=CatalogueAnalytics
)
def catalogue_analytics(
    catalogue_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_MARKETING_CATALOGUES_MANAGE)),
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


__all__ = ["router"]

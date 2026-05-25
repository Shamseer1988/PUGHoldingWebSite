"""Website Admin CMS endpoints (Phase 5).

All routes require a website-scoped bearer token. CRUD actions write
entries to the audit log so the website audit log viewer surfaces
who-did-what-when.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context, require_website_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.models.auth import SCOPE_WEBSITE, AuditLog, User
from app.models.cms import (
    MEDIA_KIND_IMAGE,
    MEDIA_KIND_VIDEO,
    CMSPage,
    Company,
    CompanyBrandLogo,
    CompanyService,
    ContactMessage,
    HeroSlide,
    LeadershipMessage,
    MediaAsset,
    NavigationItem,
    NewsItem,
    NewsletterSubscriber,
    SITE_PAGE_KEYS,
    SitePage,
    SiteSetting,
)
from app.schemas.cms import (
    CMSPageCreate,
    CMSPageListItem,
    CMSPageRead,
    CMSPageUpdate,
    CompanyCreate,
    CompanyRead,
    CompanyUpdate,
    ContactMessageRead,
    ContactReply,
    DashboardSummary,
    HeroSlideCreate,
    HeroSlideRead,
    HeroSlideUpdate,
    LeadershipCreate,
    LeadershipRead,
    LeadershipUpdate,
    MediaAssetRead,
    MediaAssetUpdate,
    MediaUploadResult,
    NavigationItemCreate,
    NavigationItemRead,
    NavigationItemTreeRead,
    NavigationItemUpdate,
    NewsCreate,
    NewsRead,
    NewsUpdate,
    NewsletterSubscriberRead,
    SitePageRead,
    SitePageUpdate,
    SiteSettingRead,
    SiteSettingUpdate,
    UploadResponse,
)
from app.services.audit_log import record_audit


# Image upload constraints
ALLOWED_IMAGE_MIME = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


router = APIRouter(
    prefix="/admin/cms",
    tags=["Website Admin - CMS"],
    dependencies=[Depends(require_website_admin)],
)


def _audit(
    db: Session,
    user: User,
    request: Request,
    *,
    action: str,
    target_type: str,
    target_id: object,
    details: Optional[dict] = None,
) -> None:
    ctx = get_request_context(request)
    record_audit(
        db,
        action=action,
        actor_id=user.id,
        actor_email=user.email,
        scope=SCOPE_WEBSITE,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details=details,
        commit=False,
    )


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_model=DashboardSummary)
def dashboard(db: Session = Depends(get_db)) -> DashboardSummary:
    def count(model) -> int:
        return db.execute(select(func.count()).select_from(model)).scalar_one() or 0

    stats = [
        {"key": "companies", "label": "Companies", "value": count(Company)},
        {"key": "news", "label": "News & events", "value": count(NewsItem)},
        {"key": "leadership", "label": "Leadership messages", "value": count(LeadershipMessage)},
        {"key": "hero_slides", "label": "Hero slides", "value": count(HeroSlide)},
        {
            "key": "contact_unread",
            "label": "Unread messages",
            "value": db.execute(
                select(func.count())
                .select_from(ContactMessage)
                .where(ContactMessage.is_read.is_(False))
            ).scalar_one()
            or 0,
        },
        {"key": "subscribers", "label": "Newsletter subscribers", "value": count(NewsletterSubscriber)},
    ]

    contact_per_month = _bucket_by_month(db, ContactMessage.created_at)
    news_per_month = _bucket_by_month(db, NewsItem.published_at)

    latest_messages = (
        db.execute(
            select(ContactMessage)
            .order_by(desc(ContactMessage.created_at))
            .limit(5)
        )
        .scalars()
        .all()
    )
    latest_news = (
        db.execute(
            select(NewsItem)
            .order_by(desc(NewsItem.published_at))
            .limit(5)
        )
        .scalars()
        .all()
    )

    return DashboardSummary(
        stats=stats,
        contact_messages_per_month=contact_per_month,
        news_per_month=news_per_month,
        latest_contact_messages=[
            ContactMessageRead.model_validate(m) for m in latest_messages
        ],
        latest_news=[NewsRead.model_validate(n) for n in latest_news],
    )


def _bucket_by_month(db: Session, column) -> list[dict]:
    """Aggregate rows by YYYY-MM. Done in Python so the same code works
    against PostgreSQL (production) and SQLite (tests) without dialect
    branching."""
    rows = db.execute(select(column)).all()
    buckets: dict[str, int] = {}
    for (ts,) in rows:
        if ts is None:
            continue
        key = ts.strftime("%Y-%m")
        buckets[key] = buckets.get(key, 0) + 1
    return [
        {"month": month, "count": count}
        for month, count in sorted(buckets.items())
    ]


# ---------------------------------------------------------------------------
# Hero slides
# ---------------------------------------------------------------------------


@router.get("/hero-slides", response_model=List[HeroSlideRead])
def list_hero_slides(db: Session = Depends(get_db)) -> List[HeroSlide]:
    return (
        db.execute(select(HeroSlide).order_by(HeroSlide.display_order, HeroSlide.id))
        .scalars()
        .all()
    )


@router.post("/hero-slides", response_model=HeroSlideRead, status_code=status.HTTP_201_CREATED)
def create_hero_slide(
    payload: HeroSlideCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> HeroSlide:
    slide = HeroSlide(**payload.model_dump())
    db.add(slide)
    db.flush()
    _audit(db, user, request, action="cms.hero_slide.create", target_type="hero_slide", target_id=slide.id)
    db.commit()
    db.refresh(slide)
    return slide


@router.patch("/hero-slides/{slide_id}", response_model=HeroSlideRead)
def update_hero_slide(
    slide_id: int,
    payload: HeroSlideUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> HeroSlide:
    slide = db.get(HeroSlide, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="Hero slide not found")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(slide, k, v)
    _audit(
        db,
        user,
        request,
        action="cms.hero_slide.update",
        target_type="hero_slide",
        target_id=slide.id,
        details={"changed_keys": list(changes.keys())},
    )
    db.commit()
    db.refresh(slide)
    return slide


@router.delete("/hero-slides/{slide_id}")
def delete_hero_slide(
    slide_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> Response:
    slide = db.get(HeroSlide, slide_id)
    if slide is None:
        raise HTTPException(status_code=404, detail="Hero slide not found")
    db.delete(slide)
    _audit(db, user, request, action="cms.hero_slide.delete", target_type="hero_slide", target_id=slide_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------


@router.get("/companies", response_model=List[CompanyRead])
def list_companies(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(default=None, pattern=r"^(distribution|retail|services)$"),
) -> List[Company]:
    stmt = select(Company).order_by(Company.display_order, Company.id)
    if category:
        stmt = stmt.where(Company.category == category)
    return db.execute(stmt).scalars().all()


@router.get("/companies/{company_id}", response_model=CompanyRead)
def get_company(company_id: int, db: Session = Depends(get_db)) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.post("/companies", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> Company:
    data = payload.model_dump()
    service_names = data.pop("services", [])
    brand_logos = data.pop("brand_logos", [])
    company = Company(**data)
    for i, name in enumerate(service_names):
        company.services.append(CompanyService(name=name, display_order=i))
    for i, logo in enumerate(brand_logos):
        company.brand_logos.append(
            CompanyBrandLogo(
                image_url=logo["image_url"],
                name=logo.get("name"),
                link_url=logo.get("link_url"),
                display_order=logo.get("display_order") or i,
            )
        )
    db.add(company)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already exists") from exc
    _audit(db, user, request, action="cms.company.create", target_type="company", target_id=company.id)
    db.commit()
    db.refresh(company)
    return company


@router.patch("/companies/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> Company:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    changes = payload.model_dump(exclude_unset=True)
    service_names = changes.pop("services", None)
    brand_logos = changes.pop("brand_logos", None)
    for k, v in changes.items():
        setattr(company, k, v)
    if service_names is not None:
        company.services.clear()
        for i, name in enumerate(service_names):
            company.services.append(CompanyService(name=name, display_order=i))
    if brand_logos is not None:
        # Wholesale replace — admin form posts the full ordered list on
        # every save so we don't need to diff individual rows.
        company.brand_logos.clear()
        for i, logo in enumerate(brand_logos):
            company.brand_logos.append(
                CompanyBrandLogo(
                    image_url=logo["image_url"],
                    name=logo.get("name"),
                    link_url=logo.get("link_url"),
                    display_order=logo.get("display_order") or i,
                )
            )
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already exists") from exc
    changed_keys = list(changes.keys())
    if service_names is not None:
        changed_keys.append("services")
    if brand_logos is not None:
        changed_keys.append("brand_logos")
    _audit(
        db,
        user,
        request,
        action="cms.company.update",
        target_type="company",
        target_id=company.id,
        details={"changed_keys": changed_keys},
    )
    db.commit()
    db.refresh(company)
    return company


@router.delete("/companies/{company_id}")
def delete_company(
    company_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> Response:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    db.delete(company)
    _audit(db, user, request, action="cms.company.delete", target_type="company", target_id=company_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Leadership
# ---------------------------------------------------------------------------


@router.get("/leadership", response_model=List[LeadershipRead])
def list_leadership(db: Session = Depends(get_db)) -> List[LeadershipMessage]:
    return (
        db.execute(
            select(LeadershipMessage).order_by(
                LeadershipMessage.display_order, LeadershipMessage.id
            )
        )
        .scalars()
        .all()
    )


@router.post("/leadership", response_model=LeadershipRead, status_code=201)
def create_leadership(
    payload: LeadershipCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> LeadershipMessage:
    leader = LeadershipMessage(**payload.model_dump())
    db.add(leader)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already exists") from exc
    _audit(db, user, request, action="cms.leadership.create", target_type="leadership", target_id=leader.id)
    db.commit()
    db.refresh(leader)
    return leader


@router.patch("/leadership/{leader_id}", response_model=LeadershipRead)
def update_leadership(
    leader_id: int,
    payload: LeadershipUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> LeadershipMessage:
    leader = db.get(LeadershipMessage, leader_id)
    if leader is None:
        raise HTTPException(status_code=404, detail="Leadership not found")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(leader, k, v)
    _audit(
        db,
        user,
        request,
        action="cms.leadership.update",
        target_type="leadership",
        target_id=leader.id,
        details={"changed_keys": list(changes.keys())},
    )
    db.commit()
    db.refresh(leader)
    return leader


@router.delete("/leadership/{leader_id}")
def delete_leadership(
    leader_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> Response:
    leader = db.get(LeadershipMessage, leader_id)
    if leader is None:
        raise HTTPException(status_code=404, detail="Leadership not found")
    db.delete(leader)
    _audit(db, user, request, action="cms.leadership.delete", target_type="leadership", target_id=leader_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# News & events
# ---------------------------------------------------------------------------


@router.get("/news", response_model=List[NewsRead])
def list_news(db: Session = Depends(get_db)) -> List[NewsItem]:
    return (
        db.execute(select(NewsItem).order_by(desc(NewsItem.published_at), desc(NewsItem.id)))
        .scalars()
        .all()
    )


@router.post("/news", response_model=NewsRead, status_code=201)
def create_news(
    payload: NewsCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> NewsItem:
    data = payload.model_dump()
    if data.get("published_at") is None:
        data["published_at"] = datetime.now(timezone.utc)
    item = NewsItem(**data)
    db.add(item)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already exists") from exc
    _audit(db, user, request, action="cms.news.create", target_type="news", target_id=item.id)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/news/{item_id}", response_model=NewsRead)
def update_news(
    item_id: int,
    payload: NewsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> NewsItem:
    item = db.get(NewsItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(item, k, v)
    _audit(
        db,
        user,
        request,
        action="cms.news.update",
        target_type="news",
        target_id=item.id,
        details={"changed_keys": list(changes.keys())},
    )
    db.commit()
    db.refresh(item)
    return item


@router.delete("/news/{item_id}")
def delete_news(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> Response:
    item = db.get(NewsItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")
    db.delete(item)
    _audit(db, user, request, action="cms.news.delete", target_type="news", target_id=item_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Contact inbox
# ---------------------------------------------------------------------------


@router.get("/contact-messages", response_model=List[ContactMessageRead])
def list_contact_messages(
    db: Session = Depends(get_db),
    unread_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
) -> List[ContactMessage]:
    stmt = select(ContactMessage).order_by(desc(ContactMessage.created_at))
    if unread_only:
        stmt = stmt.where(ContactMessage.is_read.is_(False))
    if not include_archived:
        stmt = stmt.where(ContactMessage.is_archived.is_(False))
    return db.execute(stmt).scalars().all()


@router.patch("/contact-messages/{message_id}/read", response_model=ContactMessageRead)
def mark_read(
    message_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> ContactMessage:
    msg = _get_contact_or_404(db, message_id)
    msg.is_read = True
    _audit(db, user, request, action="cms.contact.read", target_type="contact_message", target_id=msg.id)
    db.commit()
    db.refresh(msg)
    return msg


@router.patch("/contact-messages/{message_id}/archive", response_model=ContactMessageRead)
def archive(
    message_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> ContactMessage:
    msg = _get_contact_or_404(db, message_id)
    msg.is_archived = True
    _audit(
        db,
        user,
        request,
        action="cms.contact.archive",
        target_type="contact_message",
        target_id=msg.id,
    )
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/contact-messages/{message_id}/reply", response_model=ContactMessageRead)
def reply(
    message_id: int,
    payload: ContactReply,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> ContactMessage:
    msg = _get_contact_or_404(db, message_id)
    msg.reply_body = payload.reply_body
    msg.is_replied = True
    msg.is_read = True
    msg.replied_by_id = user.id
    msg.replied_at = datetime.now(timezone.utc)
    _audit(
        db,
        user,
        request,
        action="cms.contact.reply",
        target_type="contact_message",
        target_id=msg.id,
    )
    db.commit()
    db.refresh(msg)
    return msg


def _get_contact_or_404(db: Session, message_id: int) -> ContactMessage:
    msg = db.get(ContactMessage, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Contact message not found")
    return msg


# ---------------------------------------------------------------------------
# Newsletter subscribers
# ---------------------------------------------------------------------------


@router.get("/newsletter-subscribers", response_model=List[NewsletterSubscriberRead])
def list_subscribers(db: Session = Depends(get_db)) -> List[NewsletterSubscriber]:
    return (
        db.execute(select(NewsletterSubscriber).order_by(desc(NewsletterSubscriber.created_at)))
        .scalars()
        .all()
    )


@router.delete("/newsletter-subscribers/{subscriber_id}")
def remove_subscriber(
    subscriber_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> Response:
    sub = db.get(NewsletterSubscriber, subscriber_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    db.delete(sub)
    _audit(
        db,
        user,
        request,
        action="cms.newsletter.delete",
        target_type="subscriber",
        target_id=subscriber_id,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Site settings (single row, id == 1)
# ---------------------------------------------------------------------------


def _get_or_create_settings(db: Session) -> SiteSetting:
    settings = db.get(SiteSetting, 1)
    if settings is None:
        settings = SiteSetting(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("/site-settings", response_model=SiteSettingRead)
def get_site_settings(db: Session = Depends(get_db)) -> SiteSetting:
    return _get_or_create_settings(db)


@router.patch("/site-settings", response_model=SiteSettingRead)
def update_site_settings(
    payload: SiteSettingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> SiteSetting:
    settings = _get_or_create_settings(db)
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(settings, k, v)
    _audit(
        db,
        user,
        request,
        action="cms.site_settings.update",
        target_type="site_settings",
        target_id=settings.id,
        details={"changed_keys": list(changes.keys())},
    )
    db.commit()
    db.refresh(settings)
    return settings


# ---------------------------------------------------------------------------
# Audit log viewer
# ---------------------------------------------------------------------------


@router.get("/audit-logs")
def list_audit_logs(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    scope: Optional[str] = Query(default=None),
    action_prefix: Optional[str] = Query(default=None),
) -> list[dict]:
    stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    if scope:
        stmt = stmt.where(AuditLog.scope == scope)
    if action_prefix:
        stmt = stmt.where(AuditLog.action.like(f"{action_prefix}%"))
    rows = db.execute(stmt).scalars().all()
    return [
        {
            "id": row.id,
            "action": row.action,
            "scope": row.scope,
            "actor_id": row.actor_id,
            "actor_email": row.actor_email,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "ip_address": row.ip_address,
            "details": row.details,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Image uploads (CMS)
# ---------------------------------------------------------------------------


@router.post("/uploads/image", response_model=UploadResponse, status_code=201)
async def upload_image(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
    file: UploadFile = File(...),
) -> UploadResponse:
    """Accept a single image upload from the admin CMS.

    Files are stored under ``<upload_dir>/cms/`` with a content-hash
    filename so identical uploads dedupe naturally. Returns a public
    URL the frontend can render.
    """
    ext = ALLOWED_IMAGE_MIME.get(file.content_type or "")
    if ext is None:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. "
            f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_MIME))}",
        )

    # Read and validate the size.
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data)} bytes). Max {MAX_IMAGE_BYTES}.",
        )
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty upload")

    settings = get_settings()
    base = Path(settings.upload_dir) / "cms"
    base.mkdir(parents=True, exist_ok=True)

    content_hash = hashlib.sha256(data).hexdigest()
    filename = f"{content_hash[:16]}.{ext}"
    target = base / filename

    if not target.exists():
        target.write_bytes(data)

    # Public URL — served by the StaticFiles mount in app/main.py.
    url = f"/api/v1/uploads/cms/{filename}"

    # Resize + WebP variants so the public site doesn't ship the
    # full-res original. See app/services/image_optimization.py.
    from app.services.image_optimization import optimize_image

    variant_set = optimize_image(
        target,
        public_base_url="/api/v1/uploads/cms",
        mime_type=file.content_type,
    )
    variants_payload = variant_set.as_dict() if variant_set is not None else None

    # Phase 5 follow-up — persist a MediaAsset row so the gallery can
    # list this file. Dedupe by file_hash; if a row already exists,
    # return it instead of creating a duplicate.
    asset, _deduped = _upsert_media_asset(
        db,
        kind=MEDIA_KIND_IMAGE,
        filename=filename,
        original_name=file.filename,
        url=url,
        mime_type=file.content_type,
        file_size=len(data),
        file_hash=content_hash,
        uploaded_by_id=user.id,
    )
    if variants_payload is not None and asset.variants != variants_payload:
        asset.variants = variants_payload
        db.flush()

    ctx = get_request_context(request)
    record_audit(
        db,
        action="cms.upload.image",
        actor_id=user.id,
        actor_email=user.email,
        scope=SCOPE_WEBSITE,
        target_type="upload",
        target_id=filename,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "size": len(data),
            "mime_type": file.content_type,
            "original_name": file.filename,
        },
    )

    return UploadResponse(
        url=url,
        filename=filename,
        size=len(data),
        mime_type=file.content_type or "",
    )


# ---------------------------------------------------------------------------
# Media gallery (Phase 5 follow-up)
# ---------------------------------------------------------------------------


ALLOWED_VIDEO_MIME = {
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/ogg": "ogv",
    "video/quicktime": "mov",
}
MAX_VIDEO_BYTES = 50 * 1024 * 1024  # 50 MB


def _upsert_media_asset(
    db: Session,
    *,
    kind: str,
    filename: str,
    original_name: Optional[str],
    url: str,
    mime_type: Optional[str],
    file_size: int,
    file_hash: str,
    uploaded_by_id: Optional[int],
) -> tuple[MediaAsset, bool]:
    """Persist (or fetch existing) media-asset row keyed by content hash."""
    existing = db.execute(
        select(MediaAsset).where(MediaAsset.file_hash == file_hash)
    ).scalar_one_or_none()
    if existing is not None:
        # Update upload metadata that may have changed (e.g. original name)
        # but keep title / alt / tags exactly as the admin left them.
        if original_name and not existing.original_name:
            existing.original_name = original_name
        return existing, True

    asset = MediaAsset(
        kind=kind,
        filename=filename,
        original_name=original_name,
        url=url,
        mime_type=mime_type,
        file_size=file_size,
        file_hash=file_hash,
        uploaded_by_id=uploaded_by_id,
    )
    db.add(asset)
    db.flush()
    return asset, False


@router.post("/media/upload", response_model=MediaUploadResult, status_code=201)
async def upload_media(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
    file: UploadFile = File(...),
) -> MediaUploadResult:
    """Accept either an image OR a video and add it to the media gallery."""
    content_type = file.content_type or ""
    if content_type in ALLOWED_IMAGE_MIME:
        ext = ALLOWED_IMAGE_MIME[content_type]
        kind = MEDIA_KIND_IMAGE
        max_bytes = MAX_IMAGE_BYTES
    elif content_type in ALLOWED_VIDEO_MIME:
        ext = ALLOWED_VIDEO_MIME[content_type]
        kind = MEDIA_KIND_VIDEO
        max_bytes = MAX_VIDEO_BYTES
    else:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type: {content_type}. Allowed images: "
                f"{', '.join(sorted(ALLOWED_IMAGE_MIME))}; videos: "
                f"{', '.join(sorted(ALLOWED_VIDEO_MIME))}"
            ),
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data)} bytes). Max {max_bytes}.",
        )

    settings = get_settings()
    base = Path(settings.upload_dir) / "cms"
    base.mkdir(parents=True, exist_ok=True)
    content_hash = hashlib.sha256(data).hexdigest()
    filename = f"{content_hash[:16]}.{ext}"
    target = base / filename
    if not target.exists():
        target.write_bytes(data)
    url = f"/api/v1/uploads/cms/{filename}"

    # Generate WebP + JPEG variants for images so the public site
    # serves a fraction of the original byte size. Video uploads
    # and SVGs skip this step (the helper returns None).
    variants_payload: Optional[dict] = None
    if kind == MEDIA_KIND_IMAGE:
        from app.services.image_optimization import optimize_image

        variant_set = optimize_image(
            target,
            public_base_url="/api/v1/uploads/cms",
            mime_type=content_type,
        )
        if variant_set is not None:
            variants_payload = variant_set.as_dict()

    asset, deduped = _upsert_media_asset(
        db,
        kind=kind,
        filename=filename,
        original_name=file.filename,
        url=url,
        mime_type=content_type,
        file_size=len(data),
        file_hash=content_hash,
        uploaded_by_id=user.id,
    )

    # Persist variants whether or not this is a dedup hit — re-running
    # the optimizer for a deduped file is harmless and lets us pick up
    # variants for assets uploaded before the pipeline existed.
    if variants_payload is not None and asset.variants != variants_payload:
        asset.variants = variants_payload
        db.flush()

    if not deduped:
        ctx = get_request_context(request)
        record_audit(
            db,
            action="cms.media.upload",
            actor_id=user.id,
            actor_email=user.email,
            scope=SCOPE_WEBSITE,
            target_type="media_asset",
            target_id=str(asset.id),
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
            details={
                "kind": kind,
                "size": len(data),
                "mime_type": content_type,
                "original_name": file.filename,
            },
            commit=False,
        )
    db.commit()
    db.refresh(asset)
    return MediaUploadResult(
        asset=MediaAssetRead.model_validate(asset),
        deduped=deduped,
    )


@router.get("/media", response_model=List[MediaAssetRead])
def list_media(
    db: Session = Depends(get_db),
    kind: Optional[str] = Query(default=None, max_length=16),
    q: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
) -> List[MediaAsset]:
    stmt = select(MediaAsset).order_by(desc(MediaAsset.created_at)).limit(limit)
    if kind:
        stmt = stmt.where(MediaAsset.kind == kind)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            (func.lower(MediaAsset.filename).like(like))
            | (func.lower(MediaAsset.original_name).like(like))
            | (func.lower(MediaAsset.title).like(like))
            | (func.lower(MediaAsset.alt_text).like(like))
            | (func.lower(MediaAsset.tags).like(like))
        )
    return db.execute(stmt).scalars().all()


@router.patch("/media/{asset_id}", response_model=MediaAssetRead)
def update_media(
    asset_id: int,
    payload: MediaAssetUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> MediaAsset:
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    updates = payload.model_dump(exclude_unset=True)
    changed: list[str] = []
    for field, value in updates.items():
        if isinstance(value, str):
            value = value.strip() or None
        if getattr(asset, field) != value:
            setattr(asset, field, value)
            changed.append(field)
    if changed:
        ctx = get_request_context(request)
        record_audit(
            db,
            action="cms.media.update",
            actor_id=user.id,
            actor_email=user.email,
            scope=SCOPE_WEBSITE,
            target_type="media_asset",
            target_id=str(asset.id),
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
            details={"fields": changed},
            commit=False,
        )
    db.commit()
    db.refresh(asset)
    return asset


@router.delete("/media/{asset_id}", status_code=204)
def delete_media(
    asset_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
):
    asset = db.get(MediaAsset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")

    # Best-effort: remove the file on disk only if no other asset
    # row references the same filename (defensive — uploads are dedupe-
    # keyed by hash so this shouldn't happen, but we keep the check).
    settings = get_settings()
    target = Path(settings.upload_dir) / "cms" / asset.filename
    other = db.execute(
        select(MediaAsset)
        .where(MediaAsset.filename == asset.filename, MediaAsset.id != asset.id)
    ).scalar_one_or_none()
    asset_id_val = asset.id
    asset_url = asset.url
    db.delete(asset)
    if other is None and target.exists():
        try:
            target.unlink()
        except OSError:
            pass

    ctx = get_request_context(request)
    record_audit(
        db,
        action="cms.media.delete",
        actor_id=user.id,
        actor_email=user.email,
        scope=SCOPE_WEBSITE,
        target_type="media_asset",
        target_id=str(asset_id_val),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"url": asset_url},
        commit=False,
    )
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Free-form CMS pages (Phase 5 follow-up)
# ---------------------------------------------------------------------------


@router.get("/pages", response_model=List[CMSPageListItem])
def list_pages(
    db: Session = Depends(get_db),
    include_drafts: bool = Query(default=True),
) -> List[CMSPage]:
    stmt = select(CMSPage).order_by(CMSPage.display_order, CMSPage.title)
    if not include_drafts:
        stmt = stmt.where(CMSPage.is_published.is_(True))
    return db.execute(stmt).scalars().all()


@router.get("/pages/{page_id}", response_model=CMSPageRead)
def get_page(page_id: int, db: Session = Depends(get_db)) -> CMSPage:
    page = db.get(CMSPage, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.post("/pages", response_model=CMSPageRead, status_code=201)
def create_page(
    payload: CMSPageCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> CMSPage:
    page = CMSPage(
        **payload.model_dump(),
        updated_by_id=user.id,
        published_at=(
            datetime.now(timezone.utc) if payload.is_published else None
        ),
    )
    db.add(page)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Page with slug '{payload.slug}' already exists.",
        ) from exc

    ctx = get_request_context(request)
    record_audit(
        db,
        action="cms.page.create",
        actor_id=user.id,
        actor_email=user.email,
        scope=SCOPE_WEBSITE,
        target_type="cms_page",
        target_id=str(page.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"slug": page.slug, "is_published": page.is_published},
        commit=False,
    )
    db.commit()
    db.refresh(page)
    return page


@router.patch("/pages/{page_id}", response_model=CMSPageRead)
def update_page(
    page_id: int,
    payload: CMSPageUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> CMSPage:
    page = db.get(CMSPage, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    updates = payload.model_dump(exclude_unset=True)
    changed: list[str] = []
    for field, value in updates.items():
        if isinstance(value, str):
            value = value.strip() or None
        if getattr(page, field) != value:
            setattr(page, field, value)
            changed.append(field)
    # Stamp published_at on first publish (and clear it on un-publish).
    if "is_published" in updates:
        if updates["is_published"] and page.published_at is None:
            page.published_at = datetime.now(timezone.utc)
        elif not updates["is_published"]:
            page.published_at = None
    if changed:
        page.updated_by_id = user.id
        ctx = get_request_context(request)
        record_audit(
            db,
            action="cms.page.update",
            actor_id=user.id,
            actor_email=user.email,
            scope=SCOPE_WEBSITE,
            target_type="cms_page",
            target_id=str(page.id),
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
            details={"fields": changed},
            commit=False,
        )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Another page with that slug already exists.",
        ) from exc
    db.refresh(page)
    return page


@router.delete("/pages/{page_id}", status_code=204)
def delete_page(
    page_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
):
    page = db.get(CMSPage, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    pid, slug = page.id, page.slug
    db.delete(page)

    ctx = get_request_context(request)
    record_audit(
        db,
        action="cms.page.delete",
        actor_id=user.id,
        actor_email=user.email,
        scope=SCOPE_WEBSITE,
        target_type="cms_page",
        target_id=str(pid),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"slug": slug},
        commit=False,
    )
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Navigation menu (Phase 5 follow-up)
# ---------------------------------------------------------------------------


def _build_nav_tree(rows: list[NavigationItem]) -> list[NavigationItemTreeRead]:
    """Turn a flat list of rows into a 2-level tree, top-level first."""
    top = [row for row in rows if row.parent_id is None]
    top.sort(key=lambda r: (r.display_order, r.id))
    out: list[NavigationItemTreeRead] = []
    for parent in top:
        children = sorted(
            (row for row in rows if row.parent_id == parent.id),
            key=lambda r: (r.display_order, r.id),
        )
        out.append(
            NavigationItemTreeRead(
                id=parent.id,
                parent_id=None,
                label=parent.label,
                href=parent.href,
                description=parent.description,
                mega_kind=parent.mega_kind,
                open_in_new_tab=parent.open_in_new_tab,
                display_order=parent.display_order,
                is_active=parent.is_active,
                children=[
                    NavigationItemTreeRead(
                        id=c.id,
                        parent_id=c.parent_id,
                        label=c.label,
                        href=c.href,
                        description=c.description,
                        mega_kind=c.mega_kind,
                        open_in_new_tab=c.open_in_new_tab,
                        display_order=c.display_order,
                        is_active=c.is_active,
                        children=[],
                    )
                    for c in children
                ],
            )
        )
    return out


@router.get("/navigation", response_model=List[NavigationItemTreeRead])
def list_navigation(
    db: Session = Depends(get_db),
    include_inactive: bool = True,
) -> list[NavigationItemTreeRead]:
    """Admin tree view — includes inactive items by default so admins
    can see what's currently disabled."""
    stmt = select(NavigationItem)
    if not include_inactive:
        stmt = stmt.where(NavigationItem.is_active.is_(True))
    rows = list(db.execute(stmt).scalars())
    return _build_nav_tree(rows)


@router.post(
    "/navigation",
    response_model=NavigationItemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_navigation_item(
    payload: NavigationItemCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> NavigationItem:
    if payload.parent_id is not None:
        parent = db.get(NavigationItem, payload.parent_id)
        if parent is None:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown parent_id {payload.parent_id}",
            )
        if parent.parent_id is not None:
            raise HTTPException(
                status_code=422,
                detail="Navigation supports a single level of nesting.",
            )
    item = NavigationItem(**payload.model_dump())
    db.add(item)
    db.flush()
    ctx = get_request_context(request)
    record_audit(
        db,
        action="cms.navigation.create",
        actor_id=user.id,
        actor_email=user.email,
        scope=SCOPE_WEBSITE,
        target_type="navigation_item",
        target_id=str(item.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"label": item.label, "href": item.href},
        commit=False,
    )
    db.commit()
    db.refresh(item)
    return item


@router.patch(
    "/navigation/{item_id}", response_model=NavigationItemRead
)
def update_navigation_item(
    item_id: int,
    payload: NavigationItemUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> NavigationItem:
    item = db.get(NavigationItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Navigation item not found")
    changes = payload.model_dump(exclude_unset=True)
    if "parent_id" in changes and changes["parent_id"] is not None:
        if changes["parent_id"] == item.id:
            raise HTTPException(
                status_code=422, detail="An item can't be its own parent."
            )
        parent = db.get(NavigationItem, changes["parent_id"])
        if parent is None:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown parent_id {changes['parent_id']}",
            )
        if parent.parent_id is not None:
            raise HTTPException(
                status_code=422,
                detail="Navigation supports a single level of nesting.",
            )
        if item.children:
            raise HTTPException(
                status_code=422,
                detail=(
                    "This item has children. Detach or delete them before "
                    "moving it under another parent."
                ),
            )
    for k, v in changes.items():
        setattr(item, k, v)
    ctx = get_request_context(request)
    record_audit(
        db,
        action="cms.navigation.update",
        actor_id=user.id,
        actor_email=user.email,
        scope=SCOPE_WEBSITE,
        target_type="navigation_item",
        target_id=str(item.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"changed_keys": list(changes.keys())},
        commit=False,
    )
    db.commit()
    db.refresh(item)
    return item


@router.delete(
    "/navigation/{item_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_navigation_item(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> Response:
    item = db.get(NavigationItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Navigation item not found")
    label = item.label
    db.delete(item)
    ctx = get_request_context(request)
    record_audit(
        db,
        action="cms.navigation.delete",
        actor_id=user.id,
        actor_email=user.email,
        scope=SCOPE_WEBSITE,
        target_type="navigation_item",
        target_id=str(item_id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"label": label},
        commit=False,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Trusted Brands (homepage showcase)
# ---------------------------------------------------------------------------


from app.models.cms import TrustedBrand  # noqa: E402  (sibling import)
from app.schemas.cms import (  # noqa: E402
    TrustedBrandCreate,
    TrustedBrandRead,
    TrustedBrandUpdate,
)


@router.get("/brands", response_model=List[TrustedBrandRead])
def list_brands(db: Session = Depends(get_db)) -> List[TrustedBrand]:
    return (
        db.execute(
            select(TrustedBrand).order_by(TrustedBrand.display_order, TrustedBrand.id)
        )
        .scalars()
        .all()
    )


@router.post(
    "/brands",
    response_model=TrustedBrandRead,
    status_code=status.HTTP_201_CREATED,
)
def create_brand(
    payload: TrustedBrandCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> TrustedBrand:
    brand = TrustedBrand(**payload.model_dump())
    db.add(brand)
    db.flush()
    _audit(
        db,
        user,
        request,
        action="cms.brand.create",
        target_type="brand",
        target_id=brand.id,
        details={"brand_name": brand.brand_name},
    )
    db.commit()
    db.refresh(brand)
    return brand


@router.patch("/brands/{brand_id}", response_model=TrustedBrandRead)
def update_brand(
    brand_id: int,
    payload: TrustedBrandUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> TrustedBrand:
    brand = db.get(TrustedBrand, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(brand, k, v)
    _audit(
        db,
        user,
        request,
        action="cms.brand.update",
        target_type="brand",
        target_id=brand.id,
        details={"changed_keys": list(changes.keys())},
    )
    db.commit()
    db.refresh(brand)
    return brand


@router.delete("/brands/{brand_id}")
def delete_brand(
    brand_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> Response:
    brand = db.get(TrustedBrand, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    db.delete(brand)
    _audit(
        db,
        user,
        request,
        action="cms.brand.delete",
        target_type="brand",
        target_id=brand_id,
        details={"brand_name": brand.brand_name},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Predefined site pages — about, companies, careers, contact, news, media
# ---------------------------------------------------------------------------


def _validate_page_key(page_key: str) -> str:
    """Reject unknown page keys so admins can't silently create orphan rows."""
    key = page_key.strip().lower()
    if key not in SITE_PAGE_KEYS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown site page '{page_key}'.",
        )
    return key


def _get_or_create_site_page(db: Session, page_key: str) -> SitePage:
    page = db.execute(
        select(SitePage).where(SitePage.page_key == page_key)
    ).scalar_one_or_none()
    if page is None:
        # Lazy-create so admins of installations that pre-date the
        # 20260525_0019 seed step still get a writable row.
        page = SitePage(page_key=page_key, sections={})
        db.add(page)
        db.commit()
        db.refresh(page)
    return page


@router.get("/site-pages", response_model=List[SitePageRead])
def list_site_pages(db: Session = Depends(get_db)) -> List[SitePage]:
    """Every known site page (one row per key). Missing rows are
    created on the fly so the admin UI always has something to render."""
    return [_get_or_create_site_page(db, k) for k in SITE_PAGE_KEYS]


@router.get("/site-pages/{page_key}", response_model=SitePageRead)
def get_site_page(
    page_key: str,
    db: Session = Depends(get_db),
) -> SitePage:
    return _get_or_create_site_page(db, _validate_page_key(page_key))


@router.put("/site-pages/{page_key}", response_model=SitePageRead)
def update_site_page(
    page_key: str,
    payload: SitePageUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> SitePage:
    key = _validate_page_key(page_key)
    page = _get_or_create_site_page(db, key)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(page, field, value)
    page.updated_by_id = user.id
    _audit(
        db,
        user,
        request,
        action="cms.site_page.update",
        target_type="site_page",
        target_id=key,
        details={"changed_keys": list(changes.keys())},
    )
    db.commit()
    db.refresh(page)
    return page

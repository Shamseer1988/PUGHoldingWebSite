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
    Company,
    CompanyService,
    ContactMessage,
    HeroSlide,
    LeadershipMessage,
    NewsItem,
    NewsletterSubscriber,
    SiteSetting,
)
from app.schemas.cms import (
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
    NewsCreate,
    NewsRead,
    NewsUpdate,
    NewsletterSubscriberRead,
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
    company = Company(**data)
    for i, name in enumerate(service_names):
        company.services.append(CompanyService(name=name, display_order=i))
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
    for k, v in changes.items():
        setattr(company, k, v)
    if service_names is not None:
        company.services.clear()
        for i, name in enumerate(service_names):
            company.services.append(CompanyService(name=name, display_order=i))
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already exists") from exc
    _audit(
        db,
        user,
        request,
        action="cms.company.update",
        target_type="company",
        target_id=company.id,
        details={"changed_keys": list(changes.keys()) + (["services"] if service_names is not None else [])},
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

"""Public read-only + form-submission endpoints.

These endpoints are unauthenticated and consumed directly by the public
website. All read endpoints filter to active / published rows only.
Form submission endpoints write to the same tables the admin manages.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context
from app.core.database import get_db
from app.models.cms import (
    Company,
    HeroSlide,
    LeadershipMessage,
    NewsItem,
    NewsletterSubscriber,
    SiteSetting,
)
from app.schemas.cms import (
    CompanyRead,
    ContactMessageRead,
    ContactSubmit,
    FeaturedCompaniesSectionResponse,
    FeaturedSection,
    HeroSlideRead,
    LeadershipRead,
    NewsRead,
    NewsletterSubscribe,
    NewsletterSubscriberRead,
    SiteSettingRead,
)
from app.services.audit_log import record_audit


router = APIRouter(prefix="/public", tags=["Public"])


# ---------------------------------------------------------------------------
# Read: hero slides
# ---------------------------------------------------------------------------


@router.get("/hero-slides", response_model=List[HeroSlideRead])
def list_active_hero_slides(db: Session = Depends(get_db)) -> List[HeroSlide]:
    return (
        db.execute(
            select(HeroSlide)
            .where(HeroSlide.is_active.is_(True))
            .order_by(HeroSlide.display_order, HeroSlide.id)
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# Read: companies
# ---------------------------------------------------------------------------


@router.get("/companies", response_model=List[CompanyRead])
def list_active_companies(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(
        default=None, pattern=r"^(distribution|retail|services)$"
    ),
) -> List[Company]:
    stmt = (
        select(Company)
        .where(Company.is_active.is_(True))
        .order_by(Company.display_order, Company.id)
    )
    if category:
        stmt = stmt.where(Company.category == category)
    return db.execute(stmt).scalars().all()


@router.get("/companies/{slug}", response_model=CompanyRead)
def get_active_company(slug: str, db: Session = Depends(get_db)) -> Company:
    company = (
        db.execute(
            select(Company).where(Company.slug == slug, Company.is_active.is_(True))
        )
        .scalars()
        .first()
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


# ---------------------------------------------------------------------------
# Read: leadership
# ---------------------------------------------------------------------------


@router.get("/leadership", response_model=List[LeadershipRead])
def list_active_leadership(db: Session = Depends(get_db)) -> List[LeadershipMessage]:
    return (
        db.execute(
            select(LeadershipMessage)
            .where(LeadershipMessage.is_active.is_(True))
            .order_by(LeadershipMessage.display_order, LeadershipMessage.id)
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------------------
# Read: news
# ---------------------------------------------------------------------------


@router.get("/news", response_model=List[NewsRead])
def list_published_news(
    db: Session = Depends(get_db),
    featured: Optional[bool] = Query(default=None),
    limit: Optional[int] = Query(default=None, ge=1, le=100),
) -> List[NewsItem]:
    stmt = (
        select(NewsItem)
        .where(NewsItem.is_published.is_(True))
        .order_by(desc(NewsItem.published_at), desc(NewsItem.id))
    )
    if featured is True:
        stmt = stmt.where(NewsItem.is_featured.is_(True))
    elif featured is False:
        stmt = stmt.where(NewsItem.is_featured.is_(False))
    if limit:
        stmt = stmt.limit(limit)
    return db.execute(stmt).scalars().all()


@router.get("/news/{slug}", response_model=NewsRead)
def get_published_news(slug: str, db: Session = Depends(get_db)) -> NewsItem:
    item = (
        db.execute(
            select(NewsItem).where(
                NewsItem.slug == slug, NewsItem.is_published.is_(True)
            )
        )
        .scalars()
        .first()
    )
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")
    return item


# ---------------------------------------------------------------------------
# Read: site settings
# ---------------------------------------------------------------------------


@router.get("/site-settings", response_model=SiteSettingRead)
def get_site_settings(db: Session = Depends(get_db)) -> SiteSetting:
    settings = db.get(SiteSetting, 1)
    if settings is None:
        # Return a transient default so the frontend always has values
        # to render — admin's first save creates the row. Pass all
        # NOT NULL columns explicitly because SQLAlchemy doesn't apply
        # column defaults to uncommitted instances.
        return SiteSetting(
            id=1,
            site_name="Paris United Group Holding",
            featured_companies_enabled=True,
            featured_companies_animation_enabled=True,
        )
    return settings


# ---------------------------------------------------------------------------
# Featured-companies homepage section
# ---------------------------------------------------------------------------


@router.get(
    "/featured-companies-section",
    response_model=FeaturedCompaniesSectionResponse,
)
def get_featured_companies_section(
    db: Session = Depends(get_db),
) -> FeaturedCompaniesSectionResponse:
    """Return the section settings + active highlighted companies.

    Falls back gracefully when site_settings has no row yet, and when
    no company is flagged ``is_highlighted`` (returns every active
    company, ordered by display_order).
    """
    settings = db.get(SiteSetting, 1)

    section = FeaturedSection(
        enabled=(
            settings.featured_companies_enabled if settings is not None else True
        ),
        eyebrow=(settings.featured_companies_eyebrow if settings else None)
        or "Group companies",
        title=(settings.featured_companies_title if settings else None)
        or "A diversified portfolio, one trusted group.",
        subtitle=(settings.featured_companies_subtitle if settings else None)
        or "Scroll to explore the businesses powering Paris United Group across "
        "retail, distribution, and services.",
        cta_label=(settings.featured_companies_cta_label if settings else None)
        or "View all companies",
        cta_url=(settings.featured_companies_cta_url if settings else None)
        or "/companies",
        animation_enabled=(
            settings.featured_companies_animation_enabled if settings else True
        ),
    )

    # Highlighted + active first; if none are highlighted, fall back to
    # every active company so the section still has content.
    highlighted = (
        db.execute(
            select(Company)
            .where(Company.is_active.is_(True), Company.is_highlighted.is_(True))
            .order_by(Company.display_order, Company.created_at)
        )
        .scalars()
        .all()
    )
    if not highlighted:
        highlighted = (
            db.execute(
                select(Company)
                .where(Company.is_active.is_(True))
                .order_by(Company.display_order, Company.created_at)
                .limit(6)
            )
            .scalars()
            .all()
        )

    return FeaturedCompaniesSectionResponse(
        section=section,
        companies=[CompanyRead.model_validate(c) for c in highlighted],
    )


# ---------------------------------------------------------------------------
# Write: contact form
# ---------------------------------------------------------------------------


@router.post(
    "/contact",
    response_model=ContactMessageRead,
    status_code=201,
)
def submit_contact_message(
    payload: ContactSubmit,
    request: Request,
    db: Session = Depends(get_db),
) -> ContactMessageRead:
    """Persist a contact form submission and audit it."""
    message = create_contact_message(db, payload, request=request)
    return ContactMessageRead.model_validate(message)


def create_contact_message(
    db: Session,
    payload: ContactSubmit,
    *,
    request: Request,
):
    from app.models.cms import ContactMessage

    ctx = get_request_context(request)
    msg = ContactMessage(
        name=payload.name.strip(),
        email=str(payload.email).strip().lower(),
        phone=payload.phone,
        department=payload.department,
        subject=payload.subject,
        message=payload.message,
    )
    db.add(msg)
    db.flush()

    record_audit(
        db,
        action="public.contact.submit",
        actor_email=msg.email,
        scope="website",
        target_type="contact_message",
        target_id=str(msg.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"department": payload.department},
        commit=False,
    )
    db.commit()
    db.refresh(msg)
    return msg


# ---------------------------------------------------------------------------
# Write: newsletter subscription
# ---------------------------------------------------------------------------


@router.post(
    "/newsletter",
    response_model=NewsletterSubscriberRead,
    status_code=201,
)
def subscribe_to_newsletter(
    payload: NewsletterSubscribe,
    request: Request,
    db: Session = Depends(get_db),
) -> NewsletterSubscriberRead:
    """Add an email to the newsletter list.

    Re-subscribing an existing (but inactive) email re-activates it.
    Returns 200-equivalent payload either way so the frontend doesn't
    leak whether an email was already subscribed.
    """
    email = str(payload.email).strip().lower()
    ctx = get_request_context(request)

    existing = (
        db.execute(
            select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
        )
        .scalars()
        .first()
    )
    if existing is not None:
        if not existing.is_active:
            existing.is_active = True
            db.flush()
        record_audit(
            db,
            action="public.newsletter.resubscribe",
            actor_email=email,
            scope="website",
            target_type="subscriber",
            target_id=str(existing.id),
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
            commit=False,
        )
        db.commit()
        db.refresh(existing)
        return NewsletterSubscriberRead.model_validate(existing)

    subscriber = NewsletterSubscriber(email=email, is_active=True)
    db.add(subscriber)
    try:
        db.flush()
    except IntegrityError:
        # Race condition: another request inserted same email between
        # the SELECT and the INSERT. Fall back to fetching the row.
        db.rollback()
        existing = (
            db.execute(
                select(NewsletterSubscriber).where(
                    NewsletterSubscriber.email == email
                )
            )
            .scalars()
            .one()
        )
        return NewsletterSubscriberRead.model_validate(existing)

    record_audit(
        db,
        action="public.newsletter.subscribe",
        actor_email=email,
        scope="website",
        target_type="subscriber",
        target_id=str(subscriber.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        commit=False,
    )
    db.commit()
    db.refresh(subscriber)
    return NewsletterSubscriberRead.model_validate(subscriber)

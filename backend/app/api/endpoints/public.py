"""Public read-only + form-submission endpoints.

These endpoints are unauthenticated and consumed directly by the public
website. All read endpoints filter to active / published rows only.
Form submission endpoints write to the same tables the admin manages.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context
from app.core.database import get_db
from app.core.rate_limit import (
    rate_limit_ai_assistant,
    rate_limit_apply,
    rate_limit_contact,
    rate_limit_newsletter,
)
from app.models.cms import (
    CMSPage,
    Company,
    HeroSlide,
    LeadershipMessage,
    MediaAsset,
    NavigationItem,
    NewsItem,
    NewsletterSubscriber,
    SiteSetting,
    TrustedBrand,
)
from app.models.hr_ats import JOB_STATUS_OPEN, JobOpening
from app.schemas.cms import (
    CMSPageRead,
    CompanyRead,
    ContactMessageRead,
    ContactSubmit,
    FeaturedCompaniesSectionResponse,
    FeaturedSection,
    HeroSlideRead,
    HomepageLeadershipResponse,
    HomepageTrustedBrand,
    HomepageTrustedBrandsResponse,
    LeadershipMessageCardRead,
    LeadershipRead,
    MediaAssetRead,
    NavigationItemTreeRead,
    NewsRead,
    NewsletterSubscribe,
    NewsletterSubscriberRead,
    SiteSettingRead,
)
from app.schemas.hr_ats import (
    ApplicationSubmissionResponse,
    JobOpeningRead,
    PublicAIAskRequest,
    PublicAIAskResponse,
)
from app.ai.public_assistant import answer_question, log_query
from app.services.candidate_intake import (
    DuplicateApplicationError,
    IntakeForm,
    ingest_candidate_application,
)
from app.services.cv_storage import CvUploadError, store_cv_bytes
from app.models.hr_ats import SOURCE_PUBLIC_FORM
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
# Read: navigation (Phase 5 follow-up)
# ---------------------------------------------------------------------------


@router.get("/navigation", response_model=List[NavigationItemTreeRead])
def list_public_navigation(
    db: Session = Depends(get_db),
) -> List[NavigationItemTreeRead]:
    """Active items only, two-level tree, sorted by display_order.

    Returns an empty list when no rows are persisted — the frontend
    detects this and falls back to its compiled-in default menu, so
    the public site never renders an empty navbar.
    """
    rows = list(
        db.execute(
            select(NavigationItem).where(NavigationItem.is_active.is_(True))
        ).scalars()
    )
    parent_rows = [r for r in rows if r.parent_id is None]
    parent_rows.sort(key=lambda r: (r.display_order, r.id))

    out: list[NavigationItemTreeRead] = []
    for parent in parent_rows:
        children = sorted(
            (r for r in rows if r.parent_id == parent.id),
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
# Homepage Leadership Messages (unified section)
# ---------------------------------------------------------------------------


def _role_type_for(message: LeadershipMessage) -> str:
    """Best-effort role_type bucketing for the homepage card.

    Slugs ``chairman`` / ``md`` map directly; anything else gets a
    sensible fallback derived from the role string.
    """
    slug = (message.slug or "").lower()
    if slug == "chairman":
        return "chairman"
    if slug == "md":
        return "md"
    role = (message.role or "").lower()
    if "chairman" in role or "founder" in role:
        return "chairman"
    if "managing director" in role or role.startswith("md "):
        return "md"
    return slug or "other"


def _serialize_homepage_card(
    message: LeadershipMessage,
) -> LeadershipMessageCardRead:
    return LeadershipMessageCardRead(
        slug=message.slug,
        role_type=_role_type_for(message),
        role_label=message.role_label,
        name=message.name,
        role=message.role,
        designation=message.role,
        initials=message.initials,
        accent=message.accent,
        photo_url=message.photo_url,
        signature_image_url=message.signature_image_url,
        signature=message.signature,
        highlight_quote=message.highlight_quote or message.short_message,
        message_paragraph_1=message.message_paragraph_1 or message.full_message,
        message_paragraph_2=message.message_paragraph_2,
        cta_label=message.cta_label,
        cta_url=message.cta_url,
        display_order=message.display_order,
        is_active=message.is_active,
    )


@router.get(
    "/homepage/leadership-messages",
    response_model=HomepageLeadershipResponse,
)
def get_homepage_leadership(
    db: Session = Depends(get_db),
) -> HomepageLeadershipResponse:
    """Section settings + the two leadership cards flagged for the homepage."""
    settings = db.get(SiteSetting, 1)

    enabled = True
    eyebrow: Optional[str] = "Leadership messages"
    title: Optional[str] = "Guided by vision, driven ((by excellence))"
    subtitle: Optional[str] = (
        "A message from the leadership of Paris United Group Holding."
    )
    animation_enabled = True

    if settings is not None:
        enabled = settings.home_leadership_section_enabled
        eyebrow = settings.home_leadership_section_eyebrow or eyebrow
        title = settings.home_leadership_section_title or title
        subtitle = settings.home_leadership_section_subtitle or subtitle
        animation_enabled = settings.home_leadership_animation_enabled

    messages = (
        db.execute(
            select(LeadershipMessage)
            .where(
                LeadershipMessage.is_homepage_featured.is_(True),
                LeadershipMessage.is_active.is_(True),
            )
            .order_by(LeadershipMessage.display_order, LeadershipMessage.id)
        )
        .scalars()
        .all()
    )

    return HomepageLeadershipResponse(
        enabled=enabled,
        eyebrow=eyebrow,
        title=title,
        subtitle=subtitle,
        animation_enabled=animation_enabled,
        messages=[_serialize_homepage_card(m) for m in messages],
    )


# ---------------------------------------------------------------------------
# Homepage Trusted Brands showcase
# ---------------------------------------------------------------------------

_ALLOWED_BRAND_LAYOUTS = {"marquee", "grid", "carousel"}


@router.get(
    "/homepage/trusted-brands",
    response_model=HomepageTrustedBrandsResponse,
)
def get_homepage_trusted_brands(
    db: Session = Depends(get_db),
) -> HomepageTrustedBrandsResponse:
    """Section settings + active trusted-brand rows for the homepage.

    The frontend uses ``layout_mode`` ("marquee", "grid", or
    "carousel") to pick a presentation. We only ship active rows so
    a draft brand never accidentally renders.
    """
    settings = db.get(SiteSetting, 1)

    enabled = True
    eyebrow: Optional[str] = "Trusted brands we work with"
    title: Optional[str] = "Trusted by strong brands"
    subtitle: Optional[str] = None
    animation_enabled = True
    layout_mode = "marquee"

    if settings is not None:
        enabled = settings.home_brand_section_enabled
        eyebrow = settings.home_brand_eyebrow or eyebrow
        title = (
            settings.home_brand_title
            or settings.home_brand_strip_title  # backwards-compat
            or title
        )
        subtitle = settings.home_brand_subtitle or subtitle
        animation_enabled = settings.home_brand_animation_enabled
        candidate = (settings.home_brand_layout_mode or "marquee").strip().lower()
        if candidate in _ALLOWED_BRAND_LAYOUTS:
            layout_mode = candidate

    brands = (
        db.execute(
            select(TrustedBrand)
            .where(TrustedBrand.is_active.is_(True))
            .order_by(TrustedBrand.display_order, TrustedBrand.id)
        )
        .scalars()
        .all()
    )

    return HomepageTrustedBrandsResponse(
        enabled=enabled,
        eyebrow=eyebrow,
        title=title,
        subtitle=subtitle,
        animation_enabled=animation_enabled,
        layout_mode=layout_mode,
        brands=[
            HomepageTrustedBrand(
                id=b.id,
                brand_name=b.brand_name,
                logo_url=b.logo_url,
                logo_url_alt=b.logo_url_alt,
                link_url=b.link_url,
                category=b.category,
                is_highlight=b.is_highlight,
                display_order=b.display_order,
                is_active=b.is_active,
            )
            for b in brands
        ],
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
# Read: jobs (open only)
# ---------------------------------------------------------------------------


@router.get("/jobs", response_model=List[JobOpeningRead])
def list_open_jobs(
    db: Session = Depends(get_db),
    department: Optional[str] = None,
    company: Optional[str] = None,
    location: Optional[str] = None,
    employment_type: Optional[str] = Query(
        default=None, pattern=r"^(full_time|part_time|contract)$"
    ),
    q: Optional[str] = Query(default=None, max_length=200),
) -> List[JobOpening]:
    stmt = (
        select(JobOpening)
        .where(JobOpening.status == JOB_STATUS_OPEN)
        .order_by(desc(JobOpening.posted_at), JobOpening.id)
    )
    if department:
        stmt = stmt.where(JobOpening.department == department)
    if company:
        stmt = stmt.where(JobOpening.company == company)
    if location:
        stmt = stmt.where(JobOpening.location == location)
    if employment_type:
        stmt = stmt.where(JobOpening.employment_type == employment_type)
    if q:
        from sqlalchemy import func

        like = f"%{q.lower()}%"
        stmt = stmt.where(
            (func.lower(JobOpening.title).like(like))
            | (func.lower(JobOpening.required_skills).like(like))
            | (func.lower(JobOpening.preferred_skills).like(like))
        )
    return db.execute(stmt).scalars().all()


@router.get("/jobs/{slug}", response_model=JobOpeningRead)
def get_open_job(slug: str, db: Session = Depends(get_db)) -> JobOpening:
    job = (
        db.execute(
            select(JobOpening).where(
                JobOpening.slug == slug, JobOpening.status == JOB_STATUS_OPEN
            )
        )
        .scalars()
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------------------------
# Read: site settings
# ---------------------------------------------------------------------------


@router.get("/pages", response_model=List[CMSPageRead])
def list_public_pages(db: Session = Depends(get_db)) -> List[CMSPage]:
    return (
        db.execute(
            select(CMSPage)
            .where(CMSPage.is_published.is_(True))
            .order_by(CMSPage.display_order, CMSPage.title)
        )
        .scalars()
        .all()
    )


@router.get("/pages/{slug}", response_model=CMSPageRead)
def get_public_page(slug: str, db: Session = Depends(get_db)) -> CMSPage:
    page = db.execute(
        select(CMSPage).where(
            CMSPage.slug == slug, CMSPage.is_published.is_(True)
        )
    ).scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.get("/media", response_model=List[MediaAssetRead])
def list_public_media(
    db: Session = Depends(get_db),
    kind: Optional[str] = Query(default=None, max_length=16),
    tag: Optional[str] = Query(
        default=None,
        max_length=120,
        description=(
            "Case-insensitive token match against the asset's "
            "comma-separated `tags` field. Use a company slug "
            "(e.g. `paris-food-international`) or a category like "
            "`stores`, `events`, `team`, `campaigns`."
        ),
    ),
    limit: int = Query(default=60, ge=1, le=200),
) -> List[MediaAsset]:
    """Read-only gallery feed used by every public surface that shows
    uploaded images / videos (the public Media page + per-company
    galleries)."""
    stmt = (
        select(MediaAsset)
        .order_by(desc(MediaAsset.created_at))
        .limit(limit)
    )
    if kind:
        stmt = stmt.where(MediaAsset.kind == kind)
    if tag:
        # `tags` is a free-form comma-separated string. Match the
        # token at any position without bleeding into longer words
        # (so `team` matches `team,doha` and `stores,team` but NOT
        # `teammate` or `stores,teamwork`). Stripping whitespace +
        # lower-casing the column on the fly keeps the match
        # case-insensitive and tolerant of "stores, team" vs
        # "stores,team". Stays dialect-agnostic for SQLite + PG.
        needle = tag.strip().lower()
        if needle:
            normalised = func.lower(
                func.replace(func.coalesce(MediaAsset.tags, ""), " ", "")
            )
            stmt = stmt.where(
                or_(
                    normalised == needle,
                    normalised.like(f"{needle},%"),
                    normalised.like(f"%,{needle}"),
                    normalised.like(f"%,{needle},%"),
                )
            )
    return db.execute(stmt).scalars().all()


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
            home_leadership_section_enabled=True,
            home_leadership_animation_enabled=True,
            home_brand_section_enabled=True,
            home_brand_animation_enabled=True,
            home_brand_layout_mode="marquee",
            maintenance_mode_enabled=False,
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
        or "A diversified portfolio, ((one trusted group.))",
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
    dependencies=[Depends(rate_limit_contact)],
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
    dependencies=[Depends(rate_limit_newsletter)],
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


# ---------------------------------------------------------------------------
# Write: candidate application from the public Apply form
# ---------------------------------------------------------------------------


@router.post(
    "/candidate-applications",
    response_model=ApplicationSubmissionResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_apply)],
)
async def submit_candidate_application(
    request: Request,
    db: Session = Depends(get_db),
    file: UploadFile = File(..., description="CV file (PDF / DOC / DOCX / image)"),
    full_name: str = Form(..., min_length=1, max_length=255),
    email: str = Form(..., min_length=3, max_length=255),
    mobile: str = Form(..., min_length=4, max_length=40),
    job_slug: Optional[str] = Form(default=None, max_length=200),
    nationality: Optional[str] = Form(default=None, max_length=120),
    current_location: Optional[str] = Form(default=None, max_length=255),
    total_experience_years: Optional[float] = Form(default=None, ge=0, le=70),
    expected_salary: Optional[int] = Form(default=None, ge=0),
    notice_period: Optional[str] = Form(default=None, max_length=120),
    cover_letter: Optional[str] = Form(default=None, max_length=5000),
    consent: bool = Form(...),
) -> ApplicationSubmissionResponse:
    """Public candidate application: stores CV, dedupes, creates intake."""
    if not consent:
        raise HTTPException(
            status_code=400, detail="Consent is required to submit an application."
        )

    payload = await file.read()
    try:
        meta = store_cv_bytes(payload, file.filename or "cv", file.content_type)
    except CvUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    form = IntakeForm(
        full_name=full_name,
        email=email,
        mobile=mobile,
        nationality=nationality,
        current_location=current_location,
        total_experience_years=total_experience_years,
        expected_salary=expected_salary,
        notice_period=notice_period,
        cover_letter=cover_letter,
        job_slug=job_slug,
        source=SOURCE_PUBLIC_FORM,
    )

    try:
        result = ingest_candidate_application(db, form=form, file_meta=meta)
    except DuplicateApplicationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "You've already applied to this position. We'll get back to "
                "you on your existing application."
            ),
        ) from exc

    ctx = get_request_context(request)
    record_audit(
        db,
        action="public.candidate.apply",
        actor_email=email.strip().lower(),
        scope="hr",
        target_type="candidate_application",
        target_id=str(result.application.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "candidate_id": result.candidate.id,
            "job_slug": job_slug,
            "was_existing_candidate": result.was_existing_candidate,
            "file_hash": meta.file_hash,
        },
        commit=False,
    )
    db.commit()

    return ApplicationSubmissionResponse(
        candidate_id=result.candidate.id,
        application_id=result.application.id,
        was_existing_candidate=result.was_existing_candidate,
        job_title=(
            result.application.job_opening.title
            if result.application.job_opening is not None
            else None
        ),
        job_slug=(
            result.application.job_opening.slug
            if result.application.job_opening is not None
            else None
        ),
    )


# ---------------------------------------------------------------------------
# Public "Ask PUG AI" assistant
# ---------------------------------------------------------------------------


@router.post(
    "/ai-assistant/ask",
    response_model=PublicAIAskResponse,
    dependencies=[Depends(rate_limit_ai_assistant)],
)
def ask_pug_ai(
    payload: PublicAIAskRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PublicAIAskResponse:
    """Public chat endpoint — answers using CMS-only context.

    No auth; the client passes a `session_id` (any string up to 64 chars)
    so multi-turn conversations from the same visitor can be grouped in
    the usage log without requiring login.
    """
    history = [
        {"role": str(m.get("role", "")), "content": str(m.get("content", ""))}
        for m in (payload.history or [])
        if isinstance(m, dict)
    ]

    result = answer_question(
        db,
        question=payload.question,
        history=history,
    )

    ctx = get_request_context(request)
    log_query(
        db,
        question=payload.question,
        result=result,
        session_id=payload.session_id,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
    )

    return PublicAIAskResponse(
        answer=result.answer,
        mode=result.mode,
        was_fallback=result.was_fallback,
        session_id=payload.session_id,
        model_name=result.model_name,
    )


# ---------------------------------------------------------------------------
# SEO Configuration — public surface (Phase 1)
# ---------------------------------------------------------------------------
#
# The public Next.js layout consumes these four endpoints to render
# the SEO `<head>`, the HTML verification file route, and the
# `/sitemap.xml` + `/robots.txt` content. No admin authentication —
# they're meant to be cached at the edge.

from fastapi.responses import PlainTextResponse  # noqa: E402

from app.models.seo import (  # noqa: E402
    SeoSetting,
    SeoVerification,
    TrackingIntegration,
    VERIFICATION_TYPE_HTML_FILE,
)
from app.schemas.seo import PublicSeoHeadFeed  # noqa: E402
from app.services.seo import (  # noqa: E402
    build_robots_txt,
    find_active_verification_file,
    public_integrations,
    public_verification_metas,
)


def _seo_settings_or_default(db: Session) -> Optional[SeoSetting]:
    """Return the singleton SeoSetting row if it exists, else None.

    We deliberately don't lazy-create the row here — public endpoints
    should be read-only. The row materialises the first time an admin
    edits SEO settings.
    """
    return (
        db.execute(select(SeoSetting).order_by(SeoSetting.id))
        .scalars()
        .first()
    )


@router.get("/seo/head", response_model=PublicSeoHeadFeed)
def public_seo_head(db: Session = Depends(get_db)) -> PublicSeoHeadFeed:
    """Bundle of everything the public layout needs for the SEO `<head>`.

    The Next.js root layout fetches this once and renders verification
    meta tags + tracking scripts. Inactive rows are filtered out
    server-side so the response only carries what should actually
    render.
    """
    settings = _seo_settings_or_default(db)
    verifications = (
        db.execute(select(SeoVerification).where(SeoVerification.is_active.is_(True)))
        .scalars()
        .all()
    )
    integrations = (
        db.execute(select(TrackingIntegration).where(TrackingIntegration.is_active.is_(True)))
        .scalars()
        .all()
    )
    return PublicSeoHeadFeed(
        site_name=settings.site_name if settings else None,
        default_meta_title=settings.default_meta_title if settings else None,
        default_meta_description=settings.default_meta_description if settings else None,
        canonical_base_url=settings.canonical_base_url if settings else None,
        default_language=settings.default_language if settings else None,
        enable_canonical=settings.enable_canonical if settings else True,
        enable_open_graph=settings.enable_open_graph if settings else True,
        enable_twitter_cards=settings.enable_twitter_cards if settings else True,
        default_og_image=settings.default_og_image if settings else None,
        default_twitter_image=settings.default_twitter_image if settings else None,
        enable_sitemap=settings.enable_sitemap if settings else True,
        sitemap_include_static=settings.sitemap_include_static if settings else True,
        sitemap_include_companies=settings.sitemap_include_companies if settings else True,
        sitemap_include_cms_pages=settings.sitemap_include_cms_pages if settings else True,
        sitemap_include_news=settings.sitemap_include_news if settings else True,
        sitemap_default_changefreq=settings.sitemap_default_changefreq if settings else None,
        sitemap_default_priority=settings.sitemap_default_priority if settings else None,
        verification_metas=public_verification_metas(verifications),
        integrations=public_integrations(integrations),
    )


@router.get(
    "/seo/verify/{filename}",
    response_class=PlainTextResponse,
    responses={
        200: {"content": {"text/plain": {}}},
        404: {"description": "No active verification file with that name"},
    },
)
def public_seo_verify_file(
    filename: str, db: Session = Depends(get_db)
) -> PlainTextResponse:
    """Serve the content of an active HTML / TXT verification file.

    Called via a Next.js rewrite at the site root, e.g.
    ``GET /googleXXX.html`` → ``GET /api/v1/public/seo/verify/googleXXX.html``.

    Filename validation runs again here so the route can never be
    coerced into serving anything outside the allow-list, even if a
    rewrite ever changes upstream.
    """
    # Reject any traversal / slash attempts immediately.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    rows = (
        db.execute(
            select(SeoVerification).where(
                SeoVerification.verification_type == VERIFICATION_TYPE_HTML_FILE,
                SeoVerification.is_active.is_(True),
                SeoVerification.html_filename == filename,
            )
        )
        .scalars()
        .all()
    )
    record = rows[0] if rows else None
    if record is None or not record.html_file_content:
        raise HTTPException(status_code=404, detail="Verification file not found")

    # Google's docs say `google*.html` should be served as text/plain.
    return PlainTextResponse(
        content=record.html_file_content,
        media_type="text/plain; charset=utf-8",
    )


@router.get(
    "/seo/robots",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/plain": {}}}},
)
def public_seo_robots(db: Session = Depends(get_db)) -> PlainTextResponse:
    """Return the rendered ``robots.txt`` body.

    The Next.js root layer at ``app/robots.ts`` calls this and returns
    the text verbatim, so admins can override the file without a
    redeploy.
    """
    settings = _seo_settings_or_default(db)
    return PlainTextResponse(
        content=build_robots_txt(settings),
        media_type="text/plain; charset=utf-8",
    )

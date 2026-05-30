"""Admin endpoints for the URL Shortener (Marketing → Tools).

Routes (all prefixed ``/admin/marketing/short-urls``):

    GET    /                 list (paginated, optional search)
    POST   /                 create (slug optional — auto if omitted)
    GET    /{id}             detail
    PATCH  /{id}             update target / title / is_active / expires_at
    DELETE /{id}             hard delete

Read endpoints accept either ``marketing:short_urls:read`` or
``marketing:short_urls:manage`` so a viewer role can browse without
write access. Write endpoints require ``:manage`` outright.

Every mutating call writes an audit-log row scoped to ``short_url``.
"""
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_request_context,
    require_any_permission,
    require_permission,
    require_website_admin,
)
from app.auth.permissions import (
    PERM_MARKETING_SHORT_URLS_MANAGE,
    PERM_MARKETING_SHORT_URLS_READ,
)
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.models.auth import User
from app.models.short_url import ShortUrl
from app.schemas.short_url import (
    ShortUrlCreate,
    ShortUrlListResponse,
    ShortUrlRead,
    ShortUrlUpdate,
)
from app.services.audit_log import record_audit


logger = get_logger(__name__)


router = APIRouter(
    prefix="/admin/marketing/short-urls",
    tags=["Admin - Short URLs"],
    dependencies=[Depends(require_website_admin)],
)


_VIEWER = require_any_permission(
    PERM_MARKETING_SHORT_URLS_READ, PERM_MARKETING_SHORT_URLS_MANAGE
)
_MANAGER = require_permission(PERM_MARKETING_SHORT_URLS_MANAGE)


# Slug autogen alphabet — lower-case + digits matches the SLUG_PATTERN
# the schema enforces, so a generated slug always passes validation.
_SLUG_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
_SLUG_LENGTH = 7
_SLUG_MAX_ATTEMPTS = 5


def _generate_unique_slug(db: Session) -> str:
    """Pick a 7-char slug that doesn't already exist.

    Five attempts is enough at 32^7 ≈ 34 billion entropy — even with
    a billion existing rows the per-attempt collision rate is < 3%,
    so the cumulative probability of all five failing is ~10^-8.
    """
    for _ in range(_SLUG_MAX_ATTEMPTS):
        candidate = "".join(
            secrets.choice(_SLUG_ALPHABET) for _ in range(_SLUG_LENGTH)
        )
        exists = db.execute(
            select(ShortUrl.id).where(ShortUrl.slug == candidate)
        ).first()
        if exists is None:
            return candidate
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not allocate a unique slug after several attempts; try again.",
    )


def _row_or_404(db: Session, short_url_id: int) -> ShortUrl:
    row = db.get(ShortUrl, short_url_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Short URL not found")
    return row


def _audit(
    db: Session,
    actor: User,
    request: Request,
    *,
    action: str,
    short_url: ShortUrl,
    details: Optional[dict] = None,
) -> None:
    ctx = get_request_context(request)
    record_audit(
        db,
        action=action,
        actor_id=actor.id,
        actor_email=actor.email,
        scope="website",
        target_type="short_url",
        target_id=str(short_url.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details=details,
        commit=False,
    )


# ---------------------------------------------------------------------------
# List + create
# ---------------------------------------------------------------------------


@router.get("", response_model=ShortUrlListResponse)
def list_short_urls(
    db: Session = Depends(get_db),
    actor: User = Depends(_VIEWER),  # noqa: ARG001 — guard only
    search: Optional[str] = Query(default=None, max_length=200),
    include_inactive: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ShortUrlListResponse:
    """Paginated list, newest first. Search matches slug + title + target."""
    where_clauses = []
    if not include_inactive:
        where_clauses.append(ShortUrl.is_active.is_(True))
    if search:
        needle = f"%{search.strip().lower()}%"
        where_clauses.append(
            or_(
                func.lower(ShortUrl.slug).like(needle),
                func.lower(ShortUrl.title).like(needle),
                func.lower(ShortUrl.target_url).like(needle),
            )
        )

    base = select(ShortUrl)
    if where_clauses:
        base = base.where(*where_clauses)

    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    rows = (
        db.execute(
            base.order_by(desc(ShortUrl.created_at)).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    return ShortUrlListResponse(
        items=[ShortUrlRead.model_validate(r) for r in rows],
        total=int(total),
    )


@router.post(
    "", response_model=ShortUrlRead, status_code=status.HTTP_201_CREATED
)
def create_short_url(
    payload: ShortUrlCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(_MANAGER),
) -> ShortUrlRead:
    """Create a short URL. Slug is auto-generated when omitted."""
    if payload.slug is None:
        slug = _generate_unique_slug(db)
    else:
        slug = payload.slug
        existing = db.execute(
            select(ShortUrl.id).where(ShortUrl.slug == slug)
        ).first()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Slug '{slug}' is already in use.",
            )

    row = ShortUrl(
        slug=slug,
        target_url=payload.target_url,
        title=payload.title,
        is_active=payload.is_active,
        expires_at=payload.expires_at,
        created_by_id=actor.id,
    )
    db.add(row)
    db.flush()  # populate row.id for audit log
    _audit(
        db,
        actor,
        request,
        action="short_url.create",
        short_url=row,
        details={"slug": row.slug, "target_url": row.target_url},
    )
    db.commit()
    db.refresh(row)
    return ShortUrlRead.model_validate(row)


# ---------------------------------------------------------------------------
# Detail + update + delete
# ---------------------------------------------------------------------------


@router.get("/{short_url_id}", response_model=ShortUrlRead)
def get_short_url(
    short_url_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(_VIEWER),  # noqa: ARG001 — guard only
) -> ShortUrlRead:
    row = _row_or_404(db, short_url_id)
    return ShortUrlRead.model_validate(row)


@router.patch("/{short_url_id}", response_model=ShortUrlRead)
def update_short_url(
    short_url_id: int,
    payload: ShortUrlUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(_MANAGER),
) -> ShortUrlRead:
    row = _row_or_404(db, short_url_id)
    changes: dict[str, object] = {}

    if payload.target_url is not None and payload.target_url != row.target_url:
        changes["target_url"] = (row.target_url, payload.target_url)
        row.target_url = payload.target_url
    if payload.title is not None and payload.title != row.title:
        changes["title"] = (row.title, payload.title)
        row.title = payload.title
    if payload.is_active is not None and payload.is_active != row.is_active:
        changes["is_active"] = (row.is_active, payload.is_active)
        row.is_active = payload.is_active
    if payload.expires_at is not None and payload.expires_at != row.expires_at:
        changes["expires_at"] = (
            row.expires_at.isoformat() if row.expires_at else None,
            payload.expires_at.isoformat(),
        )
        row.expires_at = payload.expires_at

    if changes:
        _audit(
            db,
            actor,
            request,
            action="short_url.update",
            short_url=row,
            details={"changes": {k: {"from": v[0], "to": v[1]} for k, v in changes.items()}},
        )
    db.commit()
    db.refresh(row)
    return ShortUrlRead.model_validate(row)


@router.delete(
    "/{short_url_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_short_url(
    short_url_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(_MANAGER),
) -> Response:
    row = _row_or_404(db, short_url_id)
    _audit(
        db,
        actor,
        request,
        action="short_url.delete",
        short_url=row,
        details={
            "slug": row.slug,
            "target_url": row.target_url,
            "click_count": row.click_count,
        },
    )
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

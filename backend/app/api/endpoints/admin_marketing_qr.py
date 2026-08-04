"""Admin endpoints for Divisions + branch QR codes (Marketing → QR Codes).

Routes:

    GET    /admin/marketing/divisions              list (QR codes nested)
    POST   /admin/marketing/divisions              create (+ primary QR)
    GET    /admin/marketing/divisions/{id}         detail
    PATCH  /admin/marketing/divisions/{id}         update
    DELETE /admin/marketing/divisions/{id}         delete (cascades to codes)

    POST   /admin/marketing/divisions/{id}/qr-codes  add a code
    GET    /admin/marketing/qr-codes/{id}            detail
    PATCH  /admin/marketing/qr-codes/{id}            re-point / rename / toggle
    DELETE /admin/marketing/qr-codes/{id}            delete
    GET    /admin/marketing/qr-codes/{id}/qr-code.png  rendered artwork
    GET    /admin/marketing/qr-codes/{id}/analytics    scan trend + history

Read endpoints accept either ``marketing:qr_codes:read`` or
``marketing:qr_codes:manage``; write endpoints require ``:manage``.

Every mutating call writes an audit-log row scoped to
``marketing_qr`` / ``marketing_division``. The QR rows' audit trail is
load-bearing rather than decorative: ``GET .../analytics`` reconstructs
the target-change history from it, so an operator can see what a
printed code pointed at during any past period.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import (
    get_request_context,
    require_any_permission,
    require_permission,
    require_website_admin,
)
from app.auth.permissions import (
    PERM_MARKETING_QR_CODES_MANAGE,
    PERM_MARKETING_QR_CODES_READ,
)
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.models.auth import AuditLog, User
from app.models.marketing_qr import (
    MarketingDivision,
    MarketingQrCode,
    MarketingQrScanEvent,
)
from app.schemas.marketing_qr import (
    DivisionCreate,
    DivisionListResponse,
    DivisionRead,
    DivisionStorefrontFields,
    DivisionUpdate,
    QrCodeAnalytics,
    QrCodeCreate,
    QrCodeRead,
    QrCodeUpdate,
    QrDeviceBreakdown,
    QrScanDailyPoint,
    QrTargetHistoryEntry,
)
from app.services.audit_log import record_audit


logger = get_logger(__name__)


router = APIRouter(
    prefix="/admin/marketing",
    tags=["Admin - Divisions & QR Codes"],
    dependencies=[Depends(require_website_admin)],
)


_VIEWER = require_any_permission(
    PERM_MARKETING_QR_CODES_READ, PERM_MARKETING_QR_CODES_MANAGE
)
_MANAGER = require_permission(PERM_MARKETING_QR_CODES_MANAGE)


# Audit action names — ``qr.target.update`` is queried by the analytics
# endpoint to rebuild target history, so renaming it silently empties
# that panel. Kept as module constants so the coupling is visible.
ACTION_QR_TARGET_UPDATE = "marketing.qr.target.update"
ACTION_QR_CREATE = "marketing.qr.create"
ACTION_QR_UPDATE = "marketing.qr.update"
ACTION_QR_DELETE = "marketing.qr.delete"
ACTION_DIVISION_CREATE = "marketing.division.create"
ACTION_DIVISION_UPDATE = "marketing.division.update"
ACTION_DIVISION_DELETE = "marketing.division.delete"

TARGET_TYPE_QR = "marketing_qr"
TARGET_TYPE_DIVISION = "marketing_division"

# Rendered QR sizes the endpoint will produce. 2048 is the print size
# (roughly 6.8" at 300 DPI); anything larger is wasted bytes because
# the underlying module grid doesn't gain detail.
ALLOWED_QR_SIZES = (512, 1024, 2048)

# Storefront columns copied verbatim between payload and row. Derived
# from the schema rather than hand-listed so a new field added to
# ``DivisionStorefrontFields`` flows through create AND update without
# a second edit here — the class that owns the shape stays the source
# of truth.
_STOREFRONT_FIELDS: tuple[str, ...] = tuple(
    DivisionStorefrontFields.model_fields.keys()
)


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------


def _slugify(value: str) -> str:
    """"Paris Hyper Market Al Khor" -> "paris-hyper-market-al-khor"."""
    lowered = (value or "").strip().lower()
    # Collapse anything that isn't a-z0-9 into single hyphens.
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "division"


def _unique_division_slug(db: Session, base: str, *, exclude_id: int | None = None) -> str:
    """Append ``-2``, ``-3``… until the division slug is free."""
    candidate = base[:120]
    suffix = 1
    while True:
        stmt = select(MarketingDivision.id).where(
            MarketingDivision.slug == candidate
        )
        if exclude_id is not None:
            stmt = stmt.where(MarketingDivision.id != exclude_id)
        if db.execute(stmt).first() is None:
            return candidate
        suffix += 1
        tail = f"-{suffix}"
        candidate = f"{base[: 120 - len(tail)]}{tail}"


def _unique_qr_slug(db: Session, base: str) -> str:
    """Append ``-2``, ``-3``… until the QR slug is free.

    QR slugs are global (the resolver looks up ``/q/{slug}`` without a
    division), so uniqueness is checked across the whole table rather
    than per-division.
    """
    candidate = base[:64]
    suffix = 1
    while True:
        exists = db.execute(
            select(MarketingQrCode.id).where(MarketingQrCode.slug == candidate)
        ).first()
        if exists is None:
            return candidate
        suffix += 1
        tail = f"-{suffix}"
        candidate = f"{base[: 64 - len(tail)]}{tail}"


# ---------------------------------------------------------------------------
# Row lookups + audit
# ---------------------------------------------------------------------------


def _division_or_404(db: Session, division_id: int) -> MarketingDivision:
    row = db.get(MarketingDivision, division_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Division not found")
    return row


def _qr_or_404(db: Session, qr_code_id: int) -> MarketingQrCode:
    row = db.get(MarketingQrCode, qr_code_id)
    if row is None:
        raise HTTPException(status_code=404, detail="QR code not found")
    return row


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


# ---------------------------------------------------------------------------
# Divisions
# ---------------------------------------------------------------------------


@router.get("/divisions", response_model=DivisionListResponse)
def list_divisions(
    db: Session = Depends(get_db),
    actor: User = Depends(_VIEWER),  # noqa: ARG001 — guard only
    search: Optional[str] = Query(default=None, max_length=200),
    include_inactive: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> DivisionListResponse:
    """Divisions with their QR codes nested, ordered for display.

    ``selectinload`` on ``qr_codes`` keeps this at two queries no
    matter how many divisions come back — the admin page renders every
    division's codes at once, so lazy-loading would be N+1.
    """
    where_clauses = []
    if not include_inactive:
        where_clauses.append(MarketingDivision.is_active.is_(True))
    if search:
        needle = f"%{search.strip().lower()}%"
        where_clauses.append(
            or_(
                func.lower(MarketingDivision.name).like(needle),
                func.lower(MarketingDivision.slug).like(needle),
                func.lower(MarketingDivision.city).like(needle),
            )
        )

    base = select(MarketingDivision)
    if where_clauses:
        base = base.where(*where_clauses)

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()

    rows = (
        db.execute(
            base.options(selectinload(MarketingDivision.qr_codes))
            .order_by(
                asc(MarketingDivision.sort_order),
                asc(MarketingDivision.name),
            )
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return DivisionListResponse(
        items=[DivisionRead.model_validate(r) for r in rows],
        total=int(total),
    )


@router.post(
    "/divisions", response_model=DivisionRead, status_code=status.HTTP_201_CREATED
)
def create_division(
    payload: DivisionCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(_MANAGER),
) -> DivisionRead:
    """Create a division and (by default) its first QR code.

    Auto-creating the primary code is what makes the common case —
    "one permanent QR per branch" — a single form submit. The code is
    created with no target; the resolver sends scans to the fallback
    chain until marketing points it somewhere.
    """
    if payload.slug is not None:
        existing = db.execute(
            select(MarketingDivision.id).where(
                MarketingDivision.slug == payload.slug
            )
        ).first()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Division slug '{payload.slug}' is already in use.",
            )
        slug = payload.slug
    else:
        slug = _unique_division_slug(db, _slugify(payload.name))

    row = MarketingDivision(
        slug=slug,
        name=payload.name,
        city=payload.city,
        description=payload.description,
        logo_url=payload.logo_url,
        fallback_url=payload.fallback_url,
        is_active=payload.is_active,
        is_public=payload.is_public,
        sort_order=payload.sort_order,
        created_by_id=actor.id,
        # Storefront block — set via **dict so adding a field to
        # ``DivisionStorefrontFields`` doesn't need a line here too.
        **{f: getattr(payload, f) for f in _STOREFRONT_FIELDS},
    )
    db.add(row)
    db.flush()  # populate row.id

    if payload.create_primary_qr:
        qr = MarketingQrCode(
            division_id=row.id,
            slug=_unique_qr_slug(db, slug),
            label="Primary",
            created_by_id=actor.id,
        )
        db.add(qr)
        db.flush()
        _audit(
            db,
            actor,
            request,
            action=ACTION_QR_CREATE,
            target_type=TARGET_TYPE_QR,
            target_id=qr.id,
            details={"slug": qr.slug, "label": qr.label, "division_id": row.id},
        )

    _audit(
        db,
        actor,
        request,
        action=ACTION_DIVISION_CREATE,
        target_type=TARGET_TYPE_DIVISION,
        target_id=row.id,
        details={"slug": row.slug, "name": row.name},
    )
    db.commit()

    row = db.execute(
        select(MarketingDivision)
        .options(selectinload(MarketingDivision.qr_codes))
        .where(MarketingDivision.id == row.id)
    ).scalar_one()
    return DivisionRead.model_validate(row)


@router.get("/divisions/{division_id}", response_model=DivisionRead)
def get_division(
    division_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(_VIEWER),  # noqa: ARG001 — guard only
) -> DivisionRead:
    row = db.execute(
        select(MarketingDivision)
        .options(selectinload(MarketingDivision.qr_codes))
        .where(MarketingDivision.id == division_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Division not found")
    return DivisionRead.model_validate(row)


@router.patch("/divisions/{division_id}", response_model=DivisionRead)
def update_division(
    division_id: int,
    payload: DivisionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(_MANAGER),
) -> DivisionRead:
    """Update a division.

    Renaming or re-slugging a division does not touch its QR codes'
    slugs — those were snapshotted at creation and printed artwork
    depends on them.
    """
    row = _division_or_404(db, division_id)
    changes: dict[str, tuple] = {}

    if payload.slug is not None and payload.slug != row.slug:
        clash = db.execute(
            select(MarketingDivision.id).where(
                MarketingDivision.slug == payload.slug,
                MarketingDivision.id != row.id,
            )
        ).first()
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Division slug '{payload.slug}' is already in use.",
            )
        changes["slug"] = (row.slug, payload.slug)
        row.slug = payload.slug

    for field in (
        "name",
        "city",
        "description",
        "logo_url",
        "fallback_url",
        "is_active",
        "is_public",
        "sort_order",
        *_STOREFRONT_FIELDS,
    ):
        new_value = getattr(payload, field)
        if new_value is not None and new_value != getattr(row, field):
            changes[field] = (getattr(row, field), new_value)
            setattr(row, field, new_value)

    if changes:
        _audit(
            db,
            actor,
            request,
            action=ACTION_DIVISION_UPDATE,
            target_type=TARGET_TYPE_DIVISION,
            target_id=row.id,
            details={
                "changes": {
                    k: {"from": v[0], "to": v[1]} for k, v in changes.items()
                }
            },
        )
    db.commit()

    row = db.execute(
        select(MarketingDivision)
        .options(selectinload(MarketingDivision.qr_codes))
        .where(MarketingDivision.id == division_id)
    ).scalar_one()
    return DivisionRead.model_validate(row)


@router.delete("/divisions/{division_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_division(
    division_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(_MANAGER),
) -> Response:
    """Delete a division and every QR code under it.

    This breaks any printed artwork for those codes — the resolver
    will 404 because there's no row left to read a fallback from.
    Deactivating (``is_active = false``) is the reversible option and
    the admin UI steers operators there; this endpoint exists for
    genuine mistakes.
    """
    row = _division_or_404(db, division_id)
    qr_slugs = [qr.slug for qr in row.qr_codes]
    _audit(
        db,
        actor,
        request,
        action=ACTION_DIVISION_DELETE,
        target_type=TARGET_TYPE_DIVISION,
        target_id=row.id,
        details={"slug": row.slug, "name": row.name, "qr_slugs": qr_slugs},
    )
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# QR codes
# ---------------------------------------------------------------------------


@router.post(
    "/divisions/{division_id}/qr-codes",
    response_model=QrCodeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_qr_code(
    division_id: int,
    payload: QrCodeCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(_MANAGER),
) -> QrCodeRead:
    """Add a QR code to a division.

    When ``slug`` is omitted it's derived from the division slug plus
    the label ("al-khor-shelf-talker"), de-duplicated with a numeric
    suffix. Readable slugs matter here — staff can type one by hand
    if a printed code gets scuffed.
    """
    division = _division_or_404(db, division_id)

    if payload.slug is not None:
        existing = db.execute(
            select(MarketingQrCode.id).where(MarketingQrCode.slug == payload.slug)
        ).first()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"QR slug '{payload.slug}' is already in use.",
            )
        slug = payload.slug
    else:
        label_part = _slugify(payload.label)
        base = (
            division.slug
            if label_part in ("primary", "division")
            else f"{division.slug}-{label_part}"
        )
        slug = _unique_qr_slug(db, base)

    row = MarketingQrCode(
        division_id=division.id,
        slug=slug,
        label=payload.label,
        target_url=payload.target_url,
        target_kind=payload.target_kind,
        fallback_url=payload.fallback_url,
        is_active=payload.is_active,
        sort_order=payload.sort_order,
        target_updated_at=(
            datetime.now(timezone.utc) if payload.target_url else None
        ),
        created_by_id=actor.id,
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        actor,
        request,
        action=ACTION_QR_CREATE,
        target_type=TARGET_TYPE_QR,
        target_id=row.id,
        details={
            "slug": row.slug,
            "label": row.label,
            "division_id": division.id,
            "target_url": row.target_url,
        },
    )
    db.commit()
    db.refresh(row)
    return QrCodeRead.model_validate(row)


@router.get("/qr-codes/{qr_code_id}", response_model=QrCodeRead)
def get_qr_code(
    qr_code_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(_VIEWER),  # noqa: ARG001 — guard only
) -> QrCodeRead:
    return QrCodeRead.model_validate(_qr_or_404(db, qr_code_id))


@router.patch("/qr-codes/{qr_code_id}", response_model=QrCodeRead)
def update_qr_code(
    qr_code_id: int,
    payload: QrCodeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(_MANAGER),
) -> QrCodeRead:
    """Re-point / rename / toggle a QR code.

    The slug is absent from ``QrCodeUpdate`` entirely, so there is no
    request body that can change it — the printed artwork stays valid
    no matter what an operator submits here.

    A target change is audited under its own action
    (``marketing.qr.target.update``) rather than folded into the
    generic update, because the analytics panel replays exactly that
    action to build the "what did this code point at, and when"
    history.
    """
    row = _qr_or_404(db, qr_code_id)
    changes: dict[str, tuple] = {}
    target_changed: Optional[tuple[Optional[str], Optional[str]]] = None

    if payload.target_url is not None and payload.target_url != row.target_url:
        target_changed = (row.target_url, payload.target_url)
        row.target_url = payload.target_url
        row.target_updated_at = datetime.now(timezone.utc)

    for field in ("label", "target_kind", "fallback_url", "is_active", "sort_order"):
        new_value = getattr(payload, field)
        if new_value is not None and new_value != getattr(row, field):
            changes[field] = (getattr(row, field), new_value)
            setattr(row, field, new_value)

    if target_changed is not None:
        _audit(
            db,
            actor,
            request,
            action=ACTION_QR_TARGET_UPDATE,
            target_type=TARGET_TYPE_QR,
            target_id=row.id,
            details={
                "slug": row.slug,
                "from_url": target_changed[0],
                "to_url": target_changed[1],
            },
        )
    if changes:
        _audit(
            db,
            actor,
            request,
            action=ACTION_QR_UPDATE,
            target_type=TARGET_TYPE_QR,
            target_id=row.id,
            details={
                "slug": row.slug,
                "changes": {
                    k: {"from": v[0], "to": v[1]} for k, v in changes.items()
                },
            },
        )
    db.commit()
    db.refresh(row)
    return QrCodeRead.model_validate(row)


@router.delete("/qr-codes/{qr_code_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_qr_code(
    qr_code_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(_MANAGER),
) -> Response:
    """Hard-delete a QR code.

    Same caveat as deleting a division: any printed copy of this code
    starts 404ing immediately, with no fallback to catch the scan.
    Prefer ``is_active = false``.
    """
    row = _qr_or_404(db, qr_code_id)
    _audit(
        db,
        actor,
        request,
        action=ACTION_QR_DELETE,
        target_type=TARGET_TYPE_QR,
        target_id=row.id,
        details={
            "slug": row.slug,
            "label": row.label,
            "target_url": row.target_url,
            "scan_count": row.scan_count,
        },
    )
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Rendered artwork
# ---------------------------------------------------------------------------


@router.get("/qr-codes/{qr_code_id}/qr-code.png")
def qr_code_png(
    qr_code_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(_VIEWER),  # noqa: ARG001 — guard only
    size: int = Query(default=1024),
    download: bool = Query(default=False),
) -> Response:
    """Render the branded PNG for this code's permanent ``/q/{slug}`` URL.

    Note what is encoded: the resolver URL, never ``target_url``. That
    indirection is the whole feature — artwork generated today keeps
    working after the target changes tomorrow.

    The division's ``logo_url`` supplies the centre badge so an Al Khor
    code carries the Al Khor mark; the QR service falls back to a PUG
    monogram when the division has no logo or the bytes can't be
    fetched.
    """
    from app.core.config import get_settings
    from app.services.qr_codes import build_catalogue_qr

    if size not in ALLOWED_QR_SIZES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"size must be one of: {', '.join(str(s) for s in ALLOWED_QR_SIZES)}",
        )

    row = _qr_or_404(db, qr_code_id)
    division = db.get(MarketingDivision, row.division_id)
    settings = get_settings()
    public_url = qr_public_url(settings, row.slug)

    logo_bytes = _resolve_division_logo_bytes(settings, division)
    png_bytes = build_catalogue_qr(public_url, logo_bytes=logo_bytes, size_px=size)

    safe_slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in row.slug)
    filename = f"qr-{safe_slug}-{size}.png"
    disposition = "attachment" if download else "inline"

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            # Private + short: the artwork is stable, but an operator
            # who swaps the division logo expects the preview to catch
            # up without a hard refresh.
            "Cache-Control": "private, max-age=60",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


def qr_public_url(settings, slug: str) -> str:
    """The permanent scan URL encoded into the artwork.

    Built from ``short_url_base`` when configured (the branded short
    domain, e.g. ``https://pug.qa``) and the public site URL otherwise.
    Deriving it from the request host would be a bug: a code generated
    while an admin happened to be on a staging host would be printed
    pointing at staging.
    """
    base = (
        getattr(settings, "short_url_base", None)
        or settings.public_site_url
        or ""
    ).rstrip("/")
    return f"{base}/q/{slug}"


def _resolve_division_logo_bytes(
    settings, division: Optional[MarketingDivision]
) -> Optional[bytes]:
    """Fetch the division's centre-badge logo bytes, if any.

    Preference order mirrors the catalogue QR endpoint:
      1. ``division.logo_url`` via the storage backend (works for both
         local-disk and R2 installs).
      2. ``uploads/brand-logo.png`` / ``uploads/logo.png`` — the
         operator-level default, always read off local disk because
         it's a deploy-time file rather than CMS content.
      3. ``None`` — the QR service stamps a "PUG" monogram instead.

    Every failure path falls through rather than raising: a missing
    logo must never turn into a 500 on the artwork endpoint.
    """
    from pathlib import Path

    from app.services.storage import get_storage

    if division is not None and division.logo_url:
        key = _storage_key_from_url(division.logo_url)
        if key:
            try:
                return get_storage().download_sync(key)
            except FileNotFoundError:
                logger.warning(
                    "division qr logo missing from storage",
                    key=key,
                    division_id=division.id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "division qr logo fetch failed",
                    key=key,
                    division_id=division.id,
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


def _storage_key_from_url(url: str) -> Optional[str]:
    """Recover a storage key from a media URL.

        local : ``/api/v1/uploads/media/logo.png``  -> ``media/logo.png``
        R2    : ``https://media.example.com/media/logo.png``
                                                    -> ``media/logo.png``

    Returns ``None`` when the shape isn't recognised, which the caller
    treats as "no logo" rather than an error.
    """
    if not url:
        return None
    marker = "/api/v1/uploads/"
    idx = url.find(marker)
    if idx != -1:
        return url[idx + len(marker):].lstrip("/") or None
    if url.startswith("http://") or url.startswith("https://"):
        # Strip scheme + host and treat the remaining path as the key.
        without_scheme = url.split("://", 1)[1]
        slash = without_scheme.find("/")
        if slash == -1:
            return None
        return without_scheme[slash + 1:].lstrip("/") or None
    return url.lstrip("/") or None


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@router.get("/qr-codes/{qr_code_id}/analytics", response_model=QrCodeAnalytics)
def qr_code_analytics(
    qr_code_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(_VIEWER),  # noqa: ARG001 — guard only
    days: int = Query(default=30, ge=1, le=365),
) -> QrCodeAnalytics:
    """Scan trend, device split, and target-change history for one code.

    The daily series is zero-filled across the whole window so the
    frontend chart doesn't have to reason about gaps — a day with no
    scans is a real data point, not a missing one.
    """
    row = _qr_or_404(db, qr_code_id)
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    # ``func.date`` works on both Postgres and SQLite (tests) and gives
    # a plain ISO date string on each.
    day_col = func.date(MarketingQrScanEvent.scanned_at)
    daily_rows = db.execute(
        select(day_col, func.count())
        .where(
            MarketingQrScanEvent.qr_code_id == row.id,
            MarketingQrScanEvent.scanned_at >= since,
        )
        .group_by(day_col)
        .order_by(day_col)
    ).all()
    counts_by_day = {str(d): int(c) for d, c in daily_rows}

    daily: List[QrScanDailyPoint] = []
    start_day = (now - timedelta(days=days - 1)).date()
    for offset_days in range(days):
        day = (start_day + timedelta(days=offset_days)).isoformat()
        daily.append(QrScanDailyPoint(day=day, scans=counts_by_day.get(day, 0)))

    scans_last_30 = sum(counts_by_day.values())

    device_rows = db.execute(
        select(MarketingQrScanEvent.device, func.count())
        .where(
            MarketingQrScanEvent.qr_code_id == row.id,
            MarketingQrScanEvent.scanned_at >= since,
        )
        .group_by(MarketingQrScanEvent.device)
        .order_by(desc(func.count()))
    ).all()
    devices = [
        QrDeviceBreakdown(device=d or "unknown", scans=int(c)) for d, c in device_rows
    ]

    history = _target_history(db, row.id)

    return QrCodeAnalytics(
        qr_code_id=row.id,
        total_scans=int(row.scan_count),
        scans_last_30_days=scans_last_30,
        last_scan_at=row.last_scan_at,
        daily=daily,
        devices=devices,
        target_history=history,
    )


def _target_history(db: Session, qr_code_id: int) -> List[QrTargetHistoryEntry]:
    """Replay ``marketing.qr.target.update`` audit rows into history.

    Reading this off the audit log rather than a dedicated table keeps
    one source of truth for "who changed what" — the same rows the
    Audit page shows. Capped at 50 because the panel is a sidebar, not
    a report.
    """
    rows = (
        db.execute(
            select(AuditLog)
            .where(
                AuditLog.target_type == TARGET_TYPE_QR,
                AuditLog.target_id == str(qr_code_id),
                AuditLog.action == ACTION_QR_TARGET_UPDATE,
            )
            # ``id`` breaks the tie: two re-points inside the same
            # clock tick (SQLite's CURRENT_TIMESTAMP is second-granular)
            # would otherwise come back in arbitrary order and show the
            # operator a history that reads backwards.
            .order_by(desc(AuditLog.created_at), desc(AuditLog.id))
            .limit(50)
        )
        .scalars()
        .all()
    )
    entries: List[QrTargetHistoryEntry] = []
    for entry in rows:
        details = entry.details or {}
        entries.append(
            QrTargetHistoryEntry(
                changed_at=entry.created_at,
                actor_email=entry.actor_email,
                from_url=details.get("from_url"),
                to_url=details.get("to_url"),
            )
        )
    return entries

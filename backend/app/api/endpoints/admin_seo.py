"""Admin endpoints for the SEO Configuration module (Phase 1).

Mounted at ``/api/v1/admin/seo`` behind ``require_website_admin``. Every
write goes through ``record_audit`` with action keys prefixed
``seo.*`` so the existing audit-log viewer surfaces them under the
website scope.

Routes:

  * ``GET    /settings``        – read the global SEO settings row
  * ``PATCH  /settings``        – partial update (auto-creates the row)
  * ``GET    /verifications``   – list every verification record
  * ``POST   /verifications``   – create a verification record
  * ``PATCH  /verifications/{id}`` – update
  * ``DELETE /verifications/{id}`` – delete
  * ``GET    /integrations``    – list active + inactive integrations
  * ``PUT    /integrations``    – upsert by provider (one row per provider)
  * ``DELETE /integrations/{provider}`` – remove a provider row
  * ``GET    /dashboard``       – aggregated dashboard payload
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context, require_website_admin
from app.core.database import get_db
from app.models.auth import SCOPE_WEBSITE, User
from app.models.seo import (
    PROVIDER_CLARITY,
    PROVIDER_GA4,
    PROVIDER_GTM,
    PROVIDER_META_PIXEL,
    SeoSetting,
    SeoVerification,
    TrackingIntegration,
    VERIFICATION_TYPE_FULL_META,
    VERIFICATION_TYPE_HTML_FILE,
    VERIFICATION_TYPE_META,
)
from app.schemas.seo import (
    SeoDashboardRead,
    SeoSettingRead,
    SeoSettingUpdate,
    SeoVerificationCreate,
    SeoVerificationRead,
    SeoVerificationUpdate,
    TrackingIntegrationRead,
    TrackingIntegrationUpsert,
)
from app.services.audit_log import record_audit
from app.services.seo import (
    MetaSanitiseError,
    duplicate_tracking_warning,
    integration_by_provider,
    sanitize_meta_tag,
    validate_tracking_id,
    verification_active_for,
)


router = APIRouter(
    prefix="/admin/seo",
    tags=["Website Admin - SEO"],
    dependencies=[Depends(require_website_admin)],
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _audit(
    db: Session,
    user: User,
    request: Request,
    *,
    action: str,
    target_type: str,
    target_id: Optional[int],
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


def _get_or_create_seo_settings(db: Session) -> SeoSetting:
    """The settings row is a singleton; create lazily on first access."""
    row = db.execute(select(SeoSetting).order_by(SeoSetting.id)).scalars().first()
    if row is None:
        row = SeoSetting()
        db.add(row)
        db.flush()
    return row


# ---------------------------------------------------------------------------
# Global settings
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=SeoSettingRead)
def get_settings(db: Session = Depends(get_db)) -> SeoSetting:
    return _get_or_create_seo_settings(db)


@router.patch("/settings", response_model=SeoSettingRead)
def update_settings(
    payload: SeoSettingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> SeoSetting:
    row = _get_or_create_seo_settings(db)
    changed: dict = {}
    for field, value in payload.model_dump(exclude_unset=True).items():
        if getattr(row, field) != value:
            changed[field] = value
            setattr(row, field, value)
    if changed:
        row.updated_by_id = user.id
        row.updated_at = datetime.now(timezone.utc)
        _audit(
            db,
            user,
            request,
            action="seo.settings.update",
            target_type="seo_setting",
            target_id=row.id,
            details={"changed_fields": sorted(changed.keys())},
        )
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Verifications
# ---------------------------------------------------------------------------


@router.get("/verifications", response_model=List[SeoVerificationRead])
def list_verifications(db: Session = Depends(get_db)) -> List[SeoVerification]:
    rows = (
        db.execute(select(SeoVerification).order_by(SeoVerification.id.desc()))
        .scalars()
        .all()
    )
    return rows


@router.post(
    "/verifications",
    response_model=SeoVerificationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_verification(
    payload: SeoVerificationCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> SeoVerification:
    # Type-specific validation that's awkward to express purely in the schema.
    if payload.verification_type == VERIFICATION_TYPE_META:
        if not payload.verification_name or not payload.verification_content:
            raise HTTPException(
                status_code=422,
                detail="meta_tag verifications require verification_name + verification_content",
            )
    elif payload.verification_type == VERIFICATION_TYPE_FULL_META:
        if not payload.full_meta_tag:
            raise HTTPException(
                status_code=422,
                detail="full_meta_tag verifications require the meta tag snippet",
            )
        try:
            sanitize_meta_tag(payload.full_meta_tag)
        except MetaSanitiseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    elif payload.verification_type == VERIFICATION_TYPE_HTML_FILE:
        if not payload.html_filename or not payload.html_file_content:
            raise HTTPException(
                status_code=422,
                detail="html_file verifications require html_filename + html_file_content",
            )
        # Uniqueness check on active filename.
        existing = db.execute(
            select(SeoVerification).where(
                SeoVerification.html_filename == payload.html_filename,
                SeoVerification.is_active.is_(True),
            )
        ).scalars().first()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Another active verification already uses {payload.html_filename}",
            )

    row = SeoVerification(**payload.model_dump(), created_by_id=user.id, updated_by_id=user.id)
    db.add(row)
    db.flush()
    _audit(
        db,
        user,
        request,
        action="seo.verification.create",
        target_type="seo_verification",
        target_id=row.id,
        details={"provider": row.provider, "type": row.verification_type},
    )
    db.commit()
    db.refresh(row)
    return row


@router.patch("/verifications/{verification_id}", response_model=SeoVerificationRead)
def update_verification(
    verification_id: int,
    payload: SeoVerificationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> SeoVerification:
    row = db.get(SeoVerification, verification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Verification not found")

    data = payload.model_dump(exclude_unset=True)

    # Re-sanitise full meta tags whenever the field is touched.
    if "full_meta_tag" in data and data["full_meta_tag"]:
        try:
            sanitize_meta_tag(data["full_meta_tag"])
        except MetaSanitiseError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Active-filename uniqueness on toggle / rename.
    if data.get("is_active", row.is_active) and (
        "html_filename" in data or "is_active" in data
    ):
        candidate = data.get("html_filename", row.html_filename)
        if candidate:
            clash = (
                db.execute(
                    select(SeoVerification).where(
                        SeoVerification.id != row.id,
                        SeoVerification.html_filename == candidate,
                        SeoVerification.is_active.is_(True),
                    )
                )
                .scalars()
                .first()
            )
            if clash is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Another active verification already uses {candidate}",
                )

    for field, value in data.items():
        setattr(row, field, value)
    row.updated_by_id = user.id
    row.updated_at = datetime.now(timezone.utc)
    _audit(
        db,
        user,
        request,
        action="seo.verification.update",
        target_type="seo_verification",
        target_id=row.id,
        details={"changed_fields": sorted(data.keys())},
    )
    db.commit()
    db.refresh(row)
    return row


@router.delete("/verifications/{verification_id}", status_code=204)
def delete_verification(
    verification_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
):
    row = db.get(SeoVerification, verification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Verification not found")
    db.delete(row)
    _audit(
        db,
        user,
        request,
        action="seo.verification.delete",
        target_type="seo_verification",
        target_id=verification_id,
        details={"provider": row.provider, "type": row.verification_type},
    )
    db.commit()


# ---------------------------------------------------------------------------
# Tracking integrations
# ---------------------------------------------------------------------------


@router.get("/integrations", response_model=List[TrackingIntegrationRead])
def list_integrations(db: Session = Depends(get_db)) -> List[TrackingIntegration]:
    rows = (
        db.execute(
            select(TrackingIntegration).order_by(TrackingIntegration.provider)
        )
        .scalars()
        .all()
    )
    return rows


@router.put("/integrations", response_model=TrackingIntegrationRead)
def upsert_integration(
    payload: TrackingIntegrationUpsert,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
) -> TrackingIntegration:
    """Create or update the (singleton) row for ``payload.provider``."""
    # Validate the tracking ID against its provider's expected shape
    # whenever it's present. We don't reject saves with an empty ID —
    # admins may want to stage a row, flip ``is_active=False``, and
    # only fill the ID later.
    if payload.tracking_id:
        try:
            payload.tracking_id = validate_tracking_id(
                payload.provider, payload.tracking_id
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    row = (
        db.execute(
            select(TrackingIntegration).where(
                TrackingIntegration.provider == payload.provider
            )
        )
        .scalars()
        .first()
    )
    created = row is None
    if row is None:
        row = TrackingIntegration(
            provider=payload.provider, created_by_id=user.id, updated_by_id=user.id
        )
        db.add(row)
    data = payload.model_dump(exclude_unset=True, exclude={"provider"})
    for field, value in data.items():
        setattr(row, field, value)
    row.updated_by_id = user.id
    row.updated_at = datetime.now(timezone.utc)
    db.flush()
    _audit(
        db,
        user,
        request,
        action="seo.integration.create" if created else "seo.integration.update",
        target_type="tracking_integration",
        target_id=row.id,
        details={"provider": row.provider, "is_active": row.is_active},
    )
    db.commit()
    db.refresh(row)
    return row


@router.delete("/integrations/{provider}", status_code=204)
def delete_integration(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_website_admin),
):
    row = (
        db.execute(
            select(TrackingIntegration).where(
                TrackingIntegration.provider == provider.lower()
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    row_id = row.id
    db.delete(row)
    _audit(
        db,
        user,
        request,
        action="seo.integration.delete",
        target_type="tracking_integration",
        target_id=row_id,
        details={"provider": provider.lower()},
    )
    db.commit()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard", response_model=SeoDashboardRead)
def seo_dashboard(db: Session = Depends(get_db)) -> SeoDashboardRead:
    settings = _get_or_create_seo_settings(db)
    integrations = (
        db.execute(select(TrackingIntegration)).scalars().all()
    )
    verifications = (
        db.execute(select(SeoVerification)).scalars().all()
    )
    by_provider = integration_by_provider(integrations)

    def _id_if_active(provider: str) -> tuple[bool, Optional[str]]:
        row = by_provider.get(provider)
        if row is None or not row.is_active or not (row.tracking_id or "").strip():
            return False, None
        return True, row.tracking_id

    gtm_active, gtm_id = _id_if_active(PROVIDER_GTM)
    ga4_active, ga4_id = _id_if_active(PROVIDER_GA4)
    pixel_active, pixel_id = _id_if_active(PROVIDER_META_PIXEL)
    clarity_active, clarity_id = _id_if_active(PROVIDER_CLARITY)

    return SeoDashboardRead(
        canonical_base_url=settings.canonical_base_url,
        sitemap_enabled=settings.enable_sitemap,
        robots_enabled=settings.enable_robots,
        gtm_active=gtm_active,
        gtm_id=gtm_id,
        ga4_active=ga4_active,
        ga4_id=ga4_id,
        meta_pixel_active=pixel_active,
        meta_pixel_id=pixel_id,
        clarity_active=clarity_active,
        clarity_id=clarity_id,
        google_verification_active=verification_active_for(verifications, "google"),
        bing_verification_active=verification_active_for(verifications, "bing"),
        meta_verification_active=verification_active_for(verifications, "meta"),
        active_integrations=sorted(
            row.provider
            for row in integrations
            if row.is_active and (row.tracking_id or "").strip()
        ),
        active_verifications=sorted(
            {v.provider for v in verifications if v.is_active}
        ),
        duplicate_tracking_warning=duplicate_tracking_warning(integrations),
        last_updated_at=settings.updated_at,
    )

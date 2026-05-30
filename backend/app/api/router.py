"""Top-level API router that aggregates every sub-router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.endpoints import (
    admin_ai,
    admin_auth,
    admin_backup,
    admin_cms,
    admin_email_settings,
    admin_marketing,
    admin_seo,
    admin_short_urls,
    admin_storage,
    admin_users,
    health,
    marketing_public,
    hr_auth,
    hr_candidates,
    hr_dashboard,
    hr_interviews,
    hr_jobs,
    hr_offers,
    hr_reports,
    hr_saved_searches,
    hr_scheduled_reports,
    hr_scorecards,
    public,
    public_short_urls,
    websocket,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(public.router)
api_router.include_router(admin_auth.router)
api_router.include_router(admin_cms.router)
api_router.include_router(admin_seo.router)
api_router.include_router(admin_ai.router)
api_router.include_router(admin_email_settings.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_backup.router)
api_router.include_router(admin_storage.router)
api_router.include_router(admin_marketing.router)
api_router.include_router(admin_short_urls.router)
api_router.include_router(marketing_public.router)
api_router.include_router(public_short_urls.router)
api_router.include_router(hr_auth.router)
api_router.include_router(hr_dashboard.router)
api_router.include_router(hr_jobs.router)
api_router.include_router(hr_candidates.router)
api_router.include_router(hr_interviews.router)
api_router.include_router(hr_offers.router)
api_router.include_router(hr_reports.router)
api_router.include_router(hr_saved_searches.router)
api_router.include_router(hr_scorecards.router)
api_router.include_router(hr_scheduled_reports.router)
api_router.include_router(websocket.router)

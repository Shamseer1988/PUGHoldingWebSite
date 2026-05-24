"""Top-level API router that aggregates every sub-router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.endpoints import (
    admin_ai,
    admin_auth,
    admin_cms,
    health,
    hr_auth,
    hr_candidates,
    hr_dashboard,
    hr_interviews,
    hr_jobs,
    public,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(public.router)
api_router.include_router(admin_auth.router)
api_router.include_router(admin_cms.router)
api_router.include_router(admin_ai.router)
api_router.include_router(hr_auth.router)
api_router.include_router(hr_dashboard.router)
api_router.include_router(hr_jobs.router)
api_router.include_router(hr_candidates.router)
api_router.include_router(hr_interviews.router)

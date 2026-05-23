"""Top-level API router that aggregates every sub-router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.endpoints import admin_auth, admin_cms, health, hr_auth

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(admin_auth.router)
api_router.include_router(admin_cms.router)
api_router.include_router(hr_auth.router)

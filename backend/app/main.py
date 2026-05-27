"""FastAPI application factory.

This module defines the ASGI application used by uvicorn / gunicorn.
Domain routers (website admin, HR ATS, public, AI) are added in later
phases; Phase 1 only wires the health-check endpoint plus the cross-cutting
middleware that every later phase will rely on.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import api_router
from app.core.cache_headers import PublicCacheHeadersMiddleware
from app.core.config import ensure_production_safety, get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown hooks.

    Boots the in-process APScheduler at startup so scheduled report
    digests (and, in a future commit, nightly automatic database
    backups) fire even when no HTTP traffic is hitting the process.
    The scheduler is disabled in tests via SCHEDULER_ENABLED=false.
    """
    from app.core.scheduler import shutdown_scheduler, start_scheduler

    # Import the job modules for their register_job side effects.
    # Adding new scheduled jobs is as simple as creating a module
    # under app.jobs and importing it here.
    try:
        from app import jobs as _jobs  # noqa: F401
    except ImportError:
        # No jobs registered yet — scheduler boots empty, which is fine.
        pass

    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    # Refuse to boot in production with a weak secret key or missing
    # CORS allowlist. No-op outside production.
    ensure_production_safety(settings)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Backend API for the Paris United Group Holding corporate website "
            "and HR ATS portal."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Phase 19: rate limiting for the public write endpoints is applied
    # per-route via FastAPI dependencies — see app.core.rate_limit.

    # Edge cache headers on public GET responses. Toggle off in dev
    # via PUBLIC_CACHE_HEADERS_ENABLED=false if it gets in the way.
    app.add_middleware(PublicCacheHeadersMiddleware)

    app.include_router(api_router, prefix="/api/v1")

    # Static mount for user-uploaded assets (CMS images, etc.).
    # The directory is created on first upload, but ensure it exists
    # at boot so the StaticFiles mount doesn't raise.
    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/api/v1/uploads",
        StaticFiles(directory=str(upload_root)),
        name="uploads",
    )

    @app.get("/", tags=["Root"], summary="Root endpoint")
    def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()

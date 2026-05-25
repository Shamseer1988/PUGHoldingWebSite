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
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown hooks.

    Kept intentionally minimal in Phase 1. Later phases can attach
    connection pools, schedulers, or background workers here.
    """
    yield


def create_app() -> FastAPI:
    settings = get_settings()

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

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
from app.core.logging_config import configure_logging, get_logger
from app.core.request_id import RequestIDMiddleware


# Phase A-4: configure structlog before the first logger is bound.
# ``get_logger`` does this lazily too, but doing it explicitly here
# pins the env at import-time so the second pass inside ``create_app``
# is just a no-op.
configure_logging(app_env=get_settings().app_env)
logger = get_logger(__name__)


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

    # Phase A-3: only expose the interactive OpenAPI surface in
    # development. ``/docs``, ``/redoc`` and ``/openapi.json`` leak
    # the full route surface + every Pydantic schema to anyone who
    # finds the URL — fine for local development, never appropriate
    # for prod (and ambiguous for staging / preview environments,
    # which we also keep closed by default).
    is_development = (settings.app_env or "").lower() == "development"
    docs_url = "/docs" if is_development else None
    redoc_url = "/redoc" if is_development else None
    openapi_url = "/openapi.json" if is_development else None

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Backend API for the Paris United Group Holding corporate website "
            "and HR ATS portal."
        ),
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )

    # CORS — strict allowlist in production, permissive LAN in dev.
    #
    # FastAPI's CORSMiddleware returns ``400 Bad Request`` on every
    # preflight whose ``Origin`` header isn't in ``allow_origins``. In
    # development the frontend can hit the API from:
    #   * ``localhost`` / ``127.0.0.1`` on any port (3000, 3001, 5173…)
    #   * A LAN IP (``192.168.x.x``, ``10.x.x.x``, ``172.16-31.x.x``)
    #     when testing from a phone / tablet / another laptop on the
    #     same WiFi.
    # So we pass an ``allow_origin_regex`` that matches both. The
    # strict ``allow_origins`` list still wins for explicit values;
    # the regex is the safety net. Never enabled in production.
    is_prod = settings.app_env.lower() == "production"
    cors_kwargs: dict = {
        "allow_origins": settings.cors_origins,
        "allow_credentials": True,
        # Phase A-3: replace the wildcard ``*`` allowlists with an
        # explicit set. The methods cover everything the API actually
        # exposes; the headers cover the JSON content negotiation,
        # bearer-token auth and the request-id correlator (added in
        # A-4). Adding a new header requires a deliberate edit here,
        # which is the point.
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Request-ID"],
        "expose_headers": ["Content-Disposition"],
    }
    if not is_prod:
        # http(s)://(localhost|127.0.0.1|RFC1918 private IP)(:any port)?
        cors_kwargs["allow_origin_regex"] = (
            r"^https?://("
            r"localhost|"
            r"127\.0\.0\.1|"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
            r"192\.168\.\d{1,3}\.\d{1,3}|"
            r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
            r")(:\d+)?$"
        )
    logger.info(
        "CORS configured: app_env=%s, allow_origins=%s%s",
        settings.app_env,
        settings.cors_origins,
        ", allow_origin_regex=localhost|127.0.0.1|RFC1918 LAN (any port)"
        if not is_prod
        else "",
    )
    app.add_middleware(CORSMiddleware, **cors_kwargs)

    # Phase A-4: request-id correlator. Starlette wraps middleware
    # in registration order from the inside out, so calling
    # ``add_middleware`` here AFTER CORS makes RequestIDMiddleware the
    # outermost layer — it fires on every request (including CORS
    # preflight ``OPTIONS`` that CORSMiddleware would otherwise
    # short-circuit) and stamps ``X-Request-ID`` on every response.
    app.add_middleware(RequestIDMiddleware)

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

"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Load the .env file into os.environ *before* `Settings()` is
# instantiated. pydantic-settings also reads the .env file, but the
# `cors_origins` property below reads via `os.getenv` so we need
# python-dotenv to populate it too.
load_dotenv()


DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"

# The historic "default" secret key shipped with the repo. We keep it
# referenced here so the production validator in ``ensure_production_safety``
# can detect when an operator forgot to set ``SECRET_KEY`` and fail
# fast instead of signing JWTs with a publicly-known value.
INSECURE_DEFAULT_SECRET_KEY = "change-me-to-a-strong-random-secret"
MIN_SECRET_KEY_LENGTH = 32


class InsecureConfigurationError(RuntimeError):
    """Raised at boot when the production environment is missing a
    required hardening setting (e.g. real SECRET_KEY or CORS allowlist)."""


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = Field(default="PUG Holding API")
    app_env: str = Field(default="development")
    # Phase A-3: production-safe default. Operators flip this on in dev
    # via APP_DEBUG=true; the field never gets a True default again so
    # a forgotten override can't leak the debug surface into prod.
    app_debug: bool = Field(default=False)
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)

    # Public-facing site URL used for share links, QR codes, email
    # links, etc. In dev this is the Next.js host (port 3000); in
    # production it's the customer-facing domain. The QR-code
    # endpoint refuses to encode the backend's own ``request.base_url``
    # (port 8000) because that won't resolve from a phone scan.
    public_site_url: str = Field(default="http://localhost:3000")

    # --- Security ---
    # Phase A-3: ``secret_key`` is now Optional with a None default. A
    # boot-time validator below refuses to load Settings when the env
    # is ``production`` and SECRET_KEY hasn't been set. Dev + tests
    # still work because the test conftest pins SECRET_KEY via env
    # before any module reads it (see backend/tests/conftest.py).
    secret_key: Optional[str] = Field(default=None)
    access_token_expire_minutes: int = Field(default=60)
    refresh_token_expire_days: int = Field(default=7)
    algorithm: str = Field(default="HS256")

    # --- Database ---
    postgres_user: str = Field(default="pug_user")
    postgres_password: str = Field(default="pug_password")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="pug_holding")
    database_url: Optional[str] = Field(default=None)

    # NOTE: CORS_ORIGINS is intentionally NOT declared as a field.
    # pydantic-settings 2.x tries to JSON-decode env values when the
    # matched field is a complex type (List[str]) — and with some
    # interpreter/dotenv combinations that pre-decode still fires for
    # aliased string fields, blowing up on the comma-separated value.
    # We read it via os.getenv in the `cors_origins` property below,
    # and `extra="ignore"` keeps pydantic-settings from raising on the
    # otherwise-unmatched env var.

    # --- Observability + queue (Phase A-3) ---
    # Sentry DSN is wired in Phase A-8; declaring the field now keeps
    # the env shape stable across phases. Redis URL covers both the
    # ARQ background queue (Phase B-3) and the rate-limit/cache layer
    # (Phase B-2). Default points at a local redis so docker-compose
    # development just works.
    sentry_dsn: Optional[str] = Field(default=None)
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Phase B-3: ARQ background queue toggle. When off (the test +
    # legacy default) the image optimiser, email sender and AI
    # review run inline inside the request handler — exactly how
    # they always have. When on, those three call sites enqueue an
    # ARQ job against the Redis above and return immediately; a
    # separate ``arq.worker`` process (``python -m
    # worker_runner``) drains the queue.
    arq_enabled: bool = Field(default=False)

    # --- Uploads ---
    upload_dir: str = Field(default="app/uploads")
    max_upload_size_mb: int = Field(default=20)

    # --- Cloudflare R2 (Phase A-6) ---
    # When all four required fields are set (host + creds + bucket),
    # the storage factory in ``app.services.storage`` returns
    # ``R2StorageBackend``. Otherwise it falls back to the local-disk
    # backend that mirrors the pre-R2 behaviour, so unconfigured
    # installs (dev, CI, fresh staging) keep working without a
    # cloud account. ``r2_public_base_url`` is optional — when unset
    # the backend constructs the long ``<account>.r2.cloudflarestorage.com``
    # URL itself.
    r2_endpoint_url: Optional[str] = Field(default=None)
    r2_access_key_id: Optional[str] = Field(default=None)
    r2_secret_access_key: Optional[str] = Field(default=None)
    r2_bucket_name: str = Field(default="pug-holding-media")
    r2_public_base_url: Optional[str] = Field(default=None)

    @property
    def r2_configured(self) -> bool:
        """True when every required R2 setting is present, so the
        storage factory should hand back the R2 backend."""
        return bool(
            self.r2_endpoint_url
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket_name
        )

    # --- Azure OpenAI (placeholders) ---
    azure_openai_endpoint: Optional[str] = Field(default=None)
    azure_openai_api_key: Optional[str] = Field(default=None)
    azure_openai_deployment: Optional[str] = Field(default=None)
    azure_openai_api_version: str = Field(default="2024-08-01-preview")
    ai_enabled: bool = Field(default=False)

    # --- Email (placeholders) ---
    smtp_host: Optional[str] = Field(default=None)
    smtp_port: int = Field(default=587)
    smtp_username: Optional[str] = Field(default=None)
    smtp_password: Optional[str] = Field(default=None)
    smtp_from_email: Optional[str] = Field(default=None)
    smtp_use_tls: bool = Field(default=True)

    # --- Contact-ticket support mailbox ---
    # Where customer replies land + where outbound replies set their
    # Reply-To header so a "reply" from the inbox round-trips back
    # into the IMAP processor. Independent of smtp_from_email so the
    # "from" can be a noreply alias while replies route to support.
    contact_reply_to_email: Optional[str] = Field(default=None)
    contact_from_name: str = Field(default="Paris United Group")
    contact_from_email: Optional[str] = Field(default=None)

    # --- Inbound IMAP (Phase D — populated in a follow-up commit) ---
    contact_inbound_enabled: bool = Field(default=False)
    contact_inbound_host: Optional[str] = Field(default=None)
    contact_inbound_port: int = Field(default=993)
    contact_inbound_username: Optional[str] = Field(default=None)
    contact_inbound_password: Optional[str] = Field(default=None)
    contact_inbound_use_ssl: bool = Field(default=True)
    contact_inbound_folder: str = Field(default="INBOX")
    contact_inbound_processed_folder: Optional[str] = Field(default=None)
    contact_inbound_error_folder: Optional[str] = Field(default=None)
    contact_inbound_poll_interval_minutes: int = Field(default=5)

    @model_validator(mode="after")
    def _require_secret_key_in_production(self) -> "Settings":
        """Phase A-3: refuse to construct Settings when running in
        production without a real ``SECRET_KEY``. Fires during settings
        construction so a misconfigured prod boot fails at import
        rather than after the first signed JWT.

        Dev + test deployments can leave ``SECRET_KEY`` unset; the
        application boot path will surface a clearer error later if
        someone tries to sign without one.
        """
        if (self.app_env or "").lower() == "production":
            if not self.secret_key:
                raise ValueError(
                    "SECRET_KEY must be set when APP_ENV=production."
                )
            if self.secret_key == INSECURE_DEFAULT_SECRET_KEY:
                raise ValueError(
                    "SECRET_KEY is still the public placeholder value — "
                    "generate a unique secret before deploying to production."
                )
            if len(self.secret_key) < MIN_SECRET_KEY_LENGTH:
                raise ValueError(
                    f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} "
                    f"characters when APP_ENV=production."
                )
        return self

    @property
    def cors_origins(self) -> List[str]:
        """Return CORS origins parsed from a comma-separated env value.

        Read directly from os.environ so pydantic-settings never tries
        to JSON-decode the comma-separated string.
        """
        raw = os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Return the resolved SQLAlchemy database URI."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sqlalchemy_async_database_uri(self) -> str:
        """Phase B-1.0: async-engine DSN derived from the sync one.

        Swaps the ``+psycopg2`` driver suffix for ``+asyncpg``. If the
        caller already provided an asyncpg DSN via ``DATABASE_URL``
        (e.g. in CI), it passes through untouched. Vanilla
        ``postgresql://…`` URLs are upgraded to
        ``postgresql+asyncpg://`` so the operator doesn't have to
        remember the driver suffix.
        """
        sync = self.sqlalchemy_database_uri
        if "+asyncpg" in sync:
            return sync
        if "+psycopg2" in sync:
            return sync.replace("+psycopg2", "+asyncpg", 1)
        if sync.startswith("postgresql://"):
            return "postgresql+asyncpg://" + sync[len("postgresql://"):]
        # SQLite / other drivers — caller is expected to pass an
        # already-async-compatible URL (e.g. ``sqlite+aiosqlite://``).
        return sync


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def ensure_production_safety(settings: Settings) -> None:
    """Fail fast at boot when a production deployment is missing the
    minimum security configuration.

    Called from :func:`app.main.create_app`. Outside production we just
    return — the default secret + permissive CORS make local dev + the
    test suite frictionless.
    """
    if settings.app_env.lower() != "production":
        return

    problems: list[str] = []

    if (
        not settings.secret_key
        or settings.secret_key == INSECURE_DEFAULT_SECRET_KEY
        or len(settings.secret_key) < MIN_SECRET_KEY_LENGTH
    ):
        problems.append(
            f"SECRET_KEY must be set to a unique value of at least "
            f"{MIN_SECRET_KEY_LENGTH} characters in production."
        )

    raw_cors = os.getenv("CORS_ORIGINS")
    if not raw_cors:
        problems.append(
            "CORS_ORIGINS must be set explicitly in production — "
            "the localhost defaults are dev-only."
        )
    elif raw_cors.strip() == "*":
        problems.append(
            "CORS_ORIGINS=* is forbidden in production — list the exact "
            "front-end origins instead."
        )

    if problems:
        raise InsecureConfigurationError(
            "Refusing to start the API in production with insecure "
            "configuration:\n  - " + "\n  - ".join(problems)
        )

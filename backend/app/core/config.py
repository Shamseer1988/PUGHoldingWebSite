"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import Field
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
    app_debug: bool = Field(default=True)
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)

    # --- Security ---
    # We keep the insecure default so local dev + the test suite "just
    # work" out of the box. Production deployments MUST override
    # SECRET_KEY — ``ensure_production_safety()`` (called from
    # ``create_app``) refuses to boot if the default leaks into a
    # production environment.
    secret_key: str = Field(default=INSECURE_DEFAULT_SECRET_KEY)
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

    # --- Uploads ---
    upload_dir: str = Field(default="app/uploads")
    max_upload_size_mb: int = Field(default=20)

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

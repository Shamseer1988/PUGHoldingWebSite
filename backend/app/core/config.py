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
    secret_key: str = Field(default="change-me-to-a-strong-random-secret")
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

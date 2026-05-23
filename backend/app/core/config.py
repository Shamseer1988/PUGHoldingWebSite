"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # --- CORS ---
    # Kept as a string so a comma-separated value in .env (e.g.
    # ``CORS_ORIGINS=http://a,http://b``) works without pydantic-settings
    # trying to JSON-decode it. Consumers read ``cors_origins`` (property
    # below) for the parsed list.
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )

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
        """Return CORS origins parsed from the comma-separated env value."""
        return [
            origin.strip()
            for origin in self.cors_origins_raw.split(",")
            if origin.strip()
        ]

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

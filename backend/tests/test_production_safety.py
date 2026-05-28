"""Boot-time safety checks for production configuration.

``ensure_production_safety`` is called from ``create_app`` and is the
single gate that prevents a misconfigured deployment from starting with
a weak SECRET_KEY or missing CORS allowlist. These tests exercise that
function directly so we don't have to import the FastAPI app under
mutated env state (which would poison the lru-cached ``get_settings``
for every other test in the suite).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import (
    INSECURE_DEFAULT_SECRET_KEY,
    InsecureConfigurationError,
    Settings,
    ensure_production_safety,
)


def _settings(**overrides) -> Settings:
    """Build a Settings instance with explicit fields, bypassing the
    .env loader and pydantic env-var resolution. We pass everything we
    care about so the result is deterministic regardless of CI env."""
    defaults: dict = {
        "app_env": "development",
        "secret_key": INSECURE_DEFAULT_SECRET_KEY,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestEnsureProductionSafety:
    def test_noop_in_development_even_with_default_secret(self):
        # Dev should always pass — the dev-friendly default is the
        # point of having a default at all.
        ensure_production_safety(_settings(app_env="development"))

    def test_noop_in_staging(self):
        ensure_production_safety(_settings(app_env="staging"))

    def test_production_rejects_default_secret_key(self, monkeypatch):
        # Phase A-3 moved the secret-key check forward into the
        # Pydantic model validator, so construction itself fails when
        # APP_ENV=production carries the placeholder value. The boot
        # path never reaches ``ensure_production_safety`` in this case.
        monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
        with pytest.raises(ValidationError) as excinfo:
            _settings(
                app_env="production",
                secret_key=INSECURE_DEFAULT_SECRET_KEY,
            )
        assert "SECRET_KEY" in str(excinfo.value)

    def test_production_rejects_missing_secret_key(self, monkeypatch):
        # Same gate, missing-value branch — None should be rejected at
        # construction in production.
        monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
        with pytest.raises(ValidationError) as excinfo:
            _settings(app_env="production", secret_key=None)
        assert "SECRET_KEY" in str(excinfo.value)

    def test_production_rejects_short_secret_key(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
        with pytest.raises(ValidationError) as excinfo:
            _settings(app_env="production", secret_key="too-short")
        assert "SECRET_KEY" in str(excinfo.value)

    def test_production_rejects_missing_cors(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        with pytest.raises(InsecureConfigurationError) as excinfo:
            ensure_production_safety(
                _settings(
                    app_env="production",
                    secret_key="a" * 64,
                )
            )
        assert "CORS_ORIGINS" in str(excinfo.value)

    def test_production_rejects_wildcard_cors(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "*")
        with pytest.raises(InsecureConfigurationError) as excinfo:
            ensure_production_safety(
                _settings(
                    app_env="production",
                    secret_key="a" * 64,
                )
            )
        assert "*" in str(excinfo.value)

    def test_production_passes_with_strong_secret_and_explicit_cors(
        self, monkeypatch
    ):
        monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
        ensure_production_safety(
            _settings(app_env="production", secret_key="a" * 64)
        )

    def test_production_collects_cors_problem_after_valid_secret(
        self, monkeypatch
    ):
        # Phase A-3 split responsibility: secret-key issues fail at
        # Settings() construction (Pydantic validator); CORS issues are
        # still surfaced by ``ensure_production_safety`` because the
        # value is read lazily from os.environ outside the model. So a
        # boot with a strong secret + missing CORS still fails — just
        # in the second gate.
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        with pytest.raises(InsecureConfigurationError) as excinfo:
            ensure_production_safety(
                _settings(
                    app_env="production",
                    secret_key="a" * 64,
                )
            )
        assert "CORS_ORIGINS" in str(excinfo.value)

    def test_case_insensitive_app_env_match(self, monkeypatch):
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        with pytest.raises(InsecureConfigurationError):
            ensure_production_safety(
                _settings(app_env="PRODUCTION", secret_key="a" * 64)
            )

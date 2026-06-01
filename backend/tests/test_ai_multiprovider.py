"""Multi-provider AI — chat + embedding provider selection.

Covers the additions on top of the Phase C-6 abstraction:

1. ``resolve_config`` resolves the ``provider`` discriminator (DB row
   wins, then the ``AI_PROVIDER`` env fallback, then ``azure``).
2. ``get_chat_provider`` routes ``openai_compatible`` / ``ollama`` to
   ``OpenAICompatibleProvider`` (with the Ollama localhost default),
   and raises ``ProviderConfigError`` when base_url / model are
   missing.
3. ``get_embedding_provider`` routes on ``AI_EMBEDDING_PROVIDER``.
4. ``OpenAICompatibleProvider`` delegates to ``openai.OpenAI`` with the
   model id (not an Azure deployment) and the streaming usage opt-in.
5. ``semantic_search`` helpers are provider-aware.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.ai.providers import (
    OpenAICompatibleProvider,
    ProviderError,
    get_chat_provider,
    get_embedding_provider,
)
from app.ai.providers.azure import AzureOpenAIProvider
from app.ai.providers.factory import OLLAMA_DEFAULT_BASE_URL, ProviderConfigError
from app.ai.providers.openai_compatible import OpenAICompatibleConfig


# ---------------------------------------------------------------------------
# resolve_config — provider resolution
# ---------------------------------------------------------------------------


def test_resolve_config_defaults_to_azure(monkeypatch):
    from app.ai.candidate_review import resolve_config
    from app.core.config import get_settings
    from app.models.hr_ats import AISetting

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_provider", None)

    setting = AISetting(id=1, mode="live", provider=None)
    resolved = resolve_config(setting)
    assert resolved.provider == "azure"


def test_resolve_config_db_provider_wins(monkeypatch):
    from app.ai.candidate_review import resolve_config
    from app.core.config import get_settings
    from app.models.hr_ats import AISetting

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_provider", "azure")
    monkeypatch.setattr(settings, "ai_base_url", None)

    setting = AISetting(
        id=1,
        mode="live",
        provider="openai_compatible",
        base_url="http://localhost:8001/v1",
        model_name="llama3.1",
    )
    resolved = resolve_config(setting)
    assert resolved.provider == "openai_compatible"
    assert resolved.base_url == "http://localhost:8001/v1"
    assert resolved.model_name == "llama3.1"


def test_resolve_config_env_fallback(monkeypatch):
    from app.ai.candidate_review import resolve_config
    from app.core.config import get_settings
    from app.models.hr_ats import AISetting

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_provider", "ollama")

    setting = AISetting(id=1, mode="live", provider=None)
    resolved = resolve_config(setting)
    assert resolved.provider == "ollama"


# ---------------------------------------------------------------------------
# get_chat_provider — routing
# ---------------------------------------------------------------------------


def _live_config(**overrides):
    from app.ai.candidate_review import AI_MODE_LIVE, ResolvedAIConfig

    base = dict(
        mode=AI_MODE_LIVE,
        azure_endpoint=None,
        azure_deployment=None,
        azure_api_key=None,
        azure_api_version=None,
        model_name="llama3.1",
        temperature=0.2,
        max_output_tokens=400,
        request_timeout_seconds=45,
        extra_system_prompt=None,
        provider="openai_compatible",
        base_url="http://localhost:8001/v1",
        api_key=None,
    )
    base.update(overrides)
    return ResolvedAIConfig(**base)


def test_get_chat_provider_routes_openai_compatible():
    provider = get_chat_provider(_live_config())
    assert isinstance(provider, OpenAICompatibleProvider)


def test_get_chat_provider_ollama_uses_localhost_default():
    provider = get_chat_provider(
        _live_config(provider="ollama", base_url=None)
    )
    assert isinstance(provider, OpenAICompatibleProvider)
    # No explicit base_url → the factory fills in Ollama's localhost.
    assert provider._config.base_url == OLLAMA_DEFAULT_BASE_URL


def test_get_chat_provider_openai_compatible_requires_base_url():
    with pytest.raises(ProviderConfigError):
        get_chat_provider(_live_config(base_url=None))


def test_get_chat_provider_openai_compatible_requires_model():
    with pytest.raises(ProviderConfigError):
        get_chat_provider(_live_config(model_name=None))


def test_get_chat_provider_rejects_unknown_provider():
    with pytest.raises(ProviderConfigError):
        get_chat_provider(_live_config(provider="anthropic"))


# ---------------------------------------------------------------------------
# get_embedding_provider — routing
# ---------------------------------------------------------------------------


def test_get_embedding_provider_routes_to_openai_compatible(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_embedding_provider", "openai_compatible")
    monkeypatch.setattr(settings, "ai_embedding_base_url", "http://localhost:8001/v1")
    monkeypatch.setattr(settings, "ai_embedding_model", "nomic-embed-text")

    provider = get_embedding_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)


def test_get_embedding_provider_ollama_default_base_url(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_embedding_provider", "ollama")
    monkeypatch.setattr(settings, "ai_embedding_base_url", None)
    monkeypatch.setattr(settings, "ai_embedding_model", "nomic-embed-text")

    provider = get_embedding_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider._config.base_url == OLLAMA_DEFAULT_BASE_URL


def test_get_embedding_provider_openai_compatible_requires_base_url(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_embedding_provider", "openai_compatible")
    monkeypatch.setattr(settings, "ai_embedding_base_url", None)
    monkeypatch.setattr(settings, "ai_embedding_model", "nomic-embed-text")

    with pytest.raises(ProviderConfigError):
        get_embedding_provider(settings)


def test_get_embedding_provider_still_routes_azure_by_default(monkeypatch):
    """Default provider stays azure so existing installs are unchanged."""
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://x.example.com")
    monkeypatch.setattr(settings, "azure_openai_deployment", "embed-ada")
    monkeypatch.setattr(settings, "azure_openai_api_key", "secret")
    provider = get_embedding_provider(settings)
    assert isinstance(provider, AzureOpenAIProvider)


# ---------------------------------------------------------------------------
# OpenAICompatibleProvider — delegation
# ---------------------------------------------------------------------------


def _provider_with_fake_client(monkeypatch):
    fake_client = MagicMock()
    from app.ai.providers import openai_compatible as oai_mod

    monkeypatch.setattr(oai_mod, "_build_client", lambda _cfg: fake_client)
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            base_url="http://localhost:8001/v1",
            api_key="not-needed",
            model="llama3.1",
        )
    )
    return provider, fake_client


def test_oai_complete_passes_model_id(monkeypatch):
    provider, client = _provider_with_fake_client(monkeypatch)
    sentinel = object()
    client.chat.completions.create.return_value = sentinel

    result = provider.complete(
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.3,
        max_tokens=128,
        response_format={"type": "json_object"},
    )
    assert result is sentinel
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "llama3.1"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert "stream" not in kwargs


def test_oai_complete_stream_requests_usage(monkeypatch):
    provider, client = _provider_with_fake_client(monkeypatch)
    client.chat.completions.create.return_value = iter(["a", "b"])

    out = list(
        provider.complete_stream(messages=[{"role": "user", "content": "hi"}])
    )
    assert out == ["a", "b"]
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["stream"] is True
    assert kwargs["stream_options"] == {"include_usage": True}


def test_oai_embed_returns_first_vector(monkeypatch):
    provider, client = _provider_with_fake_client(monkeypatch)
    resp = MagicMock()
    resp.data = [MagicMock(embedding=[0.4, 0.5])]
    client.embeddings.create.return_value = resp

    vec = provider.embed("hello")
    assert vec == [0.4, 0.5]
    kwargs = client.embeddings.create.call_args.kwargs
    assert kwargs["model"] == "llama3.1"


def test_oai_wraps_sdk_errors(monkeypatch):
    provider, client = _provider_with_fake_client(monkeypatch)
    client.chat.completions.create.side_effect = RuntimeError("boom")
    with pytest.raises(ProviderError):
        provider.complete(messages=[{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# semantic_search — provider-aware helpers
# ---------------------------------------------------------------------------


def test_resolve_embedding_model_prefers_env(monkeypatch):
    from app.core.config import get_settings
    from app.services.semantic_search import resolve_embedding_model

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_embedding_model", "nomic-embed-text")
    assert resolve_embedding_model(settings) == "nomic-embed-text"


def test_ai_configured_ollama_needs_only_enabled(monkeypatch):
    from app.core.config import get_settings
    from app.services import semantic_search as ss

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "ai_embedding_provider", "ollama")
    monkeypatch.setattr(settings, "ai_embedding_base_url", None)
    assert ss._ai_configured() is True

    monkeypatch.setattr(settings, "ai_enabled", False)
    assert ss._ai_configured() is False


def test_ai_configured_openai_compatible_needs_base_url(monkeypatch):
    from app.core.config import get_settings
    from app.services import semantic_search as ss

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings, "ai_embedding_provider", "openai_compatible")
    monkeypatch.setattr(settings, "ai_embedding_base_url", None)
    assert ss._ai_configured() is False
    monkeypatch.setattr(settings, "ai_embedding_base_url", "http://localhost:8001/v1")
    assert ss._ai_configured() is True

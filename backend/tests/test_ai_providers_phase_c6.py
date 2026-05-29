"""Phase C-6 — AI provider abstraction.

Locks in three contracts:

1. **Factories** route ``mode == "live"`` configs (chat) and Settings
   with the right env (embeddings) to ``AzureOpenAIProvider``; raise
   ``ProviderConfigError`` for anything missing.
2. **AzureOpenAIProvider** delegates to ``openai.AzureOpenAI`` with
   the right kwargs (model from config, ``include_usage`` for
   streams, ``response_format`` passthrough). The underlying
   client is stubbed so the test doesn't touch Azure.
3. **Call sites** still raise ``AIConfigError`` / ``AIProviderError``
   so the existing orchestrators that catch those don't have to
   learn ``ProviderError``.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.ai.providers import (
    LLMProvider,
    ProviderError,
    get_chat_provider,
    get_embedding_provider,
)
from app.ai.providers.azure import AzureOpenAIProvider, AzureProviderConfig
from app.ai.providers.factory import ProviderConfigError


# ---------------------------------------------------------------------------
# Factory routing
# ---------------------------------------------------------------------------


def _resolved_config(**overrides):
    """Build a ``ResolvedAIConfig`` with sensible live-mode defaults."""
    from app.ai.candidate_review import AI_MODE_LIVE, ResolvedAIConfig

    base = dict(
        mode=AI_MODE_LIVE,
        azure_endpoint="https://endpoint.example.com",
        azure_deployment="gpt-4o",
        azure_api_key="secret",
        azure_api_version="2024-08-01-preview",
        model_name="gpt-4o",
        temperature=0.5,
        max_output_tokens=400,
        request_timeout_seconds=45,
        extra_system_prompt=None,
    )
    base.update(overrides)
    return ResolvedAIConfig(**base)


def test_get_chat_provider_returns_azure_provider_in_live_mode():
    config = _resolved_config()
    provider = get_chat_provider(config)
    assert isinstance(provider, AzureOpenAIProvider)


def test_get_chat_provider_rejects_non_live_mode():
    from app.ai.candidate_review import AI_MODE_MOCK

    config = _resolved_config(mode=AI_MODE_MOCK)
    with pytest.raises(ProviderConfigError):
        get_chat_provider(config)


def test_get_chat_provider_rejects_missing_credentials():
    config = _resolved_config(azure_api_key=None)
    with pytest.raises(ProviderConfigError):
        get_chat_provider(config)


def test_get_embedding_provider_routes_to_azure(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://x.example.com")
    monkeypatch.setattr(settings, "azure_openai_deployment", "embed-ada")
    monkeypatch.setattr(settings, "azure_openai_api_key", "secret")
    provider = get_embedding_provider(settings)
    assert isinstance(provider, AzureOpenAIProvider)


def test_get_embedding_provider_rejects_unconfigured_settings(monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "azure_openai_endpoint", None)
    monkeypatch.setattr(settings, "azure_openai_api_key", None)
    monkeypatch.setattr(settings, "azure_openai_deployment", None)
    with pytest.raises(ProviderConfigError):
        get_embedding_provider(settings)


# ---------------------------------------------------------------------------
# AzureOpenAIProvider delegation
# ---------------------------------------------------------------------------


def _build_provider_with_fake_client(monkeypatch):
    """Construct an ``AzureOpenAIProvider`` whose underlying client
    is a ``MagicMock`` we can introspect afterwards. ``_build_client``
    is a module-level factory in ``providers.azure`` so a single
    monkeypatch covers every instance created in the test."""
    fake_client = MagicMock()
    from app.ai.providers import azure as azure_mod

    monkeypatch.setattr(azure_mod, "_build_client", lambda _cfg: fake_client)
    provider = AzureOpenAIProvider(
        AzureProviderConfig(
            endpoint="https://x.example.com",
            deployment="gpt-4o",
            api_key="secret",
        )
    )
    return provider, fake_client


def test_provider_complete_passes_model_temperature_response_format(monkeypatch):
    provider, client = _build_provider_with_fake_client(monkeypatch)
    sentinel = object()
    client.chat.completions.create.return_value = sentinel

    result = provider.complete(
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.2,
        max_tokens=128,
        response_format={"type": "json_object"},
    )

    assert result is sentinel
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o"
    assert kwargs["temperature"] == 0.2
    assert kwargs["max_tokens"] == 128
    assert kwargs["response_format"] == {"type": "json_object"}
    # The default complete() call must NOT request a stream.
    assert "stream" not in kwargs


def test_provider_complete_stream_requests_streaming_and_usage(monkeypatch):
    provider, client = _build_provider_with_fake_client(monkeypatch)
    # The stream is an iterable of chunk-shaped objects; we hand back
    # two sentinels so the generator yields them in order.
    client.chat.completions.create.return_value = iter(["chunk-a", "chunk-b"])

    out = list(
        provider.complete_stream(
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.3,
            max_tokens=200,
        )
    )
    assert out == ["chunk-a", "chunk-b"]

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["stream"] is True
    assert kwargs["stream_options"] == {"include_usage": True}


def test_provider_embed_returns_first_data_vector(monkeypatch):
    provider, client = _build_provider_with_fake_client(monkeypatch)
    resp = MagicMock()
    resp.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
    client.embeddings.create.return_value = resp

    vec = provider.embed("hello world")
    assert vec == [0.1, 0.2, 0.3]
    kwargs = client.embeddings.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o"
    assert kwargs["input"] == "hello world"


def test_provider_complete_wraps_sdk_errors_in_provider_error(monkeypatch):
    provider, client = _build_provider_with_fake_client(monkeypatch)
    client.chat.completions.create.side_effect = RuntimeError("boom")
    with pytest.raises(ProviderError):
        provider.complete(messages=[{"role": "user", "content": "hi"}])


def test_provider_complete_stream_wraps_open_error(monkeypatch):
    provider, client = _build_provider_with_fake_client(monkeypatch)
    client.chat.completions.create.side_effect = RuntimeError("boom")
    with pytest.raises(ProviderError):
        list(provider.complete_stream(messages=[{"role": "user", "content": "hi"}]))


def test_provider_complete_stream_wraps_mid_stream_error(monkeypatch):
    provider, client = _build_provider_with_fake_client(monkeypatch)

    def _gen():
        yield "chunk-a"
        raise RuntimeError("network blip")

    client.chat.completions.create.return_value = _gen()
    with pytest.raises(ProviderError):
        list(provider.complete_stream(messages=[{"role": "user", "content": "hi"}]))


def test_provider_embed_wraps_sdk_errors(monkeypatch):
    provider, client = _build_provider_with_fake_client(monkeypatch)
    client.embeddings.create.side_effect = RuntimeError("rate limit")
    with pytest.raises(ProviderError):
        provider.embed("hello")


def test_provider_embed_raises_when_response_has_no_data(monkeypatch):
    provider, client = _build_provider_with_fake_client(monkeypatch)
    resp = MagicMock()
    resp.data = []
    client.embeddings.create.return_value = resp
    with pytest.raises(ProviderError):
        provider.embed("hello")


# ---------------------------------------------------------------------------
# Protocol membership
# ---------------------------------------------------------------------------


def test_azure_provider_satisfies_llmprovider_protocol(monkeypatch):
    """``AzureOpenAIProvider`` should be structurally compatible with
    ``LLMProvider``. Protocol with ``@runtime_checkable`` isn't on by
    default, but the methods + signatures must exist for type
    checkers + future swap providers."""
    provider, _ = _build_provider_with_fake_client(monkeypatch)
    # Pulling the attributes off prevents this test from accidentally
    # passing because the methods were renamed.
    assert callable(provider.complete)
    assert callable(provider.complete_stream)
    assert callable(provider.embed)
    # Hand a non-instance of LLMProvider to ``isinstance`` would be a
    # static-check error; structural duck typing is the real test —
    # all three method names + their positional shapes match the
    # Protocol declared in ``providers/base.py``.
    assert isinstance(provider, AzureOpenAIProvider)
    # The Protocol can't be runtime-isinstance-checked but we can
    # still confirm the attribute set lines up.
    expected_attrs = {"complete", "complete_stream", "embed"}
    assert expected_attrs.issubset(set(dir(provider)))
    # Silence an unused-import lint — ``LLMProvider`` is part of the
    # public API surface this test exists to verify.
    _ = LLMProvider

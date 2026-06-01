"""Provider factories (multi-provider).

Two functions translate the existing config types
(``ResolvedAIConfig`` for chat, ``Settings`` for embeddings) into a
concrete provider instance, routing on a ``provider`` discriminator:

  * ``azure``              → :class:`AzureOpenAIProvider`
  * ``openai_compatible``  → :class:`OpenAICompatibleProvider`
  * ``ollama``             → :class:`OpenAICompatibleProvider` with a
                             localhost default base URL

Adding a genuinely different provider (one that does NOT speak the
OpenAI dialect — e.g. Anthropic, Google) is a matter of adding a
sibling provider class + one ``elif`` branch here. No call site
changes: every provider returns the openai SDK's native response
shapes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.ai.providers.azure import AzureOpenAIProvider, AzureProviderConfig
from app.ai.providers.base import LLMProvider, EmbeddingProvider
from app.ai.providers.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)
from app.models.hr_ats import (
    AI_PROVIDER_AZURE,
    AI_PROVIDER_OLLAMA,
    AI_PROVIDER_OPENAI_COMPATIBLE,
)


if TYPE_CHECKING:  # pragma: no cover
    from app.ai.candidate_review import ResolvedAIConfig
    from app.core.config import Settings


# Ollama's OpenAI-compatible surface. Used as the base-URL default
# when ``provider = ollama`` and no explicit base URL was supplied —
# the common "Ollama is running locally" case then needs zero config.
OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434/v1"

# OpenAI-compatible servers commonly run without auth (vLLM, LM Studio,
# Ollama). The OpenAI SDK still requires a non-empty api_key string, so
# we pass this harmless placeholder when none is configured. Servers
# that DO require a key get the real one from ``AI_API_KEY`` / the DB.
_PLACEHOLDER_API_KEY = "not-needed"


class ProviderConfigError(Exception):
    """Raised when the config can't satisfy the selected provider —
    typically because endpoint / deployment / base_url / model are
    unset."""


def _normalise_provider(value: Optional[str]) -> str:
    return (value or AI_PROVIDER_AZURE).strip().lower()


def get_chat_provider(config: "ResolvedAIConfig") -> LLMProvider:
    """Build a chat provider from a resolved AI config.

    Only the LIVE branch routes through here — mock / disabled callers
    shouldn't reach this function, and we raise if they do so the
    mistake is loud rather than silent (a mock test accidentally
    hitting a real endpoint would be bad).
    """
    from app.ai.candidate_review import AI_MODE_LIVE

    if config.mode != AI_MODE_LIVE:
        raise ProviderConfigError(
            f"get_chat_provider called with mode={config.mode!r}; "
            "only 'live' mode routes through the provider abstraction."
        )

    provider = _normalise_provider(config.provider)

    if provider == AI_PROVIDER_AZURE:
        if not (
            config.azure_endpoint
            and config.azure_deployment
            and config.azure_api_key
        ):
            raise ProviderConfigError(
                "AI is set to 'live' with the Azure provider but Azure "
                "endpoint / deployment / API key are not configured."
            )
        return AzureOpenAIProvider(
            AzureProviderConfig(
                endpoint=config.azure_endpoint,
                deployment=config.azure_deployment,
                api_key=config.azure_api_key,
                api_version=config.azure_api_version or "2024-08-01-preview",
                request_timeout_seconds=config.request_timeout_seconds,
            )
        )

    if provider in (AI_PROVIDER_OPENAI_COMPATIBLE, AI_PROVIDER_OLLAMA):
        base_url = config.base_url or (
            OLLAMA_DEFAULT_BASE_URL if provider == AI_PROVIDER_OLLAMA else None
        )
        if not base_url:
            raise ProviderConfigError(
                "AI is set to 'live' with the 'openai_compatible' provider "
                "but no base URL is configured. Set it in AI settings or "
                "AI_BASE_URL in .env."
            )
        if not config.model_name:
            raise ProviderConfigError(
                f"AI is set to 'live' with the {provider!r} provider but no "
                "model name is configured. Set the model in AI settings or "
                "AI_MODEL in .env."
            )
        return OpenAICompatibleProvider(
            OpenAICompatibleConfig(
                base_url=base_url,
                api_key=config.api_key or _PLACEHOLDER_API_KEY,
                model=config.model_name,
                request_timeout_seconds=config.request_timeout_seconds,
            )
        )

    raise ProviderConfigError(f"Unknown AI provider: {provider!r}")


def get_embedding_provider(
    settings: "Settings",
    *,
    deployment_override: str | None = None,
) -> EmbeddingProvider:
    """Build an embedding provider from process settings.

    Embeddings don't carry the per-DB-row AISetting overrides that chat
    does — they're driven entirely by the ``AI_EMBEDDING_*`` env vars
    (and, for the Azure provider, the existing ``AZURE_OPENAI_*`` ones).
    ``deployment_override`` is the resolved model/deployment name the
    semantic-search service computes; it applies to whichever provider
    is selected.
    """
    provider = _normalise_provider(settings.ai_embedding_provider)

    if provider == AI_PROVIDER_AZURE:
        deployment = (
            deployment_override
            or settings.ai_embedding_model
            or settings.azure_openai_deployment
            or ""
        )
        if not (
            settings.azure_openai_endpoint
            and deployment
            and settings.azure_openai_api_key
        ):
            raise ProviderConfigError(
                "Embeddings (Azure provider) require AZURE_OPENAI_ENDPOINT / "
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT (or *_DEPLOYMENT) / "
                "AZURE_OPENAI_API_KEY to be set."
            )
        return AzureOpenAIProvider(
            AzureProviderConfig(
                endpoint=settings.azure_openai_endpoint,
                deployment=deployment,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version
                or "2024-08-01-preview",
                request_timeout_seconds=30,
            )
        )

    if provider in (AI_PROVIDER_OPENAI_COMPATIBLE, AI_PROVIDER_OLLAMA):
        base_url = settings.ai_embedding_base_url or (
            OLLAMA_DEFAULT_BASE_URL if provider == AI_PROVIDER_OLLAMA else None
        )
        model = deployment_override or settings.ai_embedding_model
        if not base_url:
            raise ProviderConfigError(
                "Embeddings ('openai_compatible' provider) require "
                "AI_EMBEDDING_BASE_URL to be set."
            )
        if not model:
            raise ProviderConfigError(
                f"Embeddings ({provider!r} provider) require AI_EMBEDDING_MODEL "
                "to be set."
            )
        return OpenAICompatibleProvider(
            OpenAICompatibleConfig(
                base_url=base_url,
                api_key=settings.ai_embedding_api_key or _PLACEHOLDER_API_KEY,
                model=model,
                request_timeout_seconds=30,
            )
        )

    raise ProviderConfigError(f"Unknown embedding provider: {provider!r}")

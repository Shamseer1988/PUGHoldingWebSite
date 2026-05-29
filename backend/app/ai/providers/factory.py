"""Provider factories (Phase C-6).

Two thin functions that translate the existing config types
(``ResolvedAIConfig`` for chat, ``Settings`` for embeddings) into
the ``AzureProviderConfig`` shape ``AzureOpenAIProvider`` consumes.

Adding a second provider — OpenAI direct, Anthropic, etc. — is a
matter of:

  1. Adding a ``provider_type`` discriminator to ``AISetting``
     (and ``Settings`` for embeddings).
  2. Adding a sibling ``OpenAIProvider`` class.
  3. Routing in these factories on the discriminator.

No call site changes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.ai.providers.azure import AzureOpenAIProvider, AzureProviderConfig
from app.ai.providers.base import LLMProvider


if TYPE_CHECKING:  # pragma: no cover
    from app.ai.candidate_review import ResolvedAIConfig
    from app.core.config import Settings


class ProviderConfigError(Exception):
    """Raised when the config can't satisfy any concrete provider —
    typically because endpoint / deployment / API key are unset."""


def get_chat_provider(config: "ResolvedAIConfig") -> LLMProvider:
    """Build a chat provider from a resolved AI config.

    Only the LIVE branch routes through here — mock / disabled
    callers shouldn't reach this function, and we raise if they
    do so the mistake is loud rather than silent (a mock test
    accidentally hitting the real Azure endpoint would be bad).
    """
    from app.ai.candidate_review import AI_MODE_LIVE

    if config.mode != AI_MODE_LIVE:
        raise ProviderConfigError(
            f"get_chat_provider called with mode={config.mode!r}; "
            "only 'live' mode routes through the provider abstraction."
        )

    if not (
        config.azure_endpoint
        and config.azure_deployment
        and config.azure_api_key
    ):
        raise ProviderConfigError(
            "AI is set to 'live' but Azure endpoint / deployment / API key are not configured."
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


def get_embedding_provider(
    settings: "Settings",
    *,
    deployment_override: str | None = None,
) -> AzureOpenAIProvider:
    """Build an embedding provider from process settings.

    Embeddings don't carry the per-DB-row AISetting overrides that
    chat does — they're driven entirely by ``settings.azure_openai_*``
    + an optional deployment override (the ``AZURE_OPENAI_EMBEDDING_DEPLOYMENT``
    env var the semantic-search service reads). The return type is
    the concrete ``AzureOpenAIProvider`` so callers can use either
    its ``embed`` method (the common case) or its chat methods (if
    a future caller wants both off the same client).
    """
    deployment = (
        deployment_override
        or settings.azure_openai_deployment
        or ""
    )
    if not (
        settings.azure_openai_endpoint
        and deployment
        and settings.azure_openai_api_key
    ):
        raise ProviderConfigError(
            "Embeddings require AZURE_OPENAI_ENDPOINT / "
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT (or *_DEPLOYMENT) / "
            "AZURE_OPENAI_API_KEY to be set."
        )

    return AzureOpenAIProvider(
        AzureProviderConfig(
            endpoint=settings.azure_openai_endpoint,
            deployment=deployment,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version or "2024-08-01-preview",
            request_timeout_seconds=30,
        )
    )

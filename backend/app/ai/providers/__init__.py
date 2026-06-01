"""LLM provider abstraction (Phase C-6).

The codebase previously couldn't swap providers without rewriting
the three call sites that build their own ``AzureOpenAI`` client
inline (candidate auto-review, public assistant, semantic search).
This package wraps the three operations they actually need —
``complete``, ``complete_stream``, ``embed`` — behind a Protocol so
a future ``OpenAIProvider`` / ``AnthropicProvider`` /
``GoogleProvider`` is a drop-in.

Providers:

* ``LLMProvider`` / ``EmbeddingProvider`` Protocols — the interfaces
  every concrete provider satisfies.
* ``AzureOpenAIProvider`` — wraps the ``AzureOpenAI`` SDK.
* ``OpenAICompatibleProvider`` — wraps the ``OpenAI`` SDK pointed at
  an arbitrary ``base_url``; serves both the ``openai_compatible``
  (vLLM / LM Studio / OpenAI direct) and ``ollama`` providers. Same
  exception shape (``ProviderError``) as Azure so call sites don't
  learn a new error vocabulary.
* ``get_chat_provider(config)`` — factory keyed on
  ``ResolvedAIConfig.mode`` + ``.provider``. Live mode returns the
  provider matching the discriminator; mock / disabled raise the
  appropriate config error so the call site can fall back to its
  module-local mock path.
* ``get_embedding_provider()`` — sibling factory for the embedding
  surface, keyed on ``Settings.ai_embedding_provider`` (semantic
  search is unauthenticated and runs in worker contexts that don't
  open an ``AISetting`` row, so its provider is env-driven and
  independent of chat).

Mock + disabled stay implemented as inline branches in each call
site. They generate prompt-specific outputs that the abstraction
can't reasonably template, so collapsing them under a
``MockLLMProvider`` would just move the per-module shaping
elsewhere. The provider abstraction exists to make the LIVE
swap easy, which is the actual user need.
"""
from __future__ import annotations

from app.ai.providers.azure import AzureOpenAIProvider
from app.ai.providers.base import (
    EmbeddingProvider,
    LLMProvider,
    ProviderError,
)
from app.ai.providers.factory import (
    get_chat_provider,
    get_embedding_provider,
)
from app.ai.providers.openai_compatible import OpenAICompatibleProvider


__all__ = [
    "AzureOpenAIProvider",
    "EmbeddingProvider",
    "LLMProvider",
    "OpenAICompatibleProvider",
    "ProviderError",
    "get_chat_provider",
    "get_embedding_provider",
]

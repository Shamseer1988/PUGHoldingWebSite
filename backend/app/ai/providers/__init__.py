"""LLM provider abstraction (Phase C-6).

The codebase previously couldn't swap providers without rewriting
the three call sites that build their own ``AzureOpenAI`` client
inline (candidate auto-review, public assistant, semantic search).
This package wraps the three operations they actually need —
``complete``, ``complete_stream``, ``embed`` — behind a Protocol so
a future ``OpenAIProvider`` / ``AnthropicProvider`` /
``GoogleProvider`` is a drop-in.

Scope of the initial slice:

* ``LLMProvider`` Protocol — the interface every concrete provider
  satisfies.
* ``AzureOpenAIProvider`` — the only concrete implementation
  today, wrapping the existing ``AzureOpenAI`` SDK calls. Same
  exception shape (``AIConfigError`` / ``AIProviderError``) so
  call sites don't have to learn a new error vocabulary.
* ``get_chat_provider(config)`` — factory keyed on the
  ``ResolvedAIConfig.mode`` + (future) ``provider_type`` field.
  Live mode returns the Azure provider; mock / disabled raise the
  appropriate config error so the call site can fall back to its
  module-local mock path.
* ``get_embedding_provider()`` — sibling factory for the embedding
  surface, which reads provider settings off ``Settings`` instead
  of ``AISetting`` (semantic search is unauthenticated, runs
  in worker contexts that don't open a DB session for it).

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


__all__ = [
    "AzureOpenAIProvider",
    "EmbeddingProvider",
    "LLMProvider",
    "ProviderError",
    "get_chat_provider",
    "get_embedding_provider",
]

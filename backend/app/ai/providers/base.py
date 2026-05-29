"""Provider Protocol + shared error type (Phase C-6).

The Protocol intentionally returns the OpenAI SDK's own
``ChatCompletion`` and ``ChatCompletionChunk`` shapes — every
existing call site already unpacks them (``completion.choices[0].
message.content``, ``chunk.choices[0].delta.content``, etc.) and we
don't want to invent a parallel response type that providers have
to translate to and call sites have to unpack again. Concrete
non-Azure providers (when they land) translate their own SDK's
shape into the same fields; that's the only adapter work needed.
"""
from __future__ import annotations

from typing import Any, Iterator, List, Mapping, Optional, Protocol


class ProviderError(Exception):
    """Raised when a concrete provider fails at request time.

    Distinct from ``AIConfigError`` (raised when the provider can't
    even start — missing endpoint / key / deployment). Callers
    typically fall back on a mock or canned response when this
    surfaces.
    """


class LLMProvider(Protocol):
    """Chat-completion surface shared by every provider.

    Implementations may raise ``ProviderError`` from any method.
    Configuration (endpoint, API key, model name) is held inside
    each provider instance; callers only pass per-request data.
    """

    def complete(
        self,
        messages: List[Mapping[str, Any]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 400,
        response_format: Optional[Mapping[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        """Blocking chat completion.

        Returns the provider's native ``ChatCompletion`` object —
        the same shape ``openai.AzureOpenAI`` already returns.
        """
        ...

    def complete_stream(
        self,
        messages: List[Mapping[str, Any]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 400,
        timeout: Optional[int] = None,
    ) -> Iterator[Any]:
        """Streaming chat completion.

        Yields per-chunk objects whose ``.choices[0].delta.content``
        contains the next token piece and whose final frame (when
        ``include_usage`` is on) carries ``.usage`` with
        ``prompt_tokens`` / ``completion_tokens``.
        """
        ...


class EmbeddingProvider(Protocol):
    """Embedding surface — separate from ``LLMProvider`` because
    the semantic-search path runs from worker contexts that don't
    open a chat-mode ``AISetting`` row and the responsibility
    naturally splits."""

    def embed(self, text: str, *, timeout: Optional[int] = None) -> List[float]:
        """Return the 1-D embedding for ``text``."""
        ...

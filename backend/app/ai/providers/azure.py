"""Azure OpenAI provider implementation (Phase C-6).

Wraps the lazy-imported ``openai.AzureOpenAI`` client. Keeps the
same return shapes the existing call sites expect (the openai SDK's
own ``ChatCompletion`` / ``ChatCompletionChunk`` / ``Embedding``)
so the refactor is a one-line per call site instead of
"translate every field".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, List, Mapping, Optional

from app.ai.providers.base import ProviderError


@dataclass(slots=True)
class AzureProviderConfig:
    """Bundle of the connection params the Azure SDK constructor
    needs. Built from ``ResolvedAIConfig`` (chat) or ``Settings``
    (embeddings) — see ``factory.py``."""

    endpoint: str
    deployment: str
    api_key: str
    api_version: str = "2024-08-01-preview"
    request_timeout_seconds: int = 45


def _build_client(config: AzureProviderConfig):
    """Construct the underlying ``AzureOpenAI`` client.

    Lazy SDK import so module load doesn't fail when the package
    isn't installed (the dev image installs it, the lightweight
    test runner may not).
    """
    try:
        from openai import AzureOpenAI  # noqa: WPS433 — lazy by design
    except ImportError as exc:  # pragma: no cover - covered by image build
        raise ProviderError(
            "openai package is not installed. Run `pip install -r requirements.txt`."
        ) from exc

    return AzureOpenAI(
        api_key=config.api_key,
        api_version=config.api_version,
        azure_endpoint=config.endpoint,
        timeout=config.request_timeout_seconds,
    )


class AzureOpenAIProvider:
    """LLMProvider + EmbeddingProvider over Azure OpenAI.

    A single instance can serve both surfaces — the call site picks
    the method it needs. Re-using one client across many requests
    is the documented Azure SDK best practice (connection pooling,
    auth caching).
    """

    def __init__(self, config: AzureProviderConfig) -> None:
        self._config = config
        self._client = _build_client(config)

    # ---- chat -----------------------------------------------------------

    def complete(
        self,
        messages: List[Mapping[str, Any]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 400,
        response_format: Optional[Mapping[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        try:
            return self._client.chat.completions.create(
                model=self._config.deployment,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                messages=list(messages),
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001 — re-raise as ProviderError
            raise ProviderError(f"Azure OpenAI call failed: {exc}") from exc

    def complete_stream(
        self,
        messages: List[Mapping[str, Any]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 400,
        timeout: Optional[int] = None,
    ) -> Iterator[Any]:
        try:
            stream = self._client.chat.completions.create(
                model=self._config.deployment,
                temperature=temperature,
                max_tokens=max_tokens,
                # ``include_usage`` makes the API append a final
                # frame carrying ``prompt_tokens`` / ``completion_tokens``.
                # Streaming callers read it off the trailing chunk.
                stream=True,
                stream_options={"include_usage": True},
                messages=list(messages),
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                f"Azure OpenAI stream open failed: {exc}"
            ) from exc

        try:
            for chunk in stream:
                yield chunk
        except Exception as exc:  # noqa: BLE001 — stream-mid failures
            raise ProviderError(
                f"Azure OpenAI stream interrupted: {exc}"
            ) from exc

    # ---- embeddings -----------------------------------------------------

    def embed(self, text: str, *, timeout: Optional[int] = None) -> List[float]:
        try:
            resp = self._client.embeddings.create(
                input=text,
                model=self._config.deployment,
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                f"Azure OpenAI embeddings call failed: {exc}"
            ) from exc

        if not resp.data:
            raise ProviderError("Azure OpenAI embeddings returned no data.")
        return list(resp.data[0].embedding)

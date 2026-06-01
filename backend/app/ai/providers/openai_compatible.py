"""OpenAI-compatible provider implementation (multi-provider).

Wraps the lazy-imported ``openai.OpenAI`` client pointed at an
arbitrary ``base_url``. This single class serves every server that
speaks the OpenAI REST dialect:

* **openai_compatible** — vLLM, LM Studio, Together, OpenAI direct,
  or any gateway exposing ``/v1/chat/completions`` + ``/v1/embeddings``.
* **ollama** — a local Ollama daemon, which exposes the same dialect
  at ``http://localhost:11434/v1``. The factory supplies that default
  base URL so "provider = ollama" works with zero extra config.

The return shapes are identical to :class:`AzureOpenAIProvider`
(the openai SDK's own ``ChatCompletion`` / ``ChatCompletionChunk`` /
embedding objects) so every existing call site unpacks them without
a per-provider branch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, List, Mapping, Optional

from app.ai.providers.base import ProviderError


@dataclass(slots=True)
class OpenAICompatibleConfig:
    """Connection params for the ``openai.OpenAI`` constructor.

    ``model`` is the model id passed on every request (e.g.
    ``gpt-4o-mini``, ``llama3.1``, ``nomic-embed-text``) — unlike
    Azure, an OpenAI-compatible server takes the model name directly
    rather than a deployment alias.
    """

    base_url: str
    api_key: str
    model: str
    request_timeout_seconds: int = 45


def _build_client(config: OpenAICompatibleConfig):
    """Construct the underlying ``OpenAI`` client.

    Lazy SDK import so module load doesn't fail when the package isn't
    installed (mirrors ``providers.azure._build_client`` — the dev
    image installs it, a lightweight runner may not).
    """
    try:
        from openai import OpenAI  # noqa: WPS433 — lazy by design
    except ImportError as exc:  # pragma: no cover - covered by image build
        raise ProviderError(
            "openai package is not installed. Run `pip install -r requirements.txt`."
        ) from exc

    return OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.request_timeout_seconds,
    )


class OpenAICompatibleProvider:
    """LLMProvider + EmbeddingProvider over any OpenAI-compatible API.

    Construction stores config + builds the client once; re-using a
    single client across requests is the documented SDK best practice.
    """

    def __init__(self, config: OpenAICompatibleConfig) -> None:
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
                model=self._config.model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
                messages=list(messages),
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001 — re-raise as ProviderError
            raise ProviderError(
                f"OpenAI-compatible call failed: {exc}"
            ) from exc

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
                model=self._config.model,
                temperature=temperature,
                max_tokens=max_tokens,
                # ``include_usage`` makes the API append a final frame
                # carrying token counts. vLLM + recent Ollama support
                # it; servers that don't simply omit the usage frame,
                # which the streaming caller already reads defensively.
                stream=True,
                stream_options={"include_usage": True},
                messages=list(messages),
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                f"OpenAI-compatible stream open failed: {exc}"
            ) from exc

        try:
            for chunk in stream:
                yield chunk
        except Exception as exc:  # noqa: BLE001 — stream-mid failures
            raise ProviderError(
                f"OpenAI-compatible stream interrupted: {exc}"
            ) from exc

    # ---- embeddings -----------------------------------------------------

    def embed(self, text: str, *, timeout: Optional[int] = None) -> List[float]:
        try:
            resp = self._client.embeddings.create(
                input=text,
                model=self._config.model,
                timeout=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                f"OpenAI-compatible embeddings call failed: {exc}"
            ) from exc

        if not resp.data:
            raise ProviderError(
                "OpenAI-compatible embeddings returned no data."
            )
        return list(resp.data[0].embedding)

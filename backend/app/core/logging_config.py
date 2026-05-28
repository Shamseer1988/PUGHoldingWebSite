"""Structured logging via structlog (Phase A-4).

Two output modes selected from ``APP_ENV``:

* **Production** — JSON one line per log record. Datadog / Loki /
  CloudWatch all parse this directly. Useful fields (``event``,
  ``logger``, ``timestamp``, ``level``, plus anything bound on the
  logger or via ``contextvars``) come through as first-class keys.

* **Development** — pretty colourised console output via
  ``structlog.dev.ConsoleRenderer``. Same fields, more humane format.

The module also configures the stdlib ``logging`` package to route
its records through the same structlog pipeline. That matters because
many libraries (FastAPI, uvicorn, SQLAlchemy, OpenAI SDK, …) log via
``logging.getLogger(__name__)``; without that bridge their lines
would still print as flat strings instead of structured JSON.

Request correlation
===================

``bind_request_id(request_id)`` binds the current request's id to a
``contextvars`` slot — every log line emitted on this asyncio task /
thread for the duration of the request will then carry ``request_id``
as a structured field. ``clear_request_id()`` unsets it.

A small FastAPI dependency :func:`logging_request_context` ties this
to ``request.state.request_id`` (set by ``RequestIDMiddleware``) so a
route only has to ``Depends(logging_request_context)`` to get correct
correlation in any logger it touches.
"""
from __future__ import annotations

import contextvars
import logging
import sys
from typing import Any, Iterator

import structlog
from fastapi import Request


_REQUEST_ID_CTX: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "pug_request_id", default=None
)

_CONFIGURED = False


def _request_id_processor(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor: stamp the current ``request_id`` (if any)
    onto every event dict. No-op when nothing is bound — e.g. logs
    emitted by background jobs or before the middleware fires."""
    request_id = _REQUEST_ID_CTX.get()
    if request_id and "request_id" not in event_dict:
        event_dict["request_id"] = request_id
    return event_dict


def configure_logging(*, app_env: str | None = None) -> None:
    """Idempotent setup of structlog + the stdlib logging bridge.

    Call from ``app.main.create_app`` (and the test conftest) before
    any module logs anything you care about. Subsequent calls are
    no-ops — re-running the configuration would just create a tower
    of duplicate handlers on the root logger.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    env = (app_env or "development").lower()
    is_production = env == "production"

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _request_id_processor,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        # ``colors=True`` only emits ANSI when stderr is a TTY.
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    # Structlog loggers run shared processors then hand an UNRENDERED
    # event dict to the stdlib handler via ``wrap_for_formatter``.
    # The stdlib ProcessorFormatter then applies the renderer once.
    # This avoids the double-render that happens when the structlog
    # pipeline emits a pre-rendered string and the stdlib formatter
    # then runs the renderer over it again.
    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Foreign (stdlib) loggers go through ``foreign_pre_chain`` so the
    # request_id / timestamp / level fields are stamped before the
    # renderer turns them into a line.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    # Drop any handler set up by a previous configuration (e.g.
    # ``logging.basicConfig`` called from another module at import).
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(logging.INFO if is_production else logging.DEBUG)

    # Quiet down a few notoriously chatty libraries so the dev console
    # doesn't drown the important lines. Production tuning happens via
    # env (LOG_LEVEL_xxxxx) in a later phase.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to ``name``.

    Use this in place of ``logging.getLogger(__name__)`` across the
    codebase. The first call lazily triggers :func:`configure_logging`
    so a module-level ``logger = get_logger(__name__)`` works even when
    importer order skips ``app.main``.
    """
    if not _CONFIGURED:
        # Best-effort configure with whatever env we can see now —
        # may be re-called by ``create_app`` with the resolved value.
        import os

        configure_logging(app_env=os.getenv("APP_ENV"))
    return structlog.stdlib.get_logger(name)


# ---------------------------------------------------------------------------
# Request-ID binding
# ---------------------------------------------------------------------------


def bind_request_id(request_id: str | None) -> contextvars.Token:
    """Bind the current request id onto the contextvar slot so every
    subsequent log line on this task / thread carries it.

    Returns the contextvar ``Token`` so the caller can restore the
    previous value via :func:`clear_request_id`.
    """
    return _REQUEST_ID_CTX.set(request_id)


def clear_request_id(token: contextvars.Token) -> None:
    """Restore the previous value of the contextvar — call from the
    middleware after the request completes so a worker thread doesn't
    carry one request's id into the next."""
    _REQUEST_ID_CTX.reset(token)


def logging_request_context(request: Request) -> Iterator[str | None]:
    """FastAPI dependency: bind ``request.state.request_id`` for the
    duration of the request and unbind afterwards.

    Routes that want their logs auto-tagged just declare
    ``_=Depends(logging_request_context)`` in the signature — no other
    plumbing.
    """
    rid = getattr(request.state, "request_id", None)
    token = bind_request_id(rid)
    try:
        yield rid
    finally:
        clear_request_id(token)


__all__ = [
    "bind_request_id",
    "clear_request_id",
    "configure_logging",
    "get_logger",
    "logging_request_context",
]

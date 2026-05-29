"""ARQ worker settings (Phase B-3).

Defines the configuration ARQ reads at startup. The functions
registered here become available for ``enqueue_job`` calls from
the FastAPI side.
"""
from __future__ import annotations

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.worker.tasks import (
    generate_ai_review_task,
    optimise_image_task,
    send_email_task,
)


_settings = get_settings()


def _redis_settings() -> RedisSettings:
    """Parse ``settings.redis_url`` into the structured
    ``RedisSettings`` shape ARQ expects."""
    return RedisSettings.from_dsn(_settings.redis_url)


async def _on_startup(_ctx: dict) -> None:
    """Hook called once when the worker process starts.

    Initialises the same structured-logging pipeline the API uses so
    job logs (which the worker emits with their own ``logger``
    field) render in the same JSON / console format as the API's.
    """
    configure_logging(app_env=_settings.app_env)


class WorkerSettings:
    """Class ARQ introspects on ``arq.run_worker``.

    Per the ARQ docs the configuration is exposed as class-level
    attributes rather than methods, which is why we don't use a
    dataclass here.
    """

    functions = [
        optimise_image_task,
        send_email_task,
        generate_ai_review_task,
    ]
    redis_settings = _redis_settings()
    max_jobs = 10                   # concurrent tasks per worker
    job_timeout = 120               # seconds before ARQ kills a job
    keep_result = 3600              # how long ARQ keeps a result in Redis
    on_startup = _on_startup


__all__ = ["WorkerSettings"]

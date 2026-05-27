"""In-process background scheduler.

A thin wrapper around APScheduler's ``BackgroundScheduler`` that is
started + shut down from the FastAPI lifespan. Job modules register
themselves on import via ``register_job``; the scheduler then fires
them at the configured times even when no HTTP traffic is hitting the
process.

Why in-process and not Celery / RQ:

* This app has a small operational footprint (one or two FastAPI
  workers). Adding a separate worker + broker would be over-build.
* APScheduler has zero infra cost — it lives inside the same Python
  process, and the cron triggers persist nothing.
* For the workloads we actually need (nightly report digests, a
  future "nightly pg_dump and push to S3"), a missed firing is
  not catastrophic — the next firing covers the gap.

Disable in tests via ``SCHEDULER_ENABLED=false`` (the default in
``conftest.py``). The production env should leave it enabled.
"""
from __future__ import annotations

import logging
import os
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


_SCHEDULER: BackgroundScheduler | None = None


# Each entry is (job_id, func, trigger). Registered via ``register_job``
# at import time so the start() call below picks them all up.
_REGISTERED_JOBS: list[tuple[str, Callable[[], None], CronTrigger | IntervalTrigger]] = []


def enabled() -> bool:
    return os.getenv("SCHEDULER_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
    }


def register_job(
    job_id: str,
    func: Callable[[], None],
    trigger: CronTrigger | IntervalTrigger,
) -> None:
    """Add a job to the registry. If the scheduler is already running
    when this is called the job is also added live; otherwise the job
    is queued for the next ``start_scheduler()`` call."""
    _REGISTERED_JOBS.append((job_id, func, trigger))
    if _SCHEDULER is not None and _SCHEDULER.running:
        _SCHEDULER.add_job(
            func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1,
        )


def start_scheduler() -> None:
    """Boot the scheduler and attach every registered job. Idempotent —
    a second call while running is a no-op."""
    global _SCHEDULER
    if not enabled():
        logger.info("Scheduler disabled via SCHEDULER_ENABLED env var")
        return
    if _SCHEDULER is not None and _SCHEDULER.running:
        return

    _SCHEDULER = BackgroundScheduler(
        timezone=os.getenv("SCHEDULER_TIMEZONE", "UTC"),
        job_defaults={
            "misfire_grace_time": 300,
            "coalesce": True,
            "max_instances": 1,
        },
    )
    for job_id, func, trigger in _REGISTERED_JOBS:
        _SCHEDULER.add_job(
            func, trigger=trigger, id=job_id, replace_existing=True
        )
    _SCHEDULER.start()
    logger.info(
        "Scheduler started with %d job(s): %s",
        len(_REGISTERED_JOBS),
        ", ".join(j for j, _, _ in _REGISTERED_JOBS) or "<none>",
    )


def shutdown_scheduler() -> None:
    """Stop the scheduler. Called from the FastAPI lifespan."""
    global _SCHEDULER
    if _SCHEDULER is not None and _SCHEDULER.running:
        _SCHEDULER.shutdown(wait=False)
        logger.info("Scheduler shut down")
    _SCHEDULER = None


def list_jobs() -> list[dict]:
    """Snapshot of every scheduled job for the admin observability UI."""
    if _SCHEDULER is None or not _SCHEDULER.running:
        return []
    out = []
    for job in _SCHEDULER.get_jobs():
        out.append(
            {
                "id": job.id,
                "name": job.name or job.id,
                "next_run_at": (
                    job.next_run_time.isoformat() if job.next_run_time else None
                ),
                "trigger": str(job.trigger),
            }
        )
    return out


def trigger_now(job_id: str) -> bool:
    """Force-run a registered job once, on the next scheduler tick.
    Returns True if the job was found, False otherwise. Used by the
    "Run now" admin button + by integration tests."""
    if _SCHEDULER is None or not _SCHEDULER.running:
        return False
    job = _SCHEDULER.get_job(job_id)
    if job is None:
        return False
    job.modify(next_run_time=__now_aware())
    return True


def __now_aware():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


__all__ = [
    "enabled",
    "list_jobs",
    "register_job",
    "shutdown_scheduler",
    "start_scheduler",
    "trigger_now",
]

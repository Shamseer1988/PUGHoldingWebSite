"""Scheduled report digest CRON job (Feature F4).

Fires once a day at 09:00 UTC via APScheduler and dispatches every
active scheduled-report row whose cadence is currently due. The
heavy lifting lives in
:func:`app.services.scheduled_reports.run_due_schedules`; this module
is just the cron-trigger registration.
"""
from __future__ import annotations

import logging
import os

from apscheduler.triggers.cron import CronTrigger

from app.core.scheduler import register_job
from app.services.scheduled_reports import run_due_schedules


logger = logging.getLogger(__name__)


# Single daily firing — the dispatcher itself decides which rows are
# due (daily / weekly / monthly). Hour is configurable so production
# can tune to "before the start-of-day stand-up" without redeploying.
_HOUR = int(os.getenv("SCHEDULED_REPORTS_HOUR_UTC", "9"))
_MINUTE = int(os.getenv("SCHEDULED_REPORTS_MINUTE_UTC", "0"))


def _job() -> None:
    """The actual scheduler callback. Wrapped so failures inside a
    single tick can't kill the scheduler thread."""
    try:
        summary = run_due_schedules()
        logger.info("Scheduled-report tick summary: %s", summary)
    except Exception:  # noqa: BLE001
        logger.exception("Scheduled-report tick crashed")


register_job(
    "scheduled_report_digests_daily",
    _job,
    CronTrigger(hour=_HOUR, minute=_MINUTE),
)

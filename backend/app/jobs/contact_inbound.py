"""Scheduled IMAP poll for the Contact-Us ticket inbox.

Fires on a fixed interval — ``CONTACT_INBOUND_POLL_INTERVAL_MINUTES``
in the env (default 5). Each tick opens a fresh SQLAlchemy session +
IMAP connection, threads any new customer replies onto their tickets
via :func:`app.services.contact_inbound.poll_inbox`, then closes both
cleanly so an idle process doesn't keep a TCP socket pinned.

The trigger registers unconditionally; the poller itself early-exits
when ``CONTACT_INBOUND_ENABLED`` is false, so an operator can
enable/disable inbound mail without touching the scheduler config.
"""
from __future__ import annotations

import logging

from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.scheduler import register_job


logger = logging.getLogger(__name__)


def _job() -> None:
    """One scheduler tick — wrap every call so a transient failure
    can never escape into the scheduler thread."""
    try:
        from app.core.database import SessionLocal
        from app.services.contact_inbound import poll_inbox

        with SessionLocal() as db:
            summary = poll_inbox(db)
        if summary.error:
            logger.warning(
                "Contact-inbox poll skipped: %s", summary.error
            )
        else:
            logger.info(
                "Contact-inbox poll: fetched=%s matched=%s new=%s skipped=%s errors=%s",
                summary.fetched,
                summary.matched,
                summary.new_tickets,
                summary.skipped,
                summary.errors,
            )
    except Exception:  # noqa: BLE001
        logger.exception("Contact-inbox poll crashed")


_settings = get_settings()
_INTERVAL = max(1, int(_settings.contact_inbound_poll_interval_minutes or 5))

register_job(
    "contact_inbound_imap_poll",
    _job,
    IntervalTrigger(minutes=_INTERVAL),
)

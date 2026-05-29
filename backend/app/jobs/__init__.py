"""Scheduled-job registration package.

Importing this package triggers ``register_job(...)`` side-effects in
each sub-module so the FastAPI lifespan picks up every job at boot.
Adding a new scheduled task is two steps:

  1. Create ``app/jobs/<name>.py`` and call
     ``app.core.scheduler.register_job(...)`` at module top level.
  2. Add ``from app.jobs import <name>`` here so it actually loads.
"""
from __future__ import annotations

# Scheduled feature modules register their jobs on import. As features
# F4 (scheduled report digests) and the future nightly backup land,
# import them here so the FastAPI lifespan wires them up.
try:
    from app.jobs import report_digests  # noqa: F401
except ImportError:
    # Feature not shipped yet — that's fine, scheduler boots empty.
    pass

# Contact-Us ticket IMAP poller — interval is read from
# CONTACT_INBOUND_POLL_INTERVAL_MINUTES at import; the job itself
# no-ops when CONTACT_INBOUND_ENABLED=false.
try:
    from app.jobs import contact_inbound  # noqa: F401
except ImportError:
    pass

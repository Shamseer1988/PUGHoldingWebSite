"""ARQ worker entrypoint (Phase B-3).

Boots a worker that drains the queue defined in
``app.worker.settings.WorkerSettings``. Equivalent to
``arq app.worker.settings.WorkerSettings`` but spelled out as a
plain Python entry script so it composes with docker-compose +
systemd without anyone needing to remember the ARQ CLI flags.

Usage:

    python worker_runner.py                    # bare metal
    docker compose up worker                   # via compose
    docker compose exec backend python worker_runner.py    # ad-hoc

The worker shares Redis with the API + the rate limiter + the
public-CMS cache. Make sure they all see the same ``REDIS_URL``.
"""
from __future__ import annotations

from arq import run_worker

from app.worker.settings import WorkerSettings


if __name__ == "__main__":
    run_worker(WorkerSettings)

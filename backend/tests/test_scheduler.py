"""APScheduler infra smoke tests."""
from __future__ import annotations

import time

from apscheduler.triggers.interval import IntervalTrigger

from app.core import scheduler


class TestSchedulerEnabledFlag:
    def test_scheduler_disabled_when_env_false(self, monkeypatch):
        monkeypatch.setenv("SCHEDULER_ENABLED", "false")
        assert scheduler.enabled() is False

    def test_scheduler_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
        assert scheduler.enabled() is True

    def test_explicit_zero_disables(self, monkeypatch):
        monkeypatch.setenv("SCHEDULER_ENABLED", "0")
        assert scheduler.enabled() is False


class TestSchedulerLifecycle:
    def test_start_is_no_op_when_disabled(self, monkeypatch):
        monkeypatch.setenv("SCHEDULER_ENABLED", "false")
        scheduler.start_scheduler()
        # No exception; list_jobs returns empty.
        assert scheduler.list_jobs() == []
        scheduler.shutdown_scheduler()  # safe to call even if not running

    def test_register_and_fire_job_when_enabled(self, monkeypatch):
        monkeypatch.setenv("SCHEDULER_ENABLED", "true")
        # Use a fresh scheduler by shutting down whatever was leftover.
        scheduler.shutdown_scheduler()
        scheduler._REGISTERED_JOBS.clear()

        # Append a tick counter via a registered job.
        counter = {"n": 0}

        def _tick() -> None:
            counter["n"] += 1

        scheduler.register_job(
            "test_tick",
            _tick,
            IntervalTrigger(seconds=1),
        )
        scheduler.start_scheduler()
        # Wait up to 3s for the first tick.
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and counter["n"] == 0:
            time.sleep(0.1)
        scheduler.shutdown_scheduler()
        scheduler._REGISTERED_JOBS.clear()
        assert counter["n"] >= 1, "Job did not fire within 3s"

    def test_list_jobs_after_register(self, monkeypatch):
        monkeypatch.setenv("SCHEDULER_ENABLED", "true")
        scheduler.shutdown_scheduler()
        scheduler._REGISTERED_JOBS.clear()

        scheduler.register_job(
            "list_demo",
            lambda: None,
            IntervalTrigger(hours=1),
        )
        scheduler.start_scheduler()
        try:
            jobs = scheduler.list_jobs()
            ids = [j["id"] for j in jobs]
            assert "list_demo" in ids
        finally:
            scheduler.shutdown_scheduler()
            scheduler._REGISTERED_JOBS.clear()

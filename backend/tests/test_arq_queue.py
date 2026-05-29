"""Phase B-3 — ARQ background queue infrastructure tests.

The actual ARQ worker process runs out-of-band (``python
worker_runner.py``); these tests verify the module surface lined
up around it without booting a worker:

* ``WorkerSettings`` exposes the three task functions and a
  ``RedisSettings`` derived from the configured URL.
* ``get_arq_pool`` returns ``None`` when the lifespan didn't
  install a pool (the test default) and returns the pool object
  when one has been pinned.
* Each task function runs against the fake-redis-backed test
  engine (the worker side of the contract).

We don't spin up a real ARQ worker because:
  * Fakeredis doesn't fully implement the BRPOPLPUSH semantics ARQ
    uses to drain the queue.
  * Booting a worker process from inside pytest is brittle (port
    binds, signal handling, cleanup).

The task functions are imported directly and ``await``ed in tests
instead, which exercises the same logic.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from app.core.arq_pool import get_arq_pool
from app.worker import settings as worker_settings_module
from app.worker.settings import WorkerSettings
from app.worker.tasks import (
    generate_ai_review_task,
    optimise_image_task,
    send_email_task,
)


# ---------------------------------------------------------------------------
# WorkerSettings — class shape ARQ introspects
# ---------------------------------------------------------------------------


class TestWorkerSettings:
    def test_exposes_all_three_registered_tasks(self):
        registered = {f.__name__ for f in WorkerSettings.functions}
        assert registered == {
            "optimise_image_task",
            "send_email_task",
            "generate_ai_review_task",
        }

    def test_redis_settings_is_derived_from_settings_url(self):
        # ``arq.connections.RedisSettings.from_dsn`` parses the host /
        # port / db number out of the URL. The default URL points at
        # ``redis://localhost:6379/0``.
        rs = WorkerSettings.redis_settings
        assert rs.host in ("localhost", "127.0.0.1")
        assert rs.port == 6379
        assert rs.database == 0

    def test_worker_runtime_limits_are_sane(self):
        # max_jobs caps concurrent tasks per worker process — too
        # high and we starve the API of CPU; too low and the queue
        # piles up under burst load.
        assert 1 <= WorkerSettings.max_jobs <= 100
        # job_timeout protects against runaway tasks (e.g. a wedged
        # SMTP send).
        assert 30 <= WorkerSettings.job_timeout <= 600
        # Results live in Redis for an hour by default so an admin
        # can debug a recently-completed job.
        assert WorkerSettings.keep_result >= 60


# ---------------------------------------------------------------------------
# get_arq_pool dependency
# ---------------------------------------------------------------------------


class TestGetArqPool:
    def test_returns_none_when_pool_not_installed(self):
        # The autouse client fixture in conftest builds the app with
        # ``ARQ_ENABLED=false`` so app.state.arq_pool is None.
        # Hand-roll a fake Request whose .app.state has no arq_pool.
        fake_state = MagicMock(spec=[])  # no attributes by default
        fake_app = MagicMock()
        fake_app.state = fake_state
        fake_request = MagicMock(spec=Request)
        fake_request.app = fake_app
        assert get_arq_pool(fake_request) is None

    def test_returns_pool_when_installed(self):
        pool_sentinel = object()
        fake_state = MagicMock()
        fake_state.arq_pool = pool_sentinel
        fake_app = MagicMock()
        fake_app.state = fake_state
        fake_request = MagicMock(spec=Request)
        fake_request.app = fake_app
        assert get_arq_pool(fake_request) is pool_sentinel


# ---------------------------------------------------------------------------
# Task functions — directly awaited (the worker side of the contract)
# ---------------------------------------------------------------------------


class TestSendEmailTask:
    @pytest.mark.asyncio
    async def test_returns_success_payload_when_send_simple_succeeds(
        self, monkeypatch
    ):
        from app.services.email import EmailResult, EmailService

        sent_payloads: list[dict] = []

        def _fake_send_simple(db, **kwargs):
            sent_payloads.append(kwargs)
            return EmailResult(success=True, message="ok")

        monkeypatch.setattr(EmailService, "send_simple", _fake_send_simple)

        result = await send_email_task(
            {},  # ctx — unused in the body
            to_email="visitor@example.com",
            subject="Welcome",
            body_text="hi there",
        )

        assert result["success"] is True
        assert result["message"] == "ok"
        assert sent_payloads == [
            {
                "to_email": "visitor@example.com",
                "subject": "Welcome",
                "body_text": "hi there",
                "body_html": None,
                "reply_to": None,
            }
        ]

    @pytest.mark.asyncio
    async def test_returns_failure_payload_when_send_simple_fails(
        self, monkeypatch
    ):
        from app.services.email import EmailResult, EmailService

        monkeypatch.setattr(
            EmailService,
            "send_simple",
            lambda db, **kw: EmailResult(success=False, message="smtp dead"),
        )

        result = await send_email_task(
            {}, to_email="visitor@example.com", subject="x", body_text="x"
        )
        assert result == {
            "success": False,
            "message": "smtp dead",
            "sent_at": None,
        }


class TestOptimiseImageTask:
    @pytest.mark.asyncio
    async def test_returns_none_variants_when_optimiser_skips(
        self, tmp_path, monkeypatch
    ):
        """Pillow returns None for SVGs / videos / unsupported types.
        The task must propagate that as ``variants: None`` instead of
        crashing."""
        from app.services import image_optimization

        monkeypatch.setattr(
            image_optimization, "optimize_image", lambda *a, **kw: None
        )

        result = await optimise_image_task(
            {},
            file_path=str(tmp_path / "no-such-file.svg"),
            media_asset_id=999,
        )
        assert result == {"media_asset_id": 999, "variants": None}

    @pytest.mark.asyncio
    async def test_persists_variants_when_optimiser_returns_them(
        self, tmp_path, monkeypatch, db_session
    ):
        """End-to-end-ish: stub the Pillow pipeline, drive the task,
        confirm the MediaAsset row got its ``variants`` column
        populated. Uses ``db_session`` so the test SQLite engine is
        the one the task's SessionLocal connects to (we monkey-patch
        SessionLocal to use the test engine for the duration of the
        call)."""
        from app.core import database as db_module
        from app.models.cms import MEDIA_KIND_IMAGE, MediaAsset
        from app.services import image_optimization

        # Seed a media asset to update.
        asset = MediaAsset(
            kind=MEDIA_KIND_IMAGE,
            filename="x.png",
            original_name="x.png",
            url="/api/v1/uploads/cms/x.png",
            mime_type="image/png",
            file_size=10,
            file_hash="hash",
            variants=None,
        )
        db_session.add(asset)
        db_session.commit()

        from app.services.image_optimization import VariantSet

        fake_variants = VariantSet(
            webp={"thumb": "/p/x-thumb.webp"},
            jpg={"thumb": "/p/x-thumb.jpg"},
        )
        monkeypatch.setattr(
            image_optimization,
            "optimize_image",
            lambda *a, **kw: fake_variants,
        )
        # Point the worker's SessionLocal at the test engine.
        from sqlalchemy.orm import sessionmaker

        TestSession = sessionmaker(
            bind=db_session.bind,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
        monkeypatch.setattr(db_module, "SessionLocal", TestSession)

        result = await optimise_image_task(
            {},
            file_path=str(tmp_path / "ignored.png"),
            media_asset_id=asset.id,
        )

        assert result["media_asset_id"] == asset.id
        assert result["variants"] == {
            "webp": {"thumb": "/p/x-thumb.webp"},
            "jpg": {"thumb": "/p/x-thumb.jpg"},
        }
        # Row in the DB carries the variants now.
        db_session.expire_all()
        refreshed = db_session.get(MediaAsset, asset.id)
        assert refreshed.variants == {
            "webp": {"thumb": "/p/x-thumb.webp"},
            "jpg": {"thumb": "/p/x-thumb.jpg"},
        }


class TestGenerateAiReviewTask:
    @pytest.mark.asyncio
    async def test_returns_skipped_when_application_missing(
        self, monkeypatch, db_session
    ):
        # Point the worker's SessionLocal at the test engine so the
        # task's session sees the same (empty-of-applications) DB.
        from app.core import database as db_module
        from sqlalchemy.orm import sessionmaker

        TestSession = sessionmaker(
            bind=db_session.bind,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
        monkeypatch.setattr(db_module, "SessionLocal", TestSession)

        result = await generate_ai_review_task(
            {}, candidate_id=1, application_id=9_999
        )
        assert result["application_id"] == 9_999
        assert result["review_id"] is None
        assert "missing" in (result.get("skipped") or "").lower()

    @pytest.mark.asyncio
    async def test_swallows_run_auto_review_exception(
        self, monkeypatch, db_session
    ):
        """A poisoned review must not crash the worker — the task
        catches, logs, and returns an error payload so ARQ can mark
        the job failed."""
        from app.core import database as db_module
        from app.services import candidate_auto_review
        from app.models.hr_ats import CandidateJobApplication
        from app.models.hr_ats import Candidate
        from sqlalchemy.orm import sessionmaker

        # Minimum viable candidate + application to drive the task
        # past the "missing application" branch.
        cand = Candidate(
            full_name="X",
            email="x@example.com",
            mobile="100",
            source="public_form",
        )
        db_session.add(cand)
        db_session.commit()
        app_row = CandidateJobApplication(
            candidate_id=cand.id,
            job_opening_id=None,
            status="cv_received",
        )
        db_session.add(app_row)
        db_session.commit()

        TestSession = sessionmaker(
            bind=db_session.bind,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
        monkeypatch.setattr(db_module, "SessionLocal", TestSession)

        def _boom(*_a, **_kw):
            raise RuntimeError("simulated crash")

        monkeypatch.setattr(
            candidate_auto_review, "run_auto_review", _boom
        )

        result = await generate_ai_review_task(
            {}, candidate_id=cand.id, application_id=app_row.id
        )
        assert result["review_id"] is None
        assert "simulated crash" in result.get("error", "")

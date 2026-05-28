"""Phase B-1.0 — async DB plumbing smoke tests.

The repo is currently sync end-to-end (56 modules, ~850 call sites
against ``Session``). This phase only adds the *infrastructure* —
async engine, ``AsyncSessionLocal``, ``get_async_db`` dependency,
test fixtures — so net-new code in later phases can opt in. These
tests prove the infrastructure works without migrating anything
existing:

1. The async DSN derivation is correct.
2. The async session can round-trip an ORM row.
3. The FastAPI dependency yields a fresh AsyncSession per request,
   correctly bound to whatever engine the override points at.
4. Concurrency: two requests served on the same event loop don't
   bleed transactions into each other.
"""
from __future__ import annotations

import pytest
from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import (
    AsyncSessionLocal,
    async_engine,
    get_async_db,
)
from app.main import app
from app.models.auth import User


# ---------------------------------------------------------------------------
# DSN derivation
# ---------------------------------------------------------------------------


class TestAsyncDsn:
    def test_psycopg2_dsn_is_rewritten_to_asyncpg(self):
        s = Settings(database_url="postgresql+psycopg2://u:p@h:5432/db")
        assert s.sqlalchemy_async_database_uri == (
            "postgresql+asyncpg://u:p@h:5432/db"
        )

    def test_vanilla_postgresql_dsn_gets_asyncpg_driver(self):
        s = Settings(database_url="postgresql://u:p@h:5432/db")
        assert s.sqlalchemy_async_database_uri == (
            "postgresql+asyncpg://u:p@h:5432/db"
        )

    def test_explicit_asyncpg_dsn_passes_through(self):
        s = Settings(database_url="postgresql+asyncpg://u:p@h:5432/db")
        assert s.sqlalchemy_async_database_uri == (
            "postgresql+asyncpg://u:p@h:5432/db"
        )

    def test_default_components_build_an_asyncpg_dsn(self):
        # No DATABASE_URL → DSN built from the postgres_* fields,
        # which currently use the psycopg2 driver suffix.
        s = Settings()
        assert s.sqlalchemy_async_database_uri.startswith(
            "postgresql+asyncpg://"
        )
        assert "psycopg2" not in s.sqlalchemy_async_database_uri

    def test_sqlite_dsn_passes_through_unchanged(self):
        s = Settings(database_url="sqlite+aiosqlite:///:memory:")
        assert s.sqlalchemy_async_database_uri == (
            "sqlite+aiosqlite:///:memory:"
        )


# ---------------------------------------------------------------------------
# Engine wiring
# ---------------------------------------------------------------------------


def test_module_exports_a_singleton_async_engine():
    # ``database.async_engine`` is built once at import. Callers
    # rely on it staying the same instance so dependencies can
    # construct sessions against a consistent pool.
    from app.core.database import async_engine as engine_a
    from app.core.database import async_engine as engine_b
    assert engine_a is engine_b


def test_async_session_local_is_bound_to_async_engine():
    sess = AsyncSessionLocal()
    assert sess.bind is async_engine
    # We don't await close because the session was never used;
    # ``AsyncSessionLocal`` doesn't open a connection until the
    # first awaited operation.


# ---------------------------------------------------------------------------
# Round-trip — async fixture proves a write + read works
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_session_round_trips_an_orm_row(
    async_db_session: AsyncSession,
):
    """The plumbing is wired correctly if a vanilla ORM round-trip
    works: add, commit, query, get the same row back."""
    user = User(
        email="async-smoke@pug.example.com",
        full_name="Async Smoke",
        password_hash="x" * 60,
        is_active=True,
    )
    async_db_session.add(user)
    await async_db_session.commit()
    await async_db_session.refresh(user)
    assert user.id is not None

    result = await async_db_session.execute(
        select(User).where(User.email == "async-smoke@pug.example.com")
    )
    fetched = result.scalar_one()
    assert fetched.full_name == "Async Smoke"


# ---------------------------------------------------------------------------
# FastAPI dependency — yields an AsyncSession per request, overridable
# ---------------------------------------------------------------------------


# Build a tiny disposable router that uses ``get_async_db``. We mount
# it on the real ``app`` instead of constructing a parallel FastAPI
# so the test exercises the same middleware stack any real async
# endpoint would. The route is namespaced under a unique prefix so
# it can't collide with anything in the live API.

_smoke_router = APIRouter()


@_smoke_router.get("/__phase_b1_smoke__/count")
async def _count_users(db: AsyncSession = Depends(get_async_db)) -> dict[str, int]:
    """Test-only endpoint: count User rows via the injected async session."""
    result = await db.execute(select(User))
    return {"count": len(result.scalars().all())}


@_smoke_router.post("/__phase_b1_smoke__/users")
async def _create_user(
    email: str, db: AsyncSession = Depends(get_async_db)
) -> dict[str, int]:
    user = User(
        email=email,
        full_name="Created via smoke endpoint",
        password_hash="x" * 60,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id}


# Register once at module import; FastAPI is happy with idempotent
# include_router calls on a router that's already registered, but to
# be extra defensive we guard against the second collection.
if not any(
    getattr(r, "path", None) == "/__phase_b1_smoke__/count"
    for r in app.router.routes
):
    app.include_router(_smoke_router)


@pytest.mark.asyncio
async def test_get_async_db_yields_a_session_per_request(async_client):
    """Two requests through the FastAPI app, each one served by a
    fresh ``AsyncSession`` from the test engine. The first creates
    a row, the second sees it — proving the dependency is wired
    against the override-injected engine, not the production one."""
    initial = await async_client.get("/__phase_b1_smoke__/count")
    assert initial.status_code == 200
    assert initial.json() == {"count": 0}

    created = await async_client.post(
        "/__phase_b1_smoke__/users",
        params={"email": "via-endpoint@pug.example.com"},
    )
    assert created.status_code == 200
    assert created.json()["id"] is not None

    after = await async_client.get("/__phase_b1_smoke__/count")
    assert after.status_code == 200
    assert after.json() == {"count": 1}


# ---------------------------------------------------------------------------
# Concurrency — the dependency must not leak transactions across requests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_requests_do_not_share_a_session(async_client):
    """Three POSTs fired concurrently on the same event loop. Each
    must end up with its own row — no double-counting, no
    transaction bleed, no UNIQUE-constraint blow-up from sharing a
    session across coroutines."""
    import asyncio

    async def _post(i: int):
        r = await async_client.post(
            "/__phase_b1_smoke__/users",
            params={"email": f"concurrent-{i}@pug.example.com"},
        )
        assert r.status_code == 200
        return r.json()["id"]

    ids = await asyncio.gather(_post(0), _post(1), _post(2))
    assert len(set(ids)) == 3  # three distinct primary keys

    final = await async_client.get("/__phase_b1_smoke__/count")
    assert final.json() == {"count": 3}

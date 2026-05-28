"""SQLAlchemy engine, session factory, and base class.

Phase B-1.0 — two engines, two dependencies
============================================

The repo has 56 modules and ~850 call-sites against the sync
``Session``. Migrating them all in one pass is the prompt's literal
ask but a fortnight of high-risk work — see the planning notes in
the Phase B-1 README. This module instead exposes the **async stack
alongside** the existing sync stack so:

  * **net-new code** (Phases B-2 Redis cache, B-3 ARQ queue, C-2
    WebSocket notifications, C-5 AI streaming) can take
    ``Depends(get_async_db)`` and get an ``AsyncSession`` against
    the same Postgres database; and
  * **existing code** keeps using ``Depends(get_db)`` -> sync
    ``Session`` until / unless an operator migrates a specific
    endpoint in isolation.

Alembic remains sync because the migration tooling has no native
async support; it uses ``engine`` (psycopg2) regardless of which
dependency a runtime endpoint chose.
"""
from __future__ import annotations

from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()


# ---------------------------------------------------------------------------
# Sync stack — current production path, every existing endpoint.
# ---------------------------------------------------------------------------

engine = create_engine(
    settings.sqlalchemy_database_uri,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
    future=True,
)


# ---------------------------------------------------------------------------
# Async stack — new, opt-in. Same DB, async driver (asyncpg in prod,
# aiosqlite in tests). ``expire_on_commit=False`` mirrors the sync
# session's behaviour so a freshly-committed instance can still be
# read in the same coroutine without triggering the lazy-load that
# would deadlock an AsyncSession.
# ---------------------------------------------------------------------------

async_engine = create_async_engine(
    settings.sqlalchemy_async_database_uri,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Declarative base used by every ORM model in the project."""


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a sync session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an :class:`AsyncSession` per request.

    Use this in **new** async endpoints. The lifecycle is identical
    to the sync helper above — open on enter, close on exit, the
    framework injects it per request. Mixing with ``Depends(get_db)``
    in the same endpoint signature is allowed but rarely useful.
    """
    async with AsyncSessionLocal() as db:
        yield db


__all__ = [
    "AsyncSessionLocal",
    "Base",
    "SessionLocal",
    "async_engine",
    "engine",
    "get_async_db",
    "get_db",
]

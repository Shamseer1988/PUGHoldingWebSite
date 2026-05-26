"""Pytest fixtures.

Phase 2 tests run against an in-memory SQLite database so they don't
require a running PostgreSQL. We override the ``get_db`` dependency and
create the tables fresh per session.
"""
from __future__ import annotations

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import hash_password
from app.core.database import Base, get_db
from app.core.rate_limit import reset_rate_limits
from app.main import app
from app.models.auth import (
    SCOPE_HR,
    SCOPE_SYSTEM,
    SCOPE_WEBSITE,
    Permission,
    Role,
    User,
)


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> Generator[None, None, None]:
    """Public endpoints share a process-global rate-limit bucket; without
    a reset between tests, the cumulative request count from earlier
    tests trips the limiter and unrelated tests get HTTP 429 instead of
    the response they assert on."""
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    TestingSession = sessionmaker(
        bind=db_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_engine) -> Generator[TestClient, None, None]:
    """TestClient with the ``get_db`` dependency wired to the test engine."""
    TestingSession = sessionmaker(
        bind=db_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Seed helpers for the auth tests
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_auth(db_session: Session) -> dict[str, object]:
    """Create a small set of permissions, roles, and users for tests.

    Returns a dict with:
      - users: dict[str, User]   # keyed by email
      - password: str            # password used for every seeded user
    """
    password = "TestPass!123"
    password_hash = hash_password(password)

    # Permissions
    p_website = Permission(
        key="website.dashboard.read",
        scope=SCOPE_WEBSITE,
        description="Read website dashboard",
    )
    p_hr = Permission(
        key="hr.dashboard.read",
        scope=SCOPE_HR,
        description="Read HR dashboard",
    )
    db_session.add_all([p_website, p_hr])
    db_session.flush()

    # Roles
    r_super = Role(
        name="Super Admin",
        scope=SCOPE_SYSTEM,
        description="All scopes",
        permissions=[p_website, p_hr],
    )
    r_web = Role(
        name="Website Admin",
        scope=SCOPE_WEBSITE,
        description="Website only",
        permissions=[p_website],
    )
    r_hr = Role(
        name="HR Manager",
        scope=SCOPE_HR,
        description="HR only",
        permissions=[p_hr],
    )
    db_session.add_all([r_super, r_web, r_hr])
    db_session.flush()

    # Users
    u_super = User(
        email="superadmin@pug.example.com",
        full_name="Super Admin",
        password_hash=password_hash,
        is_active=True,
        is_superuser=True,
        roles=[r_super],
    )
    u_web = User(
        email="webadmin@pug.example.com",
        full_name="Web Admin",
        password_hash=password_hash,
        is_active=True,
        roles=[r_web],
    )
    u_hr = User(
        email="hr@pug.example.com",
        full_name="HR Manager",
        password_hash=password_hash,
        is_active=True,
        roles=[r_hr],
    )
    u_inactive = User(
        email="disabled@pug.example.com",
        full_name="Disabled User",
        password_hash=password_hash,
        is_active=False,
        roles=[r_web],
    )
    db_session.add_all([u_super, u_web, u_hr, u_inactive])
    db_session.commit()

    return {
        "password": password,
        "users": {
            u.email: u for u in [u_super, u_web, u_hr, u_inactive]
        },
    }

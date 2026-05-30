"""Pytest fixtures.

Phase 2 tests run against an in-memory SQLite database so they don't
require a running PostgreSQL. We override the ``get_db`` dependency and
create the tables fresh per session.
"""
from __future__ import annotations

import os

# Disable the background scheduler before the FastAPI app is imported,
# so test sessions don't accidentally fire real digest jobs against the
# ephemeral SQLite engine. Individual scheduler-feature tests opt back
# in with monkeypatch.setenv.
os.environ.setdefault("SCHEDULER_ENABLED", "false")

# Phase A-3: ``Settings.secret_key`` no longer carries an insecure
# placeholder default. Tests still need *something* to sign JWTs with
# (the auth fixtures hit /admin/auth/login and /hr/auth/login).
# ``setdefault`` keeps CI overrides intact while pinning a value here
# so the suite is self-contained when run locally.
os.environ.setdefault(
    "SECRET_KEY",
    "pytest-secret-key-only-used-by-the-test-suite-do-not-deploy",
)

# Phase B-2: switch the rate limiter from the in-memory bucket to
# Redis. Most tests don't exercise rate-limit behaviour and we don't
# want random suite traffic tripping a real Redis bucket. The
# rate-limit-specific tests opt back in via the ``rate_limit_on``
# fixture in test_security.py.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from typing import AsyncGenerator, Generator  # noqa: E402

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.permissions import (
    HR_PERMISSIONS,
    HR_ROLES,
    HR_ROLES_BY_NAME,
    MARKETING_PERMISSIONS,
    MARKETING_ROLES,
)
from app.auth.security import hash_password
from app.core.database import Base, get_async_db, get_db
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


@pytest.fixture(autouse=True)
def _reset_storage_backend_cache() -> Generator[None, None, None]:
    """``get_storage()`` is ``lru_cache``-d so the boto3 client is
    built once per process. In tests that's a footgun: a fixture that
    ``monkeypatch.setenv("UPLOAD_DIR", ...)`` then ``get_settings.cache_clear()``s
    expects the storage layer to pick up the new path on the next
    call. Without clearing this cache the storage stays pinned to
    whatever path the FIRST test that touched it locked in, and
    subsequent tests write to the wrong tmp_path.

    Cheap to reset — it's a single function-level cache — so we just
    blow it away around every test."""
    from app.services.storage import get_storage

    get_storage.cache_clear()
    yield
    get_storage.cache_clear()


class _PerCallFakeRedis:
    """Builds a fresh ``FakeRedis`` per method access, bound to the
    same shared ``FakeServer``.

    The test suite repeatedly calls ``asyncio.run(fake_redis.get(...))``
    — each ``asyncio.run`` creates a new event loop, but
    ``fakeredis``'s connection pool internals (an ``asyncio.Queue``)
    can only live inside the loop that first touched them. Reusing
    a single client across runs raises "Queue is bound to a
    different event loop". Building a brand-new client per
    attribute access keeps every operation cleanly tied to whatever
    loop ends up awaiting it.
    """

    def __init__(self, server) -> None:
        self._server = server

    def __getattr__(self, name):
        from fakeredis import aioredis as fake_aioredis

        server = self._server

        def factory(*args, **kwargs):
            client = fake_aioredis.FakeRedis(
                server=server, decode_responses=True
            )
            return getattr(client, name)(*args, **kwargs)

        return factory


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Phase B-2: pin a ``fakeredis`` instance as the process-wide
    Redis client for every test.

    The real client is constructed by
    ``app.core.redis_client._build_client`` from
    ``settings.redis_url``; monkey-patching that function makes the
    rate limiter, cache decorator and any future Redis-touching code
    use the in-process fake transparently. Tests inspect Redis state
    via the yielded proxy (see ``_PerCallFakeRedis`` for the
    event-loop reasoning).

    A single ``FakeServer`` backs both the in-app client and the
    test-inspector proxy so they see the same data, but each
    individual call gets its own ``FakeRedis`` so the connection
    pool can bind to whichever event loop is running it.
    """
    from fakeredis import FakeServer
    from fakeredis import aioredis as fake_aioredis

    from app.core import redis_client as redis_module

    # Reset any singleton built by a previous test so this test gets
    # a fresh fakeredis instance (no leftover keys from earlier).
    redis_module._reset_client_for_tests()
    server = FakeServer()
    monkeypatch.setattr(
        redis_module,
        "_build_client",
        lambda: fake_aioredis.FakeRedis(server=server, decode_responses=True),
    )
    yield _PerCallFakeRedis(server)
    redis_module._reset_client_for_tests()


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
# Async fixtures (Phase B-1.1) — mirror the sync trio above against the
# aiosqlite driver. Use in net-new tests that exercise the async stack
# (Phase B-2 cache layer, B-3 ARQ tasks, etc.). Existing tests are
# unaffected because pytest only instantiates a fixture when a test
# requests it by name.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def async_db_engine():
    """Async in-memory SQLite engine with a shared connection.

    ``StaticPool`` + ``check_same_thread=False`` keeps the single
    connection alive across the fixture's coroutine and the
    application's request coroutines so they see each other's
    writes — same trick as the sync ``db_engine`` fixture above.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def async_db_session(async_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """An ``AsyncSession`` bound to the test engine.

    Use this for tests that exercise async services / repositories
    directly. For tests that hit an HTTP endpoint, prefer the
    ``async_client`` fixture below — it wires the same engine into
    the FastAPI app via ``dependency_overrides`` so a request +
    direct query observe each other's writes.
    """
    TestingAsyncSession = async_sessionmaker(
        bind=async_db_engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with TestingAsyncSession() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def async_client(async_db_engine):
    """``httpx.AsyncClient`` against the app with ``get_async_db``
    overridden to point at the test engine.

    httpx's ``ASGITransport`` skips the network — requests go
    straight through Starlette's app callable — so this is as fast
    as a sync ``TestClient`` and runs inside the event loop the
    test coroutine is using.
    """
    from httpx import ASGITransport, AsyncClient

    TestingAsyncSession = async_sessionmaker(
        bind=async_db_engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async def _override_get_async_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestingAsyncSession() as session:
            yield session

    app.dependency_overrides[get_async_db] = _override_get_async_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_async_db, None)


# ---------------------------------------------------------------------------
# Seed helpers for the auth tests
# ---------------------------------------------------------------------------


@pytest.fixture
def seed_auth(db_session: Session) -> dict[str, object]:
    """Create the full RBAC catalogue + one user per HR role for tests.

    After Phase 1 of the RBAC overhaul the HR endpoints require
    fine-grained permission keys, so the conftest must seed the full
    permission table and the seven HR roles defined in
    :mod:`app.auth.permissions`. The Test users are:

      - superadmin@pug.example.com     Super Admin (is_superuser=True)
      - webadmin@pug.example.com       Website Admin
      - hr@pug.example.com             HR Manager (legacy fixture key)
      - hradmin@pug.example.com        HR Admin
      - hrexec@pug.example.com         HR Executive
      - deptmgr@pug.example.com        Department Manager (department=Engineering)
      - interviewer@pug.example.com    Interviewer
      - viewer@pug.example.com         Viewer / Auditor
      - disabled@pug.example.com       Inactive user

    Returns:
      - users:    dict[email, User]
      - roles:    dict[name, Role]
      - password: str
    """
    password = "TestPass!123"
    password_hash = hash_password(password)

    # 1. Permissions — both website (legacy two) and the full HR set
    p_website = Permission(
        key="website.dashboard.read",
        scope=SCOPE_WEBSITE,
        description="Read website dashboard",
    )
    db_session.add(p_website)

    hr_perms: dict[str, Permission] = {}
    for key, description in HR_PERMISSIONS:
        perm = Permission(key=key, scope=SCOPE_HR, description=description)
        hr_perms[key] = perm
        db_session.add(perm)

    # Marketing — same shape as HR. Scope=system so the role can be
    # held by a user logging into the website portal.
    marketing_perms: dict[str, Permission] = {}
    for key, description in MARKETING_PERMISSIONS:
        perm = Permission(key=key, scope=SCOPE_SYSTEM, description=description)
        marketing_perms[key] = perm
        db_session.add(perm)
    db_session.flush()

    # 2. Roles — Website + all seven HR roles from the catalogue
    r_web = Role(
        name="Website Admin",
        scope=SCOPE_WEBSITE,
        description="Website only",
        permissions=[p_website],
    )
    db_session.add(r_web)

    roles: dict[str, Role] = {"Website Admin": r_web}
    for spec in HR_ROLES:
        scope = SCOPE_SYSTEM if spec.name == "Super Admin" else SCOPE_HR
        role = Role(
            name=spec.name,
            scope=scope,
            description=spec.description,
            permissions=[hr_perms[k] for k in spec.permissions if k in hr_perms],
        )
        # Super Admin should also have website permission so legacy
        # tests that exercise both portals via this user still work.
        # Same goes for every marketing permission — superuser bypasses
        # checks anyway but the explicit grant keeps audit reads clean.
        if spec.name == "Super Admin":
            role.permissions = role.permissions + [p_website] + list(
                marketing_perms.values()
            )
        roles[spec.name] = role
        db_session.add(role)

    # Marketing-only roles — let the test suite log in as a marketing
    # admin / viewer that has zero HR exposure.
    for spec in MARKETING_ROLES:
        role = Role(
            name=spec.name,
            scope=SCOPE_SYSTEM,
            description=spec.description,
            permissions=[
                marketing_perms[k] for k in spec.permissions if k in marketing_perms
            ],
        )
        roles[spec.name] = role
        db_session.add(role)

    db_session.flush()

    # 3. Users — one per role plus the legacy ``hr@pug.example.com``
    # mapped to HR Manager so older tests keep working.
    def _mk_user(
        email: str,
        full_name: str,
        role_names: list[str],
        *,
        is_active: bool = True,
        is_superuser: bool = False,
        department: str | None = None,
    ) -> User:
        return User(
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            is_active=is_active,
            is_superuser=is_superuser,
            department=department,
            roles=[roles[name] for name in role_names if name in roles],
        )

    u_super = _mk_user(
        "superadmin@pug.example.com",
        "Super Admin",
        ["Super Admin"],
        is_superuser=True,
    )
    u_web = _mk_user("webadmin@pug.example.com", "Web Admin", ["Website Admin"])
    # Legacy fixture key — older tests use 'hr@pug.example.com' as HR Manager
    u_hr = _mk_user("hr@pug.example.com", "HR Manager", ["HR Manager"])
    u_hradmin = _mk_user("hradmin@pug.example.com", "HR Admin", ["HR Admin"])
    u_hrexec = _mk_user("hrexec@pug.example.com", "HR Executive", ["HR Executive"])
    u_dept = _mk_user(
        "deptmgr@pug.example.com",
        "Dept Manager",
        ["Department Manager"],
        department="Engineering",
    )
    u_interviewer = _mk_user(
        "interviewer@pug.example.com",
        "Interviewer",
        ["Interviewer"],
    )
    u_viewer = _mk_user("viewer@pug.example.com", "Viewer", ["Viewer / Auditor"])
    u_marketingmgr = _mk_user(
        "marketingmgr@pug.example.com",
        "Marketing Manager",
        ["Marketing Manager"],
    )
    u_marketingviewer = _mk_user(
        "marketingviewer@pug.example.com",
        "Marketing Viewer",
        ["Marketing Viewer"],
    )
    u_inactive = _mk_user(
        "disabled@pug.example.com",
        "Disabled User",
        ["Website Admin"],
        is_active=False,
    )

    users_list = [
        u_super, u_web, u_hr, u_hradmin, u_hrexec, u_dept,
        u_interviewer, u_viewer, u_marketingmgr, u_marketingviewer,
        u_inactive,
    ]
    db_session.add_all(users_list)
    db_session.commit()

    return {
        "password": password,
        "users": {u.email: u for u in users_list},
        "roles": roles,
    }

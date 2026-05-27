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

from app.auth.permissions import HR_PERMISSIONS, HR_ROLES, HR_ROLES_BY_NAME
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
        if spec.name == "Super Admin":
            role.permissions = role.permissions + [p_website]
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
    u_inactive = _mk_user(
        "disabled@pug.example.com",
        "Disabled User",
        ["Website Admin"],
        is_active=False,
    )

    users_list = [
        u_super, u_web, u_hr, u_hradmin, u_hrexec, u_dept,
        u_interviewer, u_viewer, u_inactive,
    ]
    db_session.add_all(users_list)
    db_session.commit()

    return {
        "password": password,
        "users": {u.email: u for u in users_list},
        "roles": roles,
    }

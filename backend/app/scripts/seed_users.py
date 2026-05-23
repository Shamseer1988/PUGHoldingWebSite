"""Seed the auth tables with baseline roles, permissions, and users.

Run from /backend (with the venv active and .env configured):

    python -m app.scripts.seed_users

The script is idempotent: rerunning it will create missing rows and
update assignments, but it will never overwrite a user's password.

Seed accounts (default password ``ChangeMe!123``):

    superadmin@pug.example.com         super admin (all scopes)
    websiteadmin@pug.example.com       website admin (scope=website)
    hrmanager@pug.example.com          HR manager (scope=hr)
    hrexecutive@pug.example.com        HR executive (scope=hr)
    interviewer@pug.example.com        Interviewer (scope=hr, read-only-ish)

Change passwords immediately in any non-development environment.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.core.database import SessionLocal
from app.models.auth import (
    SCOPE_HR,
    SCOPE_SYSTEM,
    SCOPE_WEBSITE,
    Permission,
    Role,
    User,
)


DEFAULT_PASSWORD = "ChangeMe!123"


# ---------------------------------------------------------------------------
# Permission catalogue (Phase 2 baseline)
# ---------------------------------------------------------------------------

PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    # (key, scope, description)
    # Website admin surface
    ("website.dashboard.read", SCOPE_WEBSITE, "View website admin dashboard"),
    ("website.menu.read", SCOPE_WEBSITE, "View menus"),
    ("website.menu.write", SCOPE_WEBSITE, "Create / edit menus"),
    ("website.content.read", SCOPE_WEBSITE, "View pages, hero slides, companies, news, media"),
    ("website.content.write", SCOPE_WEBSITE, "Create / edit website content"),
    ("website.settings.read", SCOPE_WEBSITE, "View site / SEO / email / AI settings"),
    ("website.settings.write", SCOPE_WEBSITE, "Change site / SEO / email / AI settings"),
    ("website.users.manage", SCOPE_WEBSITE, "Manage website admin users and roles"),
    ("website.audit.read", SCOPE_WEBSITE, "View website audit log"),

    # HR ATS surface
    ("hr.dashboard.read", SCOPE_HR, "View HR dashboard"),
    ("hr.job.read", SCOPE_HR, "View job openings"),
    ("hr.job.write", SCOPE_HR, "Create / edit / close job openings"),
    ("hr.candidate.read", SCOPE_HR, "View candidates"),
    ("hr.candidate.write", SCOPE_HR, "Create / edit candidates and CVs"),
    ("hr.candidate.salary.read", SCOPE_HR, "View candidate salary information"),
    ("hr.candidate.cv.download", SCOPE_HR, "Download candidate CV documents"),
    ("hr.candidate.score.override", SCOPE_HR, "Manually override candidate scores"),
    ("hr.candidate.blacklist", SCOPE_HR, "Approve / set candidate blacklist status"),
    ("hr.interview.read", SCOPE_HR, "View interviews"),
    ("hr.interview.write", SCOPE_HR, "Schedule interviews / submit feedback"),
    ("hr.report.read", SCOPE_HR, "View HR reports"),
    ("hr.report.export", SCOPE_HR, "Export HR reports"),
    ("hr.users.manage", SCOPE_HR, "Manage HR users and roles"),
    ("hr.audit.read", SCOPE_HR, "View HR audit log"),
)


# ---------------------------------------------------------------------------
# Role catalogue (Phase 2 baseline)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoleSpec:
    name: str
    scope: str
    description: str
    permission_keys: tuple[str, ...]


ROLES: tuple[RoleSpec, ...] = (
    RoleSpec(
        name="Super Admin",
        scope=SCOPE_SYSTEM,
        description="Full system access across website and HR surfaces.",
        # System scope grants everything; we still attach explicit perms for
        # clarity in the UI / audit log.
        permission_keys=tuple(key for key, _, _ in PERMISSIONS),
    ),
    RoleSpec(
        name="Website Admin",
        scope=SCOPE_WEBSITE,
        description="Manages all corporate website content and settings.",
        permission_keys=(
            "website.dashboard.read",
            "website.menu.read",
            "website.menu.write",
            "website.content.read",
            "website.content.write",
            "website.settings.read",
            "website.settings.write",
            "website.users.manage",
            "website.audit.read",
        ),
    ),
    RoleSpec(
        name="HR Manager",
        scope=SCOPE_HR,
        description="Full recruitment access including overrides and exports.",
        permission_keys=(
            "hr.dashboard.read",
            "hr.job.read",
            "hr.job.write",
            "hr.candidate.read",
            "hr.candidate.write",
            "hr.candidate.salary.read",
            "hr.candidate.cv.download",
            "hr.candidate.score.override",
            "hr.candidate.blacklist",
            "hr.interview.read",
            "hr.interview.write",
            "hr.report.read",
            "hr.report.export",
            "hr.users.manage",
            "hr.audit.read",
        ),
    ),
    RoleSpec(
        name="HR Executive",
        scope=SCOPE_HR,
        description="Day-to-day recruitment: upload, edit, shortlist, schedule interviews.",
        permission_keys=(
            "hr.dashboard.read",
            "hr.job.read",
            "hr.candidate.read",
            "hr.candidate.write",
            "hr.candidate.cv.download",
            "hr.interview.read",
            "hr.interview.write",
            "hr.report.read",
        ),
    ),
    RoleSpec(
        name="Interviewer",
        scope=SCOPE_HR,
        description="Views only assigned interviews and submits feedback.",
        permission_keys=(
            "hr.dashboard.read",
            "hr.interview.read",
            "hr.interview.write",
        ),
    ),
)


# ---------------------------------------------------------------------------
# User catalogue
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UserSpec:
    email: str
    full_name: str
    role_names: tuple[str, ...]
    is_superuser: bool = False


USERS: tuple[UserSpec, ...] = (
    UserSpec(
        email="superadmin@pug.example.com",
        full_name="Super Admin",
        role_names=("Super Admin",),
        is_superuser=True,
    ),
    UserSpec(
        email="websiteadmin@pug.example.com",
        full_name="Website Admin",
        role_names=("Website Admin",),
    ),
    UserSpec(
        email="hrmanager@pug.example.com",
        full_name="HR Manager",
        role_names=("HR Manager",),
    ),
    UserSpec(
        email="hrexecutive@pug.example.com",
        full_name="HR Executive",
        role_names=("HR Executive",),
    ),
    UserSpec(
        email="interviewer@pug.example.com",
        full_name="Interviewer",
        role_names=("Interviewer",),
    ),
)


# ---------------------------------------------------------------------------
# Upserts
# ---------------------------------------------------------------------------


def _upsert_permissions(db: Session) -> dict[str, Permission]:
    existing = {p.key: p for p in db.execute(select(Permission)).scalars()}
    for key, scope, description in PERMISSIONS:
        perm = existing.get(key)
        if perm is None:
            perm = Permission(key=key, scope=scope, description=description)
            db.add(perm)
            existing[key] = perm
        else:
            perm.scope = scope
            perm.description = description
    db.flush()
    return existing


def _upsert_roles(
    db: Session, permissions: dict[str, Permission]
) -> dict[str, Role]:
    existing = {r.name: r for r in db.execute(select(Role)).scalars()}
    for spec in ROLES:
        role = existing.get(spec.name)
        if role is None:
            role = Role(
                name=spec.name,
                scope=spec.scope,
                description=spec.description,
            )
            db.add(role)
            existing[spec.name] = role
        else:
            role.scope = spec.scope
            role.description = spec.description
        role.permissions = [permissions[key] for key in spec.permission_keys]
    db.flush()
    return existing


def _upsert_users(db: Session, roles: dict[str, Role]) -> list[tuple[User, bool]]:
    """Create or update seed users.

    Returns a list of ``(user, was_created)`` tuples for reporting.
    """
    results: list[tuple[User, bool]] = []
    for spec in USERS:
        stmt = select(User).where(User.email == spec.email)
        user = db.execute(stmt).scalar_one_or_none()
        created = user is None
        if user is None:
            user = User(
                email=spec.email,
                full_name=spec.full_name,
                password_hash=hash_password(DEFAULT_PASSWORD),
                is_active=True,
                is_superuser=spec.is_superuser,
            )
            db.add(user)
        else:
            user.full_name = spec.full_name
            user.is_active = True
            user.is_superuser = spec.is_superuser
        user.roles = [roles[name] for name in spec.role_names]
        results.append((user, created))
    db.flush()
    return results


def seed(db: Session) -> None:
    perms = _upsert_permissions(db)
    roles = _upsert_roles(db, perms)
    users = _upsert_users(db, roles)
    db.commit()

    print()
    print("Seed complete.")
    print(f"  permissions: {len(perms)}")
    print(f"  roles:       {len(roles)}")
    print(f"  users:       {len(users)}")
    print()
    print(f"  Default password for new users: {DEFAULT_PASSWORD}")
    print("  (Existing user passwords were left unchanged.)")
    print()
    print("  Users:")
    for user, created in users:
        flag = "created" if created else "updated"
        scopes = ",".join(sorted(user.scopes)) or "-"
        print(f"    {user.email:<32} [{flag}] scopes={scopes}")


def main(argv: Sequence[str] | None = None) -> int:
    db = SessionLocal()
    try:
        seed(db)
    except Exception as exc:  # noqa: BLE001 - top-level CLI handler
        db.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

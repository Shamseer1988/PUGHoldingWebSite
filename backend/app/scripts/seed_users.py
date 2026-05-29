"""Seed the auth tables with baseline roles, permissions, and users.

Run from /backend (with the venv active and .env configured):

    python -m app.scripts.seed_users

The script is idempotent: rerunning it will create missing rows and
update assignments, but it will never overwrite a user's password.

The HR permission catalogue and role definitions live in
:mod:`app.auth.permissions` — this script is the runtime entry point
that converts that catalogue into rows in the auth tables.

Seed accounts (default password ``ChangeMe!123``):

    superadmin@pug.example.com         super admin (all scopes)
    websiteadmin@pug.example.com       website admin (scope=website)
    hradmin@pug.example.com            HR Admin (Phase 1 — RBAC overhaul)
    hrmanager@pug.example.com          HR Manager
    hrexecutive@pug.example.com        HR Executive / Recruiter
    deptmanager@pug.example.com        Department Manager (department=Engineering)
    interviewer@pug.example.com        Interviewer (assigned interviews only)
    viewer@pug.example.com             Viewer / Auditor (read-only reports)

Change passwords immediately in any non-development environment.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import (
    HR_PERMISSIONS,
    HR_ROLES,
    ROLE_DEPT_MANAGER,
    ROLE_HR_ADMIN,
    ROLE_HR_EXECUTIVE,
    ROLE_HR_MANAGER,
    ROLE_INTERVIEWER,
    ROLE_SUPER_ADMIN,
    ROLE_VIEWER,
)
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
# Permission catalogue
# ---------------------------------------------------------------------------

# (key, scope, description) — combines website + HR permissions. The HR set
# comes from app.auth.permissions; the website set is local since the
# website admin module isn't part of the RBAC overhaul (yet).

WEBSITE_PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    ("website.dashboard.read", SCOPE_WEBSITE, "View website admin dashboard"),
    ("website.menu.read", SCOPE_WEBSITE, "View menus"),
    ("website.menu.write", SCOPE_WEBSITE, "Create / edit menus"),
    ("website.content.read", SCOPE_WEBSITE, "View pages, hero slides, companies, news, media"),
    ("website.content.write", SCOPE_WEBSITE, "Create / edit website content"),
    ("website.settings.read", SCOPE_WEBSITE, "View site / SEO / email / AI settings"),
    ("website.settings.write", SCOPE_WEBSITE, "Change site / SEO / email / AI settings"),
    ("website.users.manage", SCOPE_WEBSITE, "Manage website admin users and roles"),
    ("website.audit.read", SCOPE_WEBSITE, "View website audit log"),
)

PERMISSIONS: tuple[tuple[str, str, str], ...] = (
    *WEBSITE_PERMISSIONS,
    # HR — pulled from the canonical catalogue
    *((key, SCOPE_HR, description) for key, description in HR_PERMISSIONS),
)


# ---------------------------------------------------------------------------
# Role catalogue — website roles defined locally, HR roles from
# app.auth.permissions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoleSpec:
    name: str
    scope: str
    description: str
    permission_keys: tuple[str, ...]


_WEBSITE_ADMIN = RoleSpec(
    name="Website Admin",
    scope=SCOPE_WEBSITE,
    description="Manages all corporate website content and settings.",
    permission_keys=tuple(key for key, _, _ in WEBSITE_PERMISSIONS),
)


def _hr_role_specs() -> tuple[RoleSpec, ...]:
    """Convert HR_ROLES (app.auth.permissions) into the legacy RoleSpec shape."""
    out: list[RoleSpec] = []
    for spec in HR_ROLES:
        scope = SCOPE_SYSTEM if spec.name == ROLE_SUPER_ADMIN else SCOPE_HR
        # Super Admin should also have every website permission so the
        # account can administer both portals.
        perms = list(spec.permissions)
        if spec.name == ROLE_SUPER_ADMIN:
            perms.extend(key for key, _, _ in WEBSITE_PERMISSIONS)
        out.append(
            RoleSpec(
                name=spec.name,
                scope=scope,
                description=spec.description or "",
                permission_keys=tuple(perms),
            )
        )
    return tuple(out)


ROLES: tuple[RoleSpec, ...] = (_WEBSITE_ADMIN, *_hr_role_specs())


# ---------------------------------------------------------------------------
# User catalogue
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UserSpec:
    email: str
    full_name: str
    role_names: tuple[str, ...]
    is_superuser: bool = False
    department: str | None = None


USERS: tuple[UserSpec, ...] = (
    UserSpec(
        email="superadmin@pug.example.com",
        full_name="Super Admin",
        role_names=(ROLE_SUPER_ADMIN,),
        is_superuser=True,
    ),
    UserSpec(
        email="websiteadmin@pug.example.com",
        full_name="Website Admin",
        role_names=("Website Admin",),
    ),
    UserSpec(
        email="hradmin@pug.example.com",
        full_name="HR Admin",
        role_names=(ROLE_HR_ADMIN,),
    ),
    UserSpec(
        email="hrmanager@pug.example.com",
        full_name="HR Manager",
        role_names=(ROLE_HR_MANAGER,),
    ),
    UserSpec(
        email="hrexecutive@pug.example.com",
        full_name="HR Executive",
        role_names=(ROLE_HR_EXECUTIVE,),
    ),
    UserSpec(
        email="deptmanager@pug.example.com",
        full_name="Department Manager",
        role_names=(ROLE_DEPT_MANAGER,),
        department="Engineering",
    ),
    UserSpec(
        email="interviewer@pug.example.com",
        full_name="Interviewer",
        role_names=(ROLE_INTERVIEWER,),
    ),
    UserSpec(
        email="viewer@pug.example.com",
        full_name="Viewer",
        role_names=(ROLE_VIEWER,),
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
        # Permissions: only attach the ones we know about. Unknown keys
        # (e.g. legacy entries) are silently skipped.
        role.permissions = [
            permissions[key] for key in spec.permission_keys if key in permissions
        ]
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
                department=spec.department,
            )
            db.add(user)
        else:
            user.full_name = spec.full_name
            user.is_active = True
            user.is_superuser = spec.is_superuser
            user.department = spec.department
        user.roles = [roles[name] for name in spec.role_names if name in roles]
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

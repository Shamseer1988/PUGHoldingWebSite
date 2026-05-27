"""Authentication and authorization models.

Implements the shared user table + scoped roles + permissions pattern
described in the master prompt. The ``scope`` column on ``roles`` and
``permissions`` enforces separation between the Website Admin and the
HR ATS surfaces:

- A role with ``scope='website'`` cannot grant access to HR endpoints.
- A role with ``scope='hr'`` cannot grant access to website admin
  endpoints.
- ``scope='system'`` is reserved for the super admin and may grant
  permissions in any scope.

The ``users`` table is shared; cross-scope privileges are expressed by
assigning multiple roles to a single user.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


# ---------------------------------------------------------------------------
# Scope constants (lowercase strings stored in the DB)
# ---------------------------------------------------------------------------

SCOPE_SYSTEM = "system"
SCOPE_WEBSITE = "website"
SCOPE_HR = "hr"

ALL_SCOPES = (SCOPE_SYSTEM, SCOPE_WEBSITE, SCOPE_HR)


# ---------------------------------------------------------------------------
# Junction tables (composite PKs, no extra columns yet)
# ---------------------------------------------------------------------------


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )


# ---------------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------------


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    # Optional org-unit tag used by the Department Manager role for
    # row-level scoping (jobs / candidates filtered to user.department).
    # Free-form string matched against JobOpening.department.
    department: Mapped[Optional[str]] = mapped_column(String(120))

    roles: Mapped[List["Role"]] = relationship(
        secondary=UserRole.__table__,
        back_populates="users",
        lazy="selectin",
    )

    # Convenience helpers ---------------------------------------------------

    @property
    def scopes(self) -> set[str]:
        """Set of scopes this user has via their assigned roles."""
        return {role.scope for role in self.roles}

    @property
    def permission_keys(self) -> set[str]:
        """Flat set of permission keys this user holds across all roles."""
        return {perm.key for role in self.roles for perm in role.permissions}

    def has_scope(self, scope: str) -> bool:
        if self.is_superuser:
            return True
        if SCOPE_SYSTEM in self.scopes:
            return True
        return scope in self.scopes

    def has_permission(self, permission_key: str) -> bool:
        if self.is_superuser:
            return True
        return permission_key in self.permission_keys


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))

    users: Mapped[List[User]] = relationship(
        secondary=UserRole.__table__,
        back_populates="roles",
        lazy="selectin",
    )
    permissions: Mapped[List["Permission"]] = relationship(
        secondary=RolePermission.__table__,
        back_populates="roles",
        lazy="selectin",
    )


class Permission(Base, TimestampMixin):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))

    roles: Mapped[List[Role]] = relationship(
        secondary=RolePermission.__table__,
        back_populates="permissions",
        lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Audit log (used by login/logout in Phase 2; later phases reuse it for
# every sensitive action across the website admin and HR ATS portals).
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Actor (nullable for failed logins where we don't have a user_id yet)
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_email: Mapped[Optional[str]] = mapped_column(String(255))

    # Action and surface
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope: Mapped[Optional[str]] = mapped_column(String(32), index=True)

    # Target (set later when we add CRUD audit entries)
    target_type: Mapped[Optional[str]] = mapped_column(String(64))
    target_id: Mapped[Optional[str]] = mapped_column(String(64))

    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(255))

    # Structured extras (e.g. failure reason, old/new values in later phases)
    details: Mapped[Optional[dict]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

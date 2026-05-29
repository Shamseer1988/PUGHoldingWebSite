"""Pydantic schemas for the Phase-5 follow-up Users & Roles admin."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RoleSummary(BaseModel):
    """Compact role row used for the role picker + user listing."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope: str
    description: Optional[str] = None


class UserListItem(BaseModel):
    """Row payload for ``GET /admin/users``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    is_superuser: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    roles: List[RoleSummary] = Field(default_factory=list)
    scopes: List[str] = Field(default_factory=list)


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    is_active: bool = True
    is_superuser: bool = False
    role_ids: List[int] = Field(
        default_factory=list,
        description="IDs of roles to assign on creation.",
    )


class UserUpdate(BaseModel):
    """All fields optional — only the fields present on the request are
    applied. ``password`` is treated specially: empty / missing keeps
    the current hash; supplying a value rotates it. ``role_ids``
    completely replaces the existing assignment when present."""

    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    role_ids: Optional[List[int]] = None


# ---------------------------------------------------------------------------
# Phase 12 — role-permission matrix
# ---------------------------------------------------------------------------


class PermissionInfo(BaseModel):
    """One permission entry shown in the matrix."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    scope: str
    description: Optional[str] = None


class RoleDetail(BaseModel):
    """Full role payload with its permission grants — used by the
    /admin/roles/{id} GET endpoint that powers the matrix UI."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope: str
    description: Optional[str] = None
    permission_ids: List[int] = Field(default_factory=list)
    permission_keys: List[str] = Field(default_factory=list)
    user_count: int = 0


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    scope: str = Field(pattern=r"^(system|website|hr)$")
    description: Optional[str] = Field(default=None, max_length=255)
    permission_ids: List[int] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    """Patch the role itself (rename, redescribe, retag scope). Permission
    grants are updated separately via the dedicated /permissions endpoint
    so audit trails stay clean."""

    name: Optional[str] = Field(default=None, min_length=2, max_length=64)
    scope: Optional[str] = Field(default=None, pattern=r"^(system|website|hr)$")
    description: Optional[str] = Field(default=None, max_length=255)


class RolePermissionUpdate(BaseModel):
    """Replace the full set of permission grants on a role."""

    permission_ids: List[int] = Field(default_factory=list)

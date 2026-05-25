"""Pydantic schemas for the authentication endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Payload for /admin/auth/login and /hr/auth/login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=255)


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    scope: str
    description: Optional[str] = None


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope: str
    description: Optional[str] = None
    permissions: List[PermissionRead] = Field(default_factory=list)


class UserRead(BaseModel):
    """User payload returned to the frontend after login / on /me."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    is_superuser: bool
    last_login_at: Optional[datetime] = None
    roles: List[RoleRead] = Field(default_factory=list)
    scopes: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)


class LoginResponse(BaseModel):
    """Response body for both admin and HR login endpoints."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds.")
    user: UserRead


class TokenPayload(BaseModel):
    """Decoded JWT payload (used internally and for documentation)."""

    sub: str
    type: str
    scopes: List[str] = Field(default_factory=list)
    exp: int
    iat: int

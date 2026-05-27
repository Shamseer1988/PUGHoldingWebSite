"""Admin endpoints for managing users + role assignments (Phase 5 follow-up).

These endpoints back the "Users & roles" page in the admin panel.
Only system-scope users (or superusers) can list / create / modify
users, since accounts span both website and HR surfaces and a
mis-assigned role could silently grant cross-scope access.

Roles themselves are seeded via ``scripts/seed_users.py`` and are
treated as read-only here — admins compose access by assigning the
seeded roles to a user, not by inventing new roles ad-hoc.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context, require_scope
from app.auth.security import hash_password
from app.core.database import get_db
from app.models.auth import ALL_SCOPES, SCOPE_SYSTEM, Permission, Role, User
from app.schemas.users import (
    PermissionInfo,
    RoleCreate,
    RoleDetail,
    RolePermissionUpdate,
    RoleSummary,
    RoleUpdate,
    UserCreate,
    UserListItem,
    UserUpdate,
)
from app.services.audit_log import record_audit


router = APIRouter(
    prefix="/admin",
    tags=["Admin - Users & Roles"],
    dependencies=[Depends(require_scope(SCOPE_SYSTEM))],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_list_item(user: User) -> UserListItem:
    return UserListItem(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        roles=[
            RoleSummary(
                id=r.id,
                name=r.name,
                scope=r.scope,
                description=r.description,
            )
            for r in user.roles
        ],
        scopes=sorted(user.scopes),
    )


def _resolve_roles(db: Session, role_ids: list[int]) -> list[Role]:
    """Fetch + validate role IDs. Raises 422 if any id is unknown."""
    if not role_ids:
        return []
    rows = (
        db.execute(select(Role).where(Role.id.in_(role_ids))).scalars().all()
    )
    found_ids = {r.id for r in rows}
    missing = [str(i) for i in role_ids if i not in found_ids]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown role id(s): {', '.join(missing)}",
        )
    return rows


def _audit(
    db: Session,
    actor: User,
    request: Request,
    *,
    action: str,
    target_user: User,
    details: Optional[dict] = None,
) -> None:
    ctx = get_request_context(request)
    record_audit(
        db,
        action=action,
        actor_id=actor.id,
        actor_email=actor.email,
        scope=SCOPE_SYSTEM,
        target_type="user",
        target_id=str(target_user.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details=details,
        commit=False,
    )


def _audit_role(
    db: Session,
    actor: User,
    request: Request,
    *,
    action: str,
    role_id: int,
    details: Optional[dict] = None,
) -> None:
    """Phase 12 — audit helper for role + permission-grant changes."""
    ctx = get_request_context(request)
    record_audit(
        db,
        action=action,
        actor_id=actor.id,
        actor_email=actor.email,
        scope=SCOPE_SYSTEM,
        target_type="role",
        target_id=str(role_id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details=details,
        commit=False,
    )


# ---------------------------------------------------------------------------
# Roles (read-only — seeded via the seed script)
# ---------------------------------------------------------------------------


@router.get("/roles", response_model=List[RoleSummary])
def list_roles(
    db: Session = Depends(get_db),
    scope: Optional[str] = Query(default=None, pattern=r"^(system|website|hr)$"),
) -> list[RoleSummary]:
    stmt = select(Role).order_by(Role.scope, Role.name)
    if scope:
        stmt = stmt.where(Role.scope == scope)
    rows = db.execute(stmt).scalars().all()
    return [
        RoleSummary(
            id=r.id,
            name=r.name,
            scope=r.scope,
            description=r.description,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Phase 12 — permission matrix endpoints
# ---------------------------------------------------------------------------


@router.get("/permissions", response_model=List[PermissionInfo])
def list_permissions(
    db: Session = Depends(get_db),
    scope: Optional[str] = Query(default=None, pattern=r"^(system|website|hr)$"),
) -> list[PermissionInfo]:
    """Every permission in the catalog. The frontend matrix groups
    these by scope, then by area (the first segment of the key)."""
    stmt = select(Permission).order_by(Permission.scope, Permission.key)
    if scope:
        stmt = stmt.where(Permission.scope == scope)
    return [PermissionInfo.model_validate(p) for p in db.execute(stmt).scalars().all()]


@router.get("/roles/{role_id}", response_model=RoleDetail)
def get_role(role_id: int, db: Session = Depends(get_db)) -> RoleDetail:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    user_count = db.execute(
        select(func.count()).select_from(User).join(User.roles).where(Role.id == role_id)
    ).scalar_one() or 0
    return RoleDetail(
        id=role.id,
        name=role.name,
        scope=role.scope,
        description=role.description,
        permission_ids=sorted([p.id for p in role.permissions]),
        permission_keys=sorted([p.key for p in role.permissions]),
        user_count=int(user_count),
    )


@router.post(
    "/roles", response_model=RoleDetail, status_code=status.HTTP_201_CREATED
)
def create_role(
    payload: RoleCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_scope(SCOPE_SYSTEM)),
) -> RoleDetail:
    """Create a new role + assign the requested permission grants in
    one shot. Conflicts (same name) return 409."""
    existing = db.execute(
        select(Role).where(Role.name == payload.name)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409, detail=f"Role '{payload.name}' already exists."
        )

    role = Role(
        name=payload.name,
        scope=payload.scope,
        description=payload.description,
    )
    db.add(role)
    db.flush()

    if payload.permission_ids:
        perms = list(
            db.execute(
                select(Permission).where(Permission.id.in_(payload.permission_ids))
            ).scalars()
        )
        # Enforce scope: a role-scope X cannot hold permissions from a
        # different scope (except SYSTEM which is allowed to grant
        # anything per the auth.py docstring).
        _assert_grants_match_scope(role.scope, perms)
        role.permissions = perms

    _audit_role(
        db,
        user,
        request,
        action="admin.role.create",
        role_id=role.id,
        details={
            "name": role.name,
            "scope": role.scope,
            "permission_ids": sorted([p.id for p in role.permissions]),
        },
    )
    db.commit()
    db.refresh(role)
    return RoleDetail(
        id=role.id,
        name=role.name,
        scope=role.scope,
        description=role.description,
        permission_ids=sorted([p.id for p in role.permissions]),
        permission_keys=sorted([p.key for p in role.permissions]),
        user_count=0,
    )


@router.patch("/roles/{role_id}", response_model=RoleDetail)
def update_role(
    role_id: int,
    payload: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_scope(SCOPE_SYSTEM)),
) -> RoleDetail:
    """Rename / redescribe / re-scope a role. To change its permission
    grants use PATCH /admin/roles/{id}/permissions instead — keeping
    the two paths separate makes the audit trail clearer."""
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")

    changes: dict[str, object] = {}
    if payload.name is not None and payload.name != role.name:
        existing = db.execute(
            select(Role).where(Role.name == payload.name, Role.id != role.id)
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=409, detail=f"Role '{payload.name}' already exists."
            )
        changes["name"] = {"old": role.name, "new": payload.name}
        role.name = payload.name
    if payload.scope is not None and payload.scope != role.scope:
        # Re-scoping a role: every grant must still be valid for the
        # new scope. Refuse rather than silently drop grants.
        _assert_grants_match_scope(payload.scope, role.permissions)
        changes["scope"] = {"old": role.scope, "new": payload.scope}
        role.scope = payload.scope
    if payload.description is not None and payload.description != role.description:
        changes["description"] = {
            "old": role.description,
            "new": payload.description,
        }
        role.description = payload.description

    if not changes:
        return _serialize_role(db, role)

    _audit_role(
        db,
        user,
        request,
        action="admin.role.update",
        role_id=role.id,
        details={"changes": changes},
    )
    db.commit()
    db.refresh(role)
    return _serialize_role(db, role)


@router.patch(
    "/roles/{role_id}/permissions", response_model=RoleDetail
)
def update_role_permissions(
    role_id: int,
    payload: RolePermissionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_scope(SCOPE_SYSTEM)),
) -> RoleDetail:
    """Replace the full set of permission grants on a role. The
    request supplies the FINAL desired set — the server diffs against
    the current set and writes a single audit row recording the
    added + removed permission keys."""
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")

    new_perms = list(
        db.execute(
            select(Permission).where(Permission.id.in_(payload.permission_ids))
        ).scalars()
    )
    _assert_grants_match_scope(role.scope, new_perms)

    old_keys = {p.key for p in role.permissions}
    new_keys = {p.key for p in new_perms}
    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)

    role.permissions = new_perms

    _audit_role(
        db,
        user,
        request,
        action="admin.role.permissions.update",
        role_id=role.id,
        details={"added": added, "removed": removed},
    )
    db.commit()
    db.refresh(role)
    return _serialize_role(db, role)


@router.delete(
    "/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_scope(SCOPE_SYSTEM)),
) -> Response:
    """Delete a role. Refused (409) if any user still holds it —
    re-assign affected users first via PATCH /admin/users/{id}."""
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    user_count = db.execute(
        select(func.count()).select_from(User).join(User.roles).where(Role.id == role_id)
    ).scalar_one() or 0
    if int(user_count) > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Role still assigned to {user_count} user(s). Re-assign "
                "them before deleting."
            ),
        )
    _audit_role(
        db,
        user,
        request,
        action="admin.role.delete",
        role_id=role.id,
        details={"name": role.name, "scope": role.scope},
    )
    db.delete(role)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _serialize_role(db: Session, role: Role) -> RoleDetail:
    user_count = db.execute(
        select(func.count()).select_from(User).join(User.roles).where(Role.id == role.id)
    ).scalar_one() or 0
    return RoleDetail(
        id=role.id,
        name=role.name,
        scope=role.scope,
        description=role.description,
        permission_ids=sorted([p.id for p in role.permissions]),
        permission_keys=sorted([p.key for p in role.permissions]),
        user_count=int(user_count),
    )


def _assert_grants_match_scope(
    role_scope: str, permissions: list[Permission]
) -> None:
    """Block cross-scope grants — a website-scope role can't hold an
    HR permission, etc. SYSTEM-scope roles can hold anything per the
    auth.py contract."""
    if role_scope == SCOPE_SYSTEM:
        return
    mismatches = [p.key for p in permissions if p.scope != role_scope]
    if mismatches:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Permissions {mismatches} are scope='{permissions[0].scope}' "
                f"but the role is scope='{role_scope}'. Cross-scope grants "
                "are only allowed on SYSTEM-scope roles."
            ),
        )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=List[UserListItem])
def list_users(
    db: Session = Depends(get_db),
    scope: Optional[str] = Query(
        default=None,
        description="Filter to users with at least one role in this scope.",
        pattern=r"^(system|website|hr)$",
    ),
    include_inactive: bool = Query(default=True),
) -> list[UserListItem]:
    stmt = select(User).order_by(User.created_at.desc())
    if not include_inactive:
        stmt = stmt.where(User.is_active.is_(True))
    users = db.execute(stmt).scalars().all()
    if scope:
        users = [u for u in users if scope in u.scopes]
    return [_to_list_item(u) for u in users]


@router.post(
    "/users",
    response_model=UserListItem,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_scope(SCOPE_SYSTEM)),
) -> UserListItem:
    roles = _resolve_roles(db, payload.role_ids or [])
    user = User(
        email=str(payload.email).lower().strip(),
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        is_active=payload.is_active,
        is_superuser=payload.is_superuser,
    )
    user.roles = roles
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that email already exists.",
        ) from exc

    _audit(
        db,
        actor,
        request,
        action="users.create",
        target_user=user,
        details={
            "email": user.email,
            "roles": [r.name for r in roles],
            "is_superuser": user.is_superuser,
        },
    )
    db.commit()
    db.refresh(user)
    return _to_list_item(user)


@router.patch("/users/{user_id}", response_model=UserListItem)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_scope(SCOPE_SYSTEM)),
) -> UserListItem:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    changes = payload.model_dump(exclude_unset=True)
    changed_keys: list[str] = []

    # Guardrails: an admin can't lock themselves out by deactivating
    # their own account or stripping their own superuser flag.
    if user.id == actor.id:
        if "is_active" in changes and changes["is_active"] is False:
            raise HTTPException(
                status_code=400,
                detail="You can't deactivate your own account.",
            )
        if "is_superuser" in changes and changes["is_superuser"] is False:
            raise HTTPException(
                status_code=400,
                detail="You can't strip superuser from your own account.",
            )

    if "full_name" in changes and changes["full_name"]:
        user.full_name = changes["full_name"].strip()
        changed_keys.append("full_name")
    if "is_active" in changes:
        user.is_active = bool(changes["is_active"])
        changed_keys.append("is_active")
    if "is_superuser" in changes:
        user.is_superuser = bool(changes["is_superuser"])
        changed_keys.append("is_superuser")
    if "password" in changes and changes["password"]:
        user.password_hash = hash_password(changes["password"])
        changed_keys.append("password")
    if "role_ids" in changes and changes["role_ids"] is not None:
        roles = _resolve_roles(db, list(changes["role_ids"]))
        user.roles = roles
        changed_keys.append("roles")

    if not changed_keys:
        return _to_list_item(user)

    _audit(
        db,
        actor,
        request,
        action="users.update",
        target_user=user,
        details={"changed_keys": changed_keys},
    )
    db.commit()
    db.refresh(user)
    return _to_list_item(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_scope(SCOPE_SYSTEM)),
) -> Response:
    """Soft-delete a user by clearing their roles + deactivating them.

    We don't hard-delete because audit-log rows reference ``actor_id``
    on a SET NULL FK — losing the row would still keep the audit entry,
    but we want the option to "reactivate" a user without rewriting
    history if they rejoin.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == actor.id:
        raise HTTPException(
            status_code=400, detail="You can't deactivate your own account."
        )
    if not user.is_active and not user.roles:
        # Already in the soft-deleted state — nothing to do.
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    user.roles = []
    user.is_active = False

    _audit(
        db,
        actor,
        request,
        action="users.deactivate",
        target_user=user,
        details={"email": user.email},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router", "ALL_SCOPES"]

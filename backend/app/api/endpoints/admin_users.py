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
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context, require_scope
from app.auth.security import hash_password
from app.core.database import get_db
from app.models.auth import ALL_SCOPES, SCOPE_SYSTEM, Role, User
from app.schemas.users import (
    RoleSummary,
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

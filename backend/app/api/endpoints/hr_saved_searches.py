"""Saved candidate searches (Feature F1 — talent pool).

CRUD over ``SavedCandidateSearch`` rows plus a ``run`` endpoint that
materialises the stored filter back into the same candidate-list
search the candidates page uses.

Permission model:

* Anyone with ``hr:candidates:view_list`` can LIST saved searches —
  but the listing is scoped: they always see their own searches,
  plus any ``team``-scoped searches from other users.
* CREATE / UPDATE / DELETE require ``hr:candidates:view_list`` AND
  that the actor be the owner (or a superuser, who can manage
  abandoned saved searches after staff churn).
* RUN doesn't change anything except the ``last_run_at`` /
  ``last_result_count`` bookkeeping columns, so it's open to anyone
  who can see the saved search.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context, require_permission
from app.auth.permissions import PERM_HR_CANDIDATES_VIEW_LIST
from app.core.database import get_db
from app.models.auth import User
from app.models.hr_ats import (
    SAVED_SEARCH_SCOPE_PRIVATE,
    SAVED_SEARCH_SCOPE_TEAM,
    SavedCandidateSearch,
)
from app.schemas.saved_search import (
    VALID_SCOPES,
    SavedSearchCreate,
    SavedSearchRead,
    SavedSearchRunResult,
    SavedSearchUpdate,
)
from app.services.audit_log import record_audit
from app.services.candidate_search import CandidateFilters, search_candidates
from app.services.user_lookup import users_by_id


router = APIRouter(
    prefix="/hr/saved-searches",
    tags=["HR - Saved Searches"],
    dependencies=[Depends(require_permission(PERM_HR_CANDIDATES_VIEW_LIST))],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _can_edit(row: SavedCandidateSearch, actor: User) -> bool:
    return bool(actor.is_superuser or (row.owner_id == actor.id))


def _serialize(
    row: SavedCandidateSearch,
    *,
    actor: User,
    owner_lookup: dict[int, User],
) -> SavedSearchRead:
    owner = owner_lookup.get(row.owner_id) if row.owner_id else None
    return SavedSearchRead(
        id=row.id,
        owner_id=row.owner_id,
        owner_email=owner.email if owner else None,
        owner_name=owner.full_name if owner else None,
        name=row.name,
        description=row.description,
        filters=row.filters or {},
        scope=row.scope,
        pinned=row.pinned,
        last_run_at=row.last_run_at,
        last_result_count=row.last_result_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
        is_owner=(row.owner_id == actor.id),
    )


def _filters_from_payload(payload: dict) -> CandidateFilters:
    """Build a :class:`CandidateFilters` from the saved JSON payload.

    Unknown keys are dropped silently (filter surface evolves over
    time; we'd rather have a saved row survive than start 500-ing).
    """
    allowed = CandidateFilters.__dataclass_fields__.keys()
    clean = {k: v for k, v in (payload or {}).items() if k in allowed}
    # Pydantic-style coercions on numeric ranges and datetimes
    for key in ("uploaded_from", "uploaded_to"):
        if isinstance(clean.get(key), str):
            try:
                clean[key] = datetime.fromisoformat(clean[key])
            except ValueError:
                clean.pop(key, None)
    return CandidateFilters(**clean)


def _audit(
    db: Session,
    actor: User,
    request: Request,
    *,
    action: str,
    target_id: Optional[int],
    details: Optional[dict] = None,
) -> None:
    ctx = get_request_context(request)
    record_audit(
        db,
        action=action,
        actor_id=actor.id,
        actor_email=actor.email,
        scope="hr",
        target_type="saved_search",
        target_id=str(target_id) if target_id is not None else None,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details=details,
        commit=False,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=List[SavedSearchRead])
def list_saved_searches(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_CANDIDATES_VIEW_LIST)),
    scope: Optional[str] = Query(
        default=None,
        description="Filter to a single scope: 'private' (mine only) or 'team' (shared)",
        pattern=r"^(private|team)$",
    ),
    pinned_only: bool = Query(default=False),
) -> list[SavedSearchRead]:
    """List saved searches visible to the actor.

    Always includes the actor's own private + team searches plus
    everyone else's team-scoped searches. Superusers see everything.
    """
    stmt = select(SavedCandidateSearch).order_by(
        SavedCandidateSearch.pinned.desc(),
        SavedCandidateSearch.name,
    )
    if actor.is_superuser:
        # Wide-open view of every saved search.
        pass
    else:
        stmt = stmt.where(
            (SavedCandidateSearch.owner_id == actor.id)
            | (SavedCandidateSearch.scope == SAVED_SEARCH_SCOPE_TEAM)
        )
    if scope:
        stmt = stmt.where(SavedCandidateSearch.scope == scope)
    if pinned_only:
        stmt = stmt.where(SavedCandidateSearch.pinned.is_(True))

    rows = db.execute(stmt).scalars().all()
    owner_ids = [r.owner_id for r in rows if r.owner_id]
    owner_lookup = users_by_id(db, owner_ids)
    return [_serialize(r, actor=actor, owner_lookup=owner_lookup) for r in rows]


@router.post(
    "",
    response_model=SavedSearchRead,
    status_code=status.HTTP_201_CREATED,
)
def create_saved_search(
    payload: SavedSearchCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_CANDIDATES_VIEW_LIST)),
) -> SavedSearchRead:
    if payload.scope not in VALID_SCOPES:
        raise HTTPException(
            status_code=422,
            detail=f"scope must be one of {sorted(VALID_SCOPES)}",
        )
    # Pre-check the unique (owner_id, name) constraint with a friendly
    # error before the DB raises.
    existing = db.execute(
        select(SavedCandidateSearch).where(
            SavedCandidateSearch.owner_id == actor.id,
            SavedCandidateSearch.name == payload.name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"You already have a saved search called '{payload.name}'."
            ),
        )

    row = SavedCandidateSearch(
        owner_id=actor.id,
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        filters=payload.filters or {},
        scope=payload.scope,
        pinned=payload.pinned,
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        actor,
        request,
        action="hr.saved_search.create",
        target_id=row.id,
        details={"name": row.name, "scope": row.scope},
    )
    db.commit()
    db.refresh(row)
    return _serialize(
        row,
        actor=actor,
        owner_lookup=users_by_id(db, [row.owner_id]),
    )


@router.patch(
    "/{search_id}", response_model=SavedSearchRead
)
def update_saved_search(
    search_id: int,
    payload: SavedSearchUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_CANDIDATES_VIEW_LIST)),
) -> SavedSearchRead:
    row = db.get(SavedCandidateSearch, search_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    if not _can_edit(row, actor):
        raise HTTPException(
            status_code=403,
            detail="You can only edit your own saved searches.",
        )

    updates = payload.model_dump(exclude_unset=True)
    if "scope" in updates and updates["scope"] not in VALID_SCOPES:
        raise HTTPException(
            status_code=422,
            detail=f"scope must be one of {sorted(VALID_SCOPES)}",
        )
    if "name" in updates and updates["name"] is not None:
        new_name = updates["name"].strip()
        if new_name != row.name:
            conflict = db.execute(
                select(SavedCandidateSearch).where(
                    SavedCandidateSearch.owner_id == row.owner_id,
                    SavedCandidateSearch.name == new_name,
                    SavedCandidateSearch.id != row.id,
                )
            ).scalar_one_or_none()
            if conflict is not None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"You already have a saved search called '{new_name}'."
                    ),
                )
        updates["name"] = new_name

    changed: list[str] = []
    for key, value in updates.items():
        if value is None and key not in ("description",):
            continue
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed.append(key)

    if changed:
        _audit(
            db,
            actor,
            request,
            action="hr.saved_search.update",
            target_id=row.id,
            details={"fields": changed},
        )
    db.commit()
    db.refresh(row)
    return _serialize(
        row,
        actor=actor,
        owner_lookup=users_by_id(db, [row.owner_id]),
    )


@router.delete(
    "/{search_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_saved_search(
    search_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_CANDIDATES_VIEW_LIST)),
) -> Response:
    row = db.get(SavedCandidateSearch, search_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    if not _can_edit(row, actor):
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own saved searches.",
        )
    _audit(
        db,
        actor,
        request,
        action="hr.saved_search.delete",
        target_id=row.id,
        details={"name": row.name},
    )
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{search_id}/run", response_model=SavedSearchRunResult
)
def run_saved_search(
    search_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_CANDIDATES_VIEW_LIST)),
) -> SavedSearchRunResult:
    """Re-execute the stored filter and return the matching candidate
    ids. Updates ``last_run_at`` / ``last_result_count`` for analytics.

    The frontend then redirects into the candidate-list page with the
    same filters applied, so the user sees a familiar UI rather than
    a separate "search results" view.
    """
    row = db.get(SavedCandidateSearch, search_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    # Private rows are visible only to the owner / superuser.
    if (
        row.scope == SAVED_SEARCH_SCOPE_PRIVATE
        and not _can_edit(row, actor)
    ):
        raise HTTPException(
            status_code=403,
            detail="This saved search is private to its owner.",
        )

    filters = _filters_from_payload(row.filters)
    results = search_candidates(db, filters)
    ids = [r.candidate.id for r in results]

    row.last_run_at = datetime.now(timezone.utc)
    row.last_result_count = len(ids)
    db.commit()

    return SavedSearchRunResult(
        saved_search_id=row.id,
        name=row.name,
        result_count=len(ids),
        candidate_ids=ids,
    )


__all__ = ["router"]

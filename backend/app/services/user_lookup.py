"""Small helper to batch-fetch ``User`` rows by id.

Previously every HR endpoint module had its own copy of this lookup
(``_email_lookup`` in hr_candidates.py and hr_interviews.py with
incompatible return types). Consolidating here gives the codebase
one source of truth and avoids per-row N+1 queries in serializers
that already have the actor ids in hand.
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User


def users_by_id(db: Session, ids: Iterable[int | None]) -> dict[int, User]:
    """Return ``{id: User}`` for every truthy id in ``ids``.

    ``None`` and falsy ids are filtered out so callers can pass raw
    ``submitted_by_id``-style values straight from related rows.
    A single SQL roundtrip regardless of how many ids are passed.
    """
    clean = {int(uid) for uid in ids if uid}
    if not clean:
        return {}
    rows = db.execute(select(User).where(User.id.in_(clean))).scalars().all()
    return {u.id: u for u in rows}


def emails_by_id(db: Session, ids: Iterable[int | None]) -> dict[int, str]:
    """Return ``{id: email}`` for the requested user ids.

    Cheaper than ``users_by_id`` when the caller only needs the email
    string (e.g. for an audit-log line). Same single-roundtrip pattern.
    """
    clean = {int(uid) for uid in ids if uid}
    if not clean:
        return {}
    rows = db.execute(
        select(User.id, User.email).where(User.id.in_(clean))
    ).all()
    return {uid: email for uid, email in rows}


__all__ = ["users_by_id", "emails_by_id"]

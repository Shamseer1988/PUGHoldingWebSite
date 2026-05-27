"""hr — add waiting_list / recommended_for_offer / not_joined recruitment statuses

Revision ID: 20260527_0003
Revises: 20260527_0002
Create Date: 2026-05-27

Phase 3 of the HR overhaul: separate recruitment / interview / offer
status streams (the data side was already independent; this migration
just rounds out the recruitment-status enum with the three high-value
statuses the master plan calls for).

The application status column is a free-form String(40), so no
database-level enum needs to change. This migration is a no-op at the
schema layer — it exists as a stable revision anchor so the new
Python-side ``APPLICATION_STATUSES`` tuple (in app/models/hr_ats.py)
has a place to point ``down_revision`` from.

The three new statuses are additive:

  - waiting_list           : candidate is kept warm for future slots
  - recommended_for_offer  : final interview cleared, awaiting offer
                             approval — distinct from "selected" which
                             implies the offer has been authorised
  - not_joined             : candidate accepted the offer but did not
                             show up on joining day (distinct from
                             rejected, which is HR-initiated)

Existing rows keep their current status; the new values are only set
by future transitions.
"""
from __future__ import annotations


# revision identifiers, used by Alembic.
revision: str = "20260527_0003"
down_revision: str = "20260527_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: status is a free-form VARCHAR. Anchor only.
    pass


def downgrade() -> None:
    # No-op.
    pass

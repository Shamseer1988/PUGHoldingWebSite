"""Merge the two migration heads into one.

``20260531_0027`` (typed assessment questions + review-trail schema)
and ``20260601_0028`` (offer-letter templates) were both cut from
``20260531_0026`` on parallel branches, so once both merged to ``main``
the history had two heads and ``alembic upgrade head`` — which the
backend container runs on boot — failed with "Multiple head revisions
are present". This revision carries no schema of its own; it simply
ties the two branches back together so there is a single linear head.

Revision ID: 20260601_0029
Revises: 20260531_0027, 20260601_0028
Create Date: 2026-06-01 13:32:55.647157

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260601_0029"
down_revision: Union[str, Sequence[str], None] = ("20260531_0027", "20260601_0028")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: a merge revision only reconciles the migration DAG; both
    # parent branches are purely additive and already applied.
    pass


def downgrade() -> None:
    # No-op: re-splitting back into two heads is never desirable.
    pass

"""rbac — flip Marketing role scope from ``system`` to ``website``

Revision ID: 20260531_0026
Revises: 20260530_0025
Create Date: 2026-05-31

Fixes a privilege-escalation hole introduced when the
``20260528_0019_marketing_roles`` migration seeded ``Marketing
Manager`` and ``Marketing Viewer`` with ``scope='system'``.

``User.has_scope(...)`` auto-returns ``True`` for any user whose
roles include the ``system`` scope, which means a Marketing user
silently passed every other scope check on the platform —
``require_scope(SCOPE_WEBSITE)`` (CMS endpoints),
``require_scope(SCOPE_HR)`` (HR portal), and even
``require_scope(SCOPE_SYSTEM)`` itself (user-management, AI
settings, email settings).

After this migration, Marketing roles carry the ``website`` scope:

  * They can still log in via ``/admin/auth/login`` (which
    requires ``SCOPE_WEBSITE``).
  * They retain their ``marketing:*`` permission keys, so
    ``/admin/marketing/*`` continues to work.
  * They lose the ``system``-scope shortcut, so HR endpoints and
    system-only endpoints (admin_users / admin_ai /
    admin_email_settings / admin_backup) correctly 403.
  * CMS + SEO endpoints additionally gate on the existing
    ``website.content.read`` / ``website.settings.read`` permission
    keys (Marketing roles don't carry them) — that gate lands in
    the same release that ships this migration.

Idempotent — re-running against an already-fixed row is a no-op.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260531_0026"
down_revision: str = "20260530_0025"
branch_labels = None
depends_on = None


MARKETING_ROLES = ("Marketing Manager", "Marketing Viewer")


def upgrade() -> None:
    bind = op.get_bind()
    for name in MARKETING_ROLES:
        bind.execute(
            sa.text(
                "UPDATE roles SET scope = 'website' "
                "WHERE name = :name AND scope <> 'website'"
            ),
            {"name": name},
        )


def downgrade() -> None:
    # Re-instate the dangerous-but-original ``system`` scope so an
    # operator who needs to roll back can do so without surprises.
    # The accompanying endpoint changes do the real gating now —
    # rolling this back without rolling those back too is what
    # restores the leak.
    bind = op.get_bind()
    for name in MARKETING_ROLES:
        bind.execute(
            sa.text(
                "UPDATE roles SET scope = 'system' "
                "WHERE name = :name AND scope <> 'system'"
            ),
            {"name": name},
        )

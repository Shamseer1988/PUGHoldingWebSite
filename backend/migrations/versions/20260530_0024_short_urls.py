"""marketing — short_urls table + read/manage permission keys

Revision ID: 20260530_0024
Revises: 20260529_0023
Create Date: 2026-05-30

Bootstraps the URL Shortener feature (Marketing → Tools):

* Creates the ``short_urls`` table that maps a short ``slug`` to a long
  ``target_url`` plus click-counter bookkeeping.
* Adds two new permission keys:
    - ``marketing:short_urls:read``    (browse + copy)
    - ``marketing:short_urls:manage``  (create / edit / delete)
* Grants both keys to the ``Super Admin`` and ``Marketing Manager``
  roles, and read-only to ``Marketing Viewer``.

Every INSERT is idempotent so re-running the migration in dev doesn't
explode.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260530_0024"
down_revision: str = "20260529_0023"
branch_labels = None
depends_on = None


NEW_PERMS = (
    (
        "marketing:short_urls:read",
        "system",
        "Browse short URLs and click counters (read-only)",
    ),
    (
        "marketing:short_urls:manage",
        "system",
        "Create, edit and delete branded short URLs",
    ),
)


ROLE_GRANTS = {
    "Super Admin": (
        "marketing:short_urls:read",
        "marketing:short_urls:manage",
    ),
    "Marketing Manager": (
        "marketing:short_urls:read",
        "marketing:short_urls:manage",
    ),
    "Marketing Viewer": ("marketing:short_urls:read",),
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "short_urls" not in existing_tables:
        op.create_table(
            "short_urls",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(64), nullable=False, unique=True),
            sa.Column("target_url", sa.Text(), nullable=False),
            sa.Column("title", sa.String(200), nullable=True),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "click_count",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("last_click_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(
                ["created_by_id"], ["users.id"], ondelete="SET NULL"
            ),
        )
        op.create_index(
            "ix_short_urls_slug", "short_urls", ["slug"], unique=True
        )
        op.create_index(
            "ix_short_urls_is_active", "short_urls", ["is_active"]
        )
        op.create_index(
            "ix_short_urls_expires_at", "short_urls", ["expires_at"]
        )
        op.create_index(
            "ix_short_urls_created_at", "short_urls", ["created_at"]
        )

    # --- Seed permissions (idempotent) -------------------------------------
    for key, scope, description in NEW_PERMS:
        existing = bind.execute(
            sa.text("SELECT id FROM permissions WHERE key = :key"),
            {"key": key},
        ).first()
        if existing is None:
            bind.execute(
                sa.text(
                    "INSERT INTO permissions (key, scope, description) "
                    "VALUES (:key, :scope, :description)"
                ),
                {"key": key, "scope": scope, "description": description},
            )

    # --- Grant permissions to roles (idempotent) ---------------------------
    for role_name, perm_keys in ROLE_GRANTS.items():
        role = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"),
            {"name": role_name},
        ).first()
        if role is None:
            # Role hasn't been seeded yet (e.g. a stripped-down install
            # that skipped 20260528_0019). Skip — the role's later
            # bootstrap will need to grant these keys itself.
            continue
        role_id = role[0]
        for key in perm_keys:
            perm = bind.execute(
                sa.text("SELECT id FROM permissions WHERE key = :key"),
                {"key": key},
            ).first()
            if perm is None:
                continue
            perm_id = perm[0]
            already = bind.execute(
                sa.text(
                    "SELECT 1 FROM role_permissions "
                    "WHERE role_id = :rid AND permission_id = :pid"
                ),
                {"rid": role_id, "pid": perm_id},
            ).first()
            if already is None:
                bind.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) "
                        "VALUES (:rid, :pid)"
                    ),
                    {"rid": role_id, "pid": perm_id},
                )


def downgrade() -> None:
    bind = op.get_bind()

    # Drop permission grants + permission rows. Cascade handles the
    # role_permissions cleanup, but we delete explicitly first for
    # symmetry with the migrations that came before.
    for key, _scope, _desc in NEW_PERMS:
        perm = bind.execute(
            sa.text("SELECT id FROM permissions WHERE key = :key"),
            {"key": key},
        ).first()
        if perm is None:
            continue
        perm_id = perm[0]
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id = :pid"
            ),
            {"pid": perm_id},
        )
        bind.execute(
            sa.text("DELETE FROM permissions WHERE id = :pid"),
            {"pid": perm_id},
        )

    op.drop_table("short_urls")

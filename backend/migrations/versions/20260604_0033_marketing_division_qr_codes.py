"""marketing — divisions + per-branch QR codes + scan events

Revision ID: 20260604_0033
Revises: 20260604_0032
Create Date: 2026-08-04

Bootstraps Marketing → QR Codes:

* ``marketing_divisions``      — branch registry (Al Atiyah, Al Khor…)
* ``marketing_qr_codes``       — one permanent code per row; ``slug``
                                 is immutable, ``target_url`` is not
* ``marketing_qr_scan_events`` — anonymised scan log

* Adds two permission keys:
    - ``marketing:qr_codes:read``    (browse + download artwork)
    - ``marketing:qr_codes:manage``  (create divisions/codes, re-point)
* Grants both to ``Super Admin`` and ``Marketing Manager``, read-only
  to ``Marketing Viewer``.

Additive only — ``offer_campaigns.branch`` stays free-text so existing
campaign rows are untouched. Every INSERT is idempotent so re-running
in dev doesn't explode.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260604_0033"
down_revision: str = "20260604_0032"
branch_labels = None
depends_on = None


NEW_PERMS = (
    (
        "marketing:qr_codes:read",
        "system",
        "Browse divisions, branch QR codes and scan analytics (read-only)",
    ),
    (
        "marketing:qr_codes:manage",
        "system",
        "Create divisions and QR codes, and re-point QR target links",
    ),
)


ROLE_GRANTS = {
    "Super Admin": (
        "marketing:qr_codes:read",
        "marketing:qr_codes:manage",
    ),
    "Marketing Manager": (
        "marketing:qr_codes:read",
        "marketing:qr_codes:manage",
    ),
    "Marketing Viewer": ("marketing:qr_codes:read",),
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # --- marketing_divisions ------------------------------------------------
    if "marketing_divisions" not in existing_tables:
        op.create_table(
            "marketing_divisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(120), nullable=False, unique=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("city", sa.String(120), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("logo_url", sa.String(500), nullable=True),
            sa.Column("fallback_url", sa.Text(), nullable=True),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default="true"
            ),
            sa.Column(
                "sort_order", sa.Integer(), nullable=False, server_default="0"
            ),
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
            "ix_marketing_divisions_slug",
            "marketing_divisions",
            ["slug"],
            unique=True,
        )
        op.create_index(
            "ix_marketing_divisions_is_active",
            "marketing_divisions",
            ["is_active"],
        )
        op.create_index(
            "ix_marketing_divisions_created_at",
            "marketing_divisions",
            ["created_at"],
        )

    # --- marketing_qr_codes -------------------------------------------------
    if "marketing_qr_codes" not in existing_tables:
        op.create_table(
            "marketing_qr_codes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("division_id", sa.Integer(), nullable=False),
            sa.Column("slug", sa.String(64), nullable=False, unique=True),
            sa.Column("label", sa.String(200), nullable=False),
            sa.Column("target_url", sa.Text(), nullable=True),
            sa.Column(
                "target_kind",
                sa.String(24),
                nullable=False,
                server_default="other",
            ),
            sa.Column("fallback_url", sa.Text(), nullable=True),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default="true"
            ),
            sa.Column(
                "sort_order", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "scan_count", sa.BigInteger(), nullable=False, server_default="0"
            ),
            sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "target_updated_at", sa.DateTime(timezone=True), nullable=True
            ),
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
                ["division_id"], ["marketing_divisions.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["created_by_id"], ["users.id"], ondelete="SET NULL"
            ),
        )
        op.create_index(
            "ix_marketing_qr_codes_slug",
            "marketing_qr_codes",
            ["slug"],
            unique=True,
        )
        op.create_index(
            "ix_marketing_qr_codes_division_id",
            "marketing_qr_codes",
            ["division_id"],
        )
        op.create_index(
            "ix_marketing_qr_codes_is_active",
            "marketing_qr_codes",
            ["is_active"],
        )
        op.create_index(
            "ix_marketing_qr_codes_target_kind",
            "marketing_qr_codes",
            ["target_kind"],
        )
        op.create_index(
            "ix_marketing_qr_codes_created_at",
            "marketing_qr_codes",
            ["created_at"],
        )

    # --- marketing_qr_scan_events -------------------------------------------
    if "marketing_qr_scan_events" not in existing_tables:
        op.create_table(
            "marketing_qr_scan_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("qr_code_id", sa.Integer(), nullable=False),
            sa.Column("resolved_url", sa.Text(), nullable=True),
            sa.Column("session_hash", sa.String(64), nullable=True),
            sa.Column("device", sa.String(16), nullable=True),
            sa.Column(
                "scanned_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.ForeignKeyConstraint(
                ["qr_code_id"], ["marketing_qr_codes.id"], ondelete="CASCADE"
            ),
        )
        op.create_index(
            "ix_marketing_qr_scan_events_qr_code_id",
            "marketing_qr_scan_events",
            ["qr_code_id"],
        )
        op.create_index(
            "ix_marketing_qr_scan_events_scanned_at",
            "marketing_qr_scan_events",
            ["scanned_at"],
        )

    # --- Seed permissions (idempotent) --------------------------------------
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

    # --- Grant permissions to roles (idempotent) ----------------------------
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

    for key, _scope, _desc in NEW_PERMS:
        perm = bind.execute(
            sa.text("SELECT id FROM permissions WHERE key = :key"),
            {"key": key},
        ).first()
        if perm is None:
            continue
        perm_id = perm[0]
        bind.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"),
            {"pid": perm_id},
        )
        bind.execute(
            sa.text("DELETE FROM permissions WHERE id = :pid"),
            {"pid": perm_id},
        )

    # Child-first so the FKs come apart cleanly on backends that don't
    # honour CASCADE at DROP time.
    op.drop_table("marketing_qr_scan_events")
    op.drop_table("marketing_qr_codes")
    op.drop_table("marketing_divisions")

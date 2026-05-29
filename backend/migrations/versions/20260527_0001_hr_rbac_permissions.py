"""hr rbac — seed fine-grained permissions + new roles

Revision ID: 20260527_0001
Revises: 20260526_0022
Create Date: 2026-05-27

Phase 1 of the HR module RBAC overhaul. This migration:

1. Adds a nullable ``department`` column to ``users`` so Department
   Managers can be scoped by org unit.
2. Inserts every HR permission key listed in
   :mod:`app.auth.permissions` (idempotent — uses ON CONFLICT-style
   upsert via SELECT-then-INSERT).
3. Creates three new HR roles — ``HR Admin``, ``Department Manager``,
   ``Viewer / Auditor`` — and refreshes the permission grants on the
   four pre-existing roles (Super Admin, HR Manager, HR Executive,
   Interviewer) so they match the new fine-grained catalogue.

Existing user → role assignments are untouched. Anyone currently in
"HR Manager" keeps that role and silently picks up the new fine-grained
grants. Anyone currently in "HR Executive" likewise.

The downgrade removes the three new roles and the department column;
the permissions stay (they're cheap and removing them would orphan
role_permissions rows for unrelated installs).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260527_0001"
down_revision: str = "20260526_0022"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Static payload — kept inline (not imported from app code) so the migration
# remains runnable even if app/auth/permissions.py drifts later. If you add
# new permission keys, also add them here.
# ---------------------------------------------------------------------------

SCOPE_HR = "hr"
SCOPE_SYSTEM = "system"

# (key, description)
HR_PERMS: tuple[tuple[str, str], ...] = (
    ("hr:dashboard:view", "View HR dashboard"),
    ("hr:jobs:view", "View all job openings"),
    ("hr:jobs:view_dept", "View jobs in own department"),
    ("hr:jobs:create", "Create new job openings"),
    ("hr:jobs:edit", "Edit job openings"),
    ("hr:jobs:approve", "Approve, reject or request revision on submitted jobs"),
    ("hr:jobs:publish", "Publish / unpublish approved jobs"),
    ("hr:jobs:delete", "Delete job openings"),
    ("hr:candidates:view_list", "View candidates list (search / filter)"),
    ("hr:candidates:view_full", "View candidate full profile + CV + history"),
    ("hr:candidates:view_dept", "View candidates in own department"),
    ("hr:candidates:edit", "Edit candidate profile, parse CV, override score"),
    ("hr:candidates:status_update", "Change candidate workflow status"),
    (
        "hr:candidates:status_override",
        "Override transitions normally blocked by workflow rules (manager only)",
    ),
    ("hr:candidates:delete", "Delete / archive candidate records"),
    ("hr:candidates:score_override", "Override candidate scores"),
    ("hr:candidates:blacklist", "Blacklist candidates"),
    ("hr:interviews:view_all", "View every interview in the system"),
    ("hr:interviews:view_mine", "View only own interviews"),
    ("hr:interviews:schedule", "Schedule new interviews"),
    ("hr:interviews:reschedule", "Edit / reschedule existing interviews"),
    ("hr:interviews:feedback", "Submit interview feedback"),
    ("hr:interviews:delete", "Delete interview rows"),
    ("hr:offers:view", "View offers"),
    ("hr:offers:create", "Prepare / edit offer letters"),
    ("hr:offers:approve", "Approve and issue offers to candidates"),
    ("hr:offers:delete", "Delete / withdraw offers"),
    ("hr:reports:view_all", "View all HR reports"),
    ("hr:reports:view_dept", "View reports scoped to own department"),
    ("hr:reports:view_mine", "View reports scoped to own interviews"),
    ("hr:reports:export", "Export HR reports as Excel/CSV/PDF"),
    ("hr:cv:download", "Download candidate CV files"),
    ("hr:settings:manage", "Manage HR settings, auto-review rules, templates"),
    ("hr:audit:read", "View HR audit log"),
    ("hr:users:manage", "Manage HR users and assign roles"),
)


def _all_keys() -> tuple[str, ...]:
    return tuple(k for k, _ in HR_PERMS)


HR_ROLES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    # (name, scope, description, permission_keys)
    (
        "Super Admin",
        SCOPE_SYSTEM,
        "Full system access — manages roles and permissions.",
        _all_keys() + ("hr:users:manage",),
    ),
    (
        "HR Admin",
        SCOPE_HR,
        "Day-to-day HR. Creates and edits jobs (draft/submit), manages candidates, schedules interviews, prepares offers. Cannot approve, cannot delete.",
        (
            "hr:dashboard:view",
            "hr:jobs:view",
            "hr:jobs:create",
            "hr:jobs:edit",
            "hr:candidates:view_list",
            "hr:candidates:view_full",
            "hr:candidates:edit",
            "hr:candidates:status_update",
            "hr:candidates:score_override",
            "hr:interviews:view_all",
            "hr:interviews:view_mine",
            "hr:interviews:schedule",
            "hr:interviews:reschedule",
            "hr:interviews:feedback",
            "hr:offers:view",
            "hr:offers:create",
            "hr:reports:view_all",
            "hr:reports:export",
            "hr:cv:download",
            "hr:settings:manage",
            "hr:audit:read",
        ),
    ),
    (
        "HR Manager",
        SCOPE_HR,
        "Senior HR with approval authority. Approves jobs and offers, overrides workflow status, can delete or blacklist.",
        (
            "hr:dashboard:view",
            "hr:jobs:view",
            "hr:jobs:create",
            "hr:jobs:edit",
            "hr:jobs:approve",
            "hr:jobs:publish",
            "hr:jobs:delete",
            "hr:candidates:view_list",
            "hr:candidates:view_full",
            "hr:candidates:edit",
            "hr:candidates:status_update",
            "hr:candidates:status_override",
            "hr:candidates:score_override",
            "hr:candidates:blacklist",
            "hr:candidates:delete",
            "hr:interviews:view_all",
            "hr:interviews:view_mine",
            "hr:interviews:schedule",
            "hr:interviews:reschedule",
            "hr:interviews:feedback",
            "hr:interviews:delete",
            "hr:offers:view",
            "hr:offers:create",
            "hr:offers:approve",
            "hr:offers:delete",
            "hr:reports:view_all",
            "hr:reports:export",
            "hr:cv:download",
            "hr:settings:manage",
            "hr:audit:read",
        ),
    ),
    (
        "HR Executive",
        SCOPE_HR,
        "Recruiter. Creates job drafts, manages candidates, schedules interviews. Cannot approve or delete.",
        (
            "hr:dashboard:view",
            "hr:jobs:view",
            "hr:jobs:create",
            "hr:jobs:edit",
            "hr:candidates:view_list",
            "hr:candidates:view_full",
            "hr:candidates:edit",
            "hr:candidates:status_update",
            "hr:interviews:view_all",
            "hr:interviews:view_mine",
            "hr:interviews:schedule",
            "hr:interviews:reschedule",
            "hr:interviews:feedback",
            "hr:offers:view",
            "hr:reports:view_all",
            "hr:reports:export",
            "hr:cv:download",
        ),
    ),
    (
        "Department Manager",
        SCOPE_HR,
        "Reviews shortlisted candidates and interview reports for own department. Can recommend but not change final status.",
        (
            "hr:dashboard:view",
            "hr:jobs:view_dept",
            "hr:candidates:view_dept",
            "hr:interviews:view_all",
            "hr:interviews:feedback",
            "hr:reports:view_dept",
            "hr:reports:export",
            "hr:cv:download",
        ),
    ),
    (
        "Interviewer",
        SCOPE_HR,
        "Sees only assigned interviews. Submits feedback. No candidate list, no offers.",
        (
            "hr:dashboard:view",
            "hr:interviews:view_mine",
            "hr:interviews:feedback",
            "hr:reports:view_mine",
        ),
    ),
    (
        "Viewer / Auditor",
        SCOPE_HR,
        "Read-only across reports + audit log. No write access.",
        (
            "hr:dashboard:view",
            "hr:jobs:view",
            "hr:candidates:view_list",
            "hr:candidates:view_full",
            "hr:interviews:view_all",
            "hr:offers:view",
            "hr:reports:view_all",
            "hr:reports:export",
            "hr:cv:download",
            "hr:audit:read",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add users.department column ----------------------------------------
    # Used by Department Manager scoping in endpoint code.
    inspector = sa.inspect(bind)
    user_cols = {col["name"] for col in inspector.get_columns("users")}
    if "department" not in user_cols:
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("department", sa.String(120), nullable=True))

    # 2. Upsert permissions --------------------------------------------------
    permissions_t = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("key", sa.String),
        sa.column("scope", sa.String),
        sa.column("description", sa.String),
    )

    existing_perm_keys = {
        row[0]
        for row in bind.execute(sa.text("SELECT key FROM permissions")).fetchall()
    }

    new_perm_rows = []
    for key, description in HR_PERMS:
        if key in existing_perm_keys:
            # Refresh description in case wording was tweaked
            bind.execute(
                sa.text(
                    "UPDATE permissions SET scope=:scope, description=:desc "
                    "WHERE key=:key"
                ),
                {"scope": SCOPE_HR, "desc": description, "key": key},
            )
        else:
            new_perm_rows.append(
                {"key": key, "scope": SCOPE_HR, "description": description}
            )

    if new_perm_rows:
        op.bulk_insert(permissions_t, new_perm_rows)

    # 3. Upsert roles -------------------------------------------------------
    roles_t = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("scope", sa.String),
        sa.column("description", sa.String),
    )

    existing_roles = {
        row[0]: row[1]
        for row in bind.execute(sa.text("SELECT name, id FROM roles")).fetchall()
    }

    for name, scope, description, _perms in HR_ROLES:
        if name in existing_roles:
            bind.execute(
                sa.text(
                    "UPDATE roles SET scope=:scope, description=:desc "
                    "WHERE name=:name"
                ),
                {"scope": scope, "desc": description, "name": name},
            )
        else:
            op.bulk_insert(
                roles_t,
                [{"name": name, "scope": scope, "description": description}],
            )

    # Refresh the role-id map now that new rows are inserted
    role_id_map = {
        row[0]: row[1]
        for row in bind.execute(sa.text("SELECT name, id FROM roles")).fetchall()
    }
    perm_id_map = {
        row[0]: row[1]
        for row in bind.execute(sa.text("SELECT key, id FROM permissions")).fetchall()
    }

    # 4. Reset role → permission links for the 7 standard roles -------------
    # Wipe + re-insert so any older grants from the previous coarse model
    # don't bleed into the new fine-grained matrix.
    for name, _scope, _description, perm_keys in HR_ROLES:
        role_id = role_id_map.get(name)
        if role_id is None:
            continue  # shouldn't happen — we just inserted them
        bind.execute(
            sa.text("DELETE FROM role_permissions WHERE role_id = :rid"),
            {"rid": role_id},
        )
        # Dedupe the permission ids per role: HR_ROLES["Super Admin"]
        # uses ``_all_keys() + ("hr:users:manage",)`` and the trailing
        # explicit entry is also already in ``_all_keys()``. Without
        # this guard the bulk_insert below trips the
        # role_permissions_pkey unique constraint.
        seen_pids: set[int] = set()
        rows: list[dict] = []
        for key in perm_keys:
            pid = perm_id_map.get(key)
            if pid is None or pid in seen_pids:
                continue
            seen_pids.add(pid)
            rows.append({"role_id": role_id, "permission_id": pid})
        if rows:
            role_perm_t = sa.table(
                "role_permissions",
                sa.column("role_id", sa.Integer),
                sa.column("permission_id", sa.Integer),
            )
            op.bulk_insert(role_perm_t, rows)


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    bind = op.get_bind()

    # Remove the three NEW roles. Manager/Executive/Interviewer existed
    # before this migration so we leave them — but we restore their
    # original (coarse) permission grants by wiping the table; the old
    # seed_users script will re-grant on next run if needed.
    new_role_names = ("HR Admin", "Department Manager", "Viewer / Auditor")
    for name in new_role_names:
        result = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"),
            {"name": name},
        ).fetchone()
        if result is None:
            continue
        rid = result[0]
        bind.execute(
            sa.text("DELETE FROM role_permissions WHERE role_id = :rid"),
            {"rid": rid},
        )
        bind.execute(
            sa.text("DELETE FROM user_roles WHERE role_id = :rid"),
            {"rid": rid},
        )
        bind.execute(
            sa.text("DELETE FROM roles WHERE id = :rid"),
            {"rid": rid},
        )

    # Drop the department column from users.
    inspector = sa.inspect(bind)
    user_cols = {col["name"] for col in inspector.get_columns("users")}
    if "department" in user_cols:
        with op.batch_alter_table("users") as batch:
            batch.drop_column("department")

    # Leave HR permission rows in place — they're cheap and other roles
    # may reference them in the future.

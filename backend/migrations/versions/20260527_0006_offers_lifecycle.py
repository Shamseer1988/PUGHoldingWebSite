"""hr — Phase 6: full offer lifecycle (extra columns + status_history)

Revision ID: 20260527_0006
Revises: 20260527_0005
Create Date: 2026-05-27

Phase 6 fleshes out the offer module from the placeholder
hr_offer_tracking row into a real offer-management lifecycle.

Schema changes
--------------
- hr_offer_tracking gains the columns the master phase plan requests:
    position (String 200)        position title at time of offer
    allowances (Text)            free-form summary of allowances
    probation_period (String 80) "3 months", etc.
    reporting_manager (String 255)
    work_location (String 255)
    offer_letter_number (String 80)
    attachment_url (String 500)  upload path for the generated PDF
    remarks (Text)

  Plus an audit cluster mirroring the job-approval pattern:
    approval_status (String 32, NOT NULL default 'draft')
    approved_by_id (FK users SET NULL), approved_at
    rejected_by_id (FK users SET NULL), rejected_at, rejection_reason
    issued_by_id (FK users SET NULL),   issued_at
    withdrawn_by_id (FK users SET NULL), withdrawn_at, withdrawn_reason
    accepted_at, declined_at   (already had responded_at — keep both
                                so reports can distinguish "yes vs no
                                vs no-reply yet")
    joining_status (String 32 nullable) 'pending' | 'joined' | 'not_joined'
    joined_at (DateTime nullable)
    not_joined_reason (Text)

- New table hr_offer_status_history records every transition with
  old vs new status + actor + remarks, mirroring hr_job_approval_history
  so the UI can render a timeline.

Status enum
-----------
The existing ``status`` column stays a free-form VARCHAR(20). Python
side gains three additional constants (OFFER_PENDING_APPROVAL,
OFFER_APPROVED, OFFER_NOT_JOINED) and the legacy OFFER_SENT continues
to mean "issued to candidate" — kept for backwards compatibility with
already-stored rows.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260527_0006"
down_revision: str = "20260527_0005"
branch_labels = None
depends_on = None


NEW_COLS = (
    # (name, type, nullable, server_default)
    ("position", sa.String(200), True, None),
    ("allowances", sa.Text(), True, None),
    ("probation_period", sa.String(80), True, None),
    ("reporting_manager", sa.String(255), True, None),
    ("work_location", sa.String(255), True, None),
    ("offer_letter_number", sa.String(80), True, None),
    ("attachment_url", sa.String(500), True, None),
    ("remarks", sa.Text(), True, None),
    # Approval audit cluster
    ("approval_status", sa.String(32), False, "draft"),
    ("approved_by_id", sa.Integer(), True, None),
    ("approved_at", sa.DateTime(timezone=True), True, None),
    ("rejected_by_id", sa.Integer(), True, None),
    ("rejected_at", sa.DateTime(timezone=True), True, None),
    ("rejection_reason", sa.Text(), True, None),
    ("issued_by_id", sa.Integer(), True, None),
    ("issued_at", sa.DateTime(timezone=True), True, None),
    ("withdrawn_by_id", sa.Integer(), True, None),
    ("withdrawn_at", sa.DateTime(timezone=True), True, None),
    ("withdrawn_reason", sa.Text(), True, None),
    ("accepted_at", sa.DateTime(timezone=True), True, None),
    ("declined_at", sa.DateTime(timezone=True), True, None),
    # Joining tracker
    ("joining_status", sa.String(32), True, None),
    ("joined_at", sa.DateTime(timezone=True), True, None),
    ("not_joined_reason", sa.Text(), True, None),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("hr_offer_tracking")}

    with op.batch_alter_table("hr_offer_tracking") as batch:
        for name, type_, nullable, server_default in NEW_COLS:
            if name in existing:
                continue
            kwargs: dict = {"nullable": nullable}
            if server_default is not None:
                kwargs["server_default"] = server_default
            batch.add_column(sa.Column(name, type_, **kwargs))

    # FK constraints — Postgres only (SQLite tests skip cleanly).
    if bind.dialect.name != "sqlite":
        with op.batch_alter_table("hr_offer_tracking") as batch:
            for col_name, fk_name in (
                ("approved_by_id", "fk_hr_offer_tracking_approved_by"),
                ("rejected_by_id", "fk_hr_offer_tracking_rejected_by"),
                ("issued_by_id", "fk_hr_offer_tracking_issued_by"),
                ("withdrawn_by_id", "fk_hr_offer_tracking_withdrawn_by"),
            ):
                try:
                    batch.create_foreign_key(
                        fk_name, "users", [col_name], ["id"], ondelete="SET NULL"
                    )
                except Exception:
                    pass

    # New hr_offer_status_history table (idempotent — won't fail if it exists)
    if not inspector.has_table("hr_offer_status_history"):
        op.create_table(
            "hr_offer_status_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "offer_id",
                sa.Integer(),
                sa.ForeignKey("hr_offer_tracking.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("action", sa.String(40), nullable=False, index=True),
            sa.Column("old_status", sa.String(32), nullable=True),
            sa.Column("new_status", sa.String(32), nullable=True),
            sa.Column(
                "actor_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("actor_email", sa.String(255), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
                index=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("hr_offer_status_history"):
        op.drop_table("hr_offer_status_history")

    if bind.dialect.name != "sqlite":
        with op.batch_alter_table("hr_offer_tracking") as batch:
            for fk_name in (
                "fk_hr_offer_tracking_approved_by",
                "fk_hr_offer_tracking_rejected_by",
                "fk_hr_offer_tracking_issued_by",
                "fk_hr_offer_tracking_withdrawn_by",
            ):
                try:
                    batch.drop_constraint(fk_name, type_="foreignkey")
                except Exception:
                    pass

    with op.batch_alter_table("hr_offer_tracking") as batch:
        for name, _, _, _ in NEW_COLS:
            try:
                batch.drop_column(name)
            except Exception:
                pass

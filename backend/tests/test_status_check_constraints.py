"""Verify the model-level CHECK constraints reject invalid enum values.

After Phase A / Issue #5, every status-bearing column carries a named
CHECK constraint that pins it to the valid enum tuple. These tests
prove the database (SQLite in tests, PostgreSQL in prod) actually
rejects typos / injection / state-machine bypasses, not just the
service layer.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _job_id(db: Session) -> int:
    """Insert a minimally-valid job and return its id, so the test can
    then try to PATCH the status to an invalid value."""
    db.execute(
        text(
            "INSERT INTO hr_job_openings (title, slug, department, "
            "company, location, status, approval_status, publish_status) "
            "VALUES (:t, :s, :d, :co, :lo, :st, :ap, :pu)"
        ),
        {
            "t": "Test Engineer",
            "s": "test-engineer-check",
            "d": "Eng",
            "co": "Test Co",
            "lo": "Test City",
            "st": "open",
            "ap": "draft",
            "pu": "draft",
        },
    )
    return int(
        db.execute(
            text("SELECT id FROM hr_job_openings WHERE slug = 'test-engineer-check'")
        ).scalar_one()
    )


def _force_set(db: Session, table: str, column: str, row_id: int, value: str) -> None:
    """Bypass SQLAlchemy validation and write a raw value directly.
    The CHECK constraint at the DB level is what we're testing."""
    db.execute(
        text(f"UPDATE {table} SET {column} = :v WHERE id = :i"),
        {"v": value, "i": row_id},
    )


class TestJobStatusCheckConstraints:
    def test_job_rejects_invalid_status(self, db_session: Session):
        job_id = _job_id(db_session)
        with pytest.raises(IntegrityError):
            _force_set(db_session, "hr_job_openings", "status", job_id, "bogus")
            db_session.flush()

    def test_job_rejects_invalid_approval_status(self, db_session: Session):
        job_id = _job_id(db_session)
        with pytest.raises(IntegrityError):
            _force_set(
                db_session,
                "hr_job_openings",
                "approval_status",
                job_id,
                "kinda_approved",
            )
            db_session.flush()

    def test_job_rejects_invalid_publish_status(self, db_session: Session):
        job_id = _job_id(db_session)
        with pytest.raises(IntegrityError):
            _force_set(
                db_session,
                "hr_job_openings",
                "publish_status",
                job_id,
                "almost_published",
            )
            db_session.flush()

    def test_job_accepts_every_documented_status(self, db_session: Session):
        from app.models.hr_ats import JOB_STATUSES

        job_id = _job_id(db_session)
        for status in JOB_STATUSES:
            _force_set(db_session, "hr_job_openings", "status", job_id, status)
            db_session.flush()


class TestApplicationStatusCheckConstraint:
    def test_application_rejects_invalid_status(self, db_session: Session):
        # Need a candidate + job first to seat the FK.
        db_session.execute(
            text("INSERT INTO hr_candidates (full_name) VALUES ('Test Person')")
        )
        cand_id = int(
            db_session.execute(
                text("SELECT id FROM hr_candidates WHERE full_name='Test Person'")
            ).scalar_one()
        )
        db_session.execute(
            text(
                "INSERT INTO hr_candidate_job_applications "
                "(candidate_id, status, applied_at) VALUES "
                "(:c, 'cv_received', CURRENT_TIMESTAMP)"
            ),
            {"c": cand_id},
        )
        app_id = int(
            db_session.execute(
                text(
                    "SELECT id FROM hr_candidate_job_applications "
                    "WHERE candidate_id = :c"
                ),
                {"c": cand_id},
            ).scalar_one()
        )
        with pytest.raises(IntegrityError):
            _force_set(
                db_session,
                "hr_candidate_job_applications",
                "status",
                app_id,
                "totally_made_up",
            )
            db_session.flush()

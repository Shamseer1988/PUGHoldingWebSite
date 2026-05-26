"""Purge every artifact created by the HR Admin Bulk-ZIP upload feature.

Usage from the backend project root (venv active, migrations applied)::

    # Dry-run (default) — prints counts + file list, makes no changes
    python -m app.scripts.purge_bulk_uploads

    # Actually delete after dry-run looks correct
    python -m app.scripts.purge_bulk_uploads --confirm

    # Also delete the audit-log entries that recorded the bulk uploads
    python -m app.scripts.purge_bulk_uploads --confirm --purge-audit

What gets removed
-----------------
* Every row in ``hr_candidates`` where ``source = 'bulk_upload'``.
* All 13 cascaded child rows (documents, applications, scores,
  breakdowns, status_history, interviews, feedback, ai_reviews,
  notes, tags, extracted_data, offer_tracking) via ON DELETE CASCADE.
* The CV files referenced by the deleted ``hr_candidate_documents``
  rows from ``{upload_dir}/cvs/``.

What is NOT removed by default
------------------------------
* ``audit_logs`` rows with ``action = 'hr.candidate.bulk_upload'`` —
  kept so the history of who uploaded what is traceable. Pass
  ``--purge-audit`` to also remove them.

Safety
------
* The DB delete and the on-disk delete happen *after* the dry-run
  preview, and only when ``--confirm`` is given. The script never
  deletes anything in dry-run mode.
* CV files are removed *after* the DB commit succeeds, so a database
  failure won't leave orphan files. A file-delete failure is reported
  but does not roll back the DB (those files become harmless orphans
  that can be cleaned up manually).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.auth import AuditLog
from app.models.hr_ats import (
    Candidate,
    CandidateAIReview,
    CandidateDocument,
    CandidateExtractedData,
    CandidateJobApplication,
    CandidateNote,
    CandidateScore,
    CandidateScoreBreakdown,
    CandidateStatusHistory,
    CandidateTag,
    Interview,
    InterviewFeedback,
    OfferTracking,
    SOURCE_BULK_UPLOAD,
)


BULK_UPLOAD_AUDIT_ACTION = "hr.candidate.bulk_upload"


def _cvs_dir() -> Path:
    """Resolve the on-disk CV directory the same way cv_storage.py does."""
    settings = get_settings()
    return Path(settings.upload_dir) / "cvs"


def _bulk_candidate_ids(db: Session) -> List[int]:
    stmt = select(Candidate.id).where(Candidate.source == SOURCE_BULK_UPLOAD)
    return [row[0] for row in db.execute(stmt).all()]


def _count_for(db: Session, model, candidate_ids: List[int]) -> int:
    """Count rows whose candidate FK is in the target set."""
    if not candidate_ids:
        return 0
    stmt = (
        select(func.count())
        .select_from(model)
        .where(model.candidate_id.in_(candidate_ids))
    )
    return int(db.execute(stmt).scalar() or 0)


def _application_descendant_count(
    db: Session, model, candidate_ids: List[int]
) -> int:
    """Count rows whose application FK belongs to a target candidate."""
    if not candidate_ids:
        return 0
    app_ids_stmt = select(CandidateJobApplication.id).where(
        CandidateJobApplication.candidate_id.in_(candidate_ids)
    )
    stmt = (
        select(func.count())
        .select_from(model)
        .where(model.application_id.in_(app_ids_stmt))
    )
    return int(db.execute(stmt).scalar() or 0)


def _interview_feedback_count(db: Session, candidate_ids: List[int]) -> int:
    if not candidate_ids:
        return 0
    app_ids_stmt = select(CandidateJobApplication.id).where(
        CandidateJobApplication.candidate_id.in_(candidate_ids)
    )
    interview_ids_stmt = select(Interview.id).where(
        Interview.application_id.in_(app_ids_stmt)
    )
    stmt = (
        select(func.count())
        .select_from(InterviewFeedback)
        .where(InterviewFeedback.interview_id.in_(interview_ids_stmt))
    )
    return int(db.execute(stmt).scalar() or 0)


def _score_breakdown_count(db: Session, candidate_ids: List[int]) -> int:
    if not candidate_ids:
        return 0
    app_ids_stmt = select(CandidateJobApplication.id).where(
        CandidateJobApplication.candidate_id.in_(candidate_ids)
    )
    score_ids_stmt = select(CandidateScore.id).where(
        CandidateScore.application_id.in_(app_ids_stmt)
    )
    stmt = (
        select(func.count())
        .select_from(CandidateScoreBreakdown)
        .where(CandidateScoreBreakdown.score_id.in_(score_ids_stmt))
    )
    return int(db.execute(stmt).scalar() or 0)


def _cv_file_paths(db: Session, candidate_ids: List[int]) -> List[Tuple[int, Path]]:
    """Return (document_id, absolute_path) for every CV referenced by these candidates."""
    if not candidate_ids:
        return []
    base = _cvs_dir().resolve()
    stmt = select(CandidateDocument.id, CandidateDocument.filename).where(
        CandidateDocument.candidate_id.in_(candidate_ids)
    )
    rows = db.execute(stmt).all()
    return [(doc_id, base / fn) for doc_id, fn in rows]


def _print_preview(
    db: Session, candidate_ids: List[int], audit_count: int, files: List[Tuple[int, Path]]
) -> int:
    """Render the dry-run report. Returns total bytes on disk being targeted."""
    print("=" * 60)
    print(" Bulk-upload purge preview")
    print("=" * 60)
    print(f" hr_candidates (source = '{SOURCE_BULK_UPLOAD}'): {len(candidate_ids)}")

    if not candidate_ids:
        print(" Nothing to delete.")
        return 0

    rows_by_table = [
        ("hr_candidate_documents", _count_for(db, CandidateDocument, candidate_ids)),
        (
            "hr_candidate_extracted_data",
            _count_for(db, CandidateExtractedData, candidate_ids),
        ),
        (
            "hr_candidate_job_applications",
            _count_for(db, CandidateJobApplication, candidate_ids),
        ),
        (
            "hr_candidate_scores",
            _application_descendant_count(db, CandidateScore, candidate_ids),
        ),
        (
            "hr_candidate_score_breakdowns",
            _score_breakdown_count(db, candidate_ids),
        ),
        (
            "hr_candidate_status_history",
            _application_descendant_count(db, CandidateStatusHistory, candidate_ids),
        ),
        (
            "hr_interviews",
            _application_descendant_count(db, Interview, candidate_ids),
        ),
        ("hr_interview_feedback", _interview_feedback_count(db, candidate_ids)),
        (
            "hr_candidate_ai_reviews",
            _application_descendant_count(db, CandidateAIReview, candidate_ids),
        ),
        (
            "hr_offer_tracking",
            _application_descendant_count(db, OfferTracking, candidate_ids),
        ),
        ("hr_candidate_notes", _count_for(db, CandidateNote, candidate_ids)),
        ("hr_candidate_tags", _count_for(db, CandidateTag, candidate_ids)),
    ]
    print(" Cascaded child rows (will be removed by ON DELETE CASCADE):")
    for table, count in rows_by_table:
        print(f"   {table:<32} {count:>6}")

    print(f" audit_logs (bulk_upload entries): {audit_count}")

    total_bytes = 0
    present = 0
    missing = 0
    for _, path in files:
        try:
            if path.exists():
                present += 1
                total_bytes += path.stat().st_size
            else:
                missing += 1
        except OSError:
            missing += 1

    print()
    print(" CV files on disk under {}:".format(_cvs_dir()))
    print(f"   referenced documents:    {len(files)}")
    print(f"   present on disk:         {present}")
    print(f"   already missing on disk: {missing}")
    print(f"   total bytes to free:     {total_bytes:,}")
    print("=" * 60)
    return total_bytes


def purge(db: Session, candidate_ids: List[int]) -> None:
    """Delete the targeted candidates.

    Uses ORM ``session.delete()`` so the ``cascade='all, delete-orphan'``
    relationships on :class:`Candidate` reliably remove every child row
    on any DB backend (PostgreSQL enforces the FK CASCADE column flag
    as a backstop, but SQLite for example does not unless
    ``PRAGMA foreign_keys=ON`` is set).
    """
    if not candidate_ids:
        return
    candidates = db.scalars(
        select(Candidate).where(Candidate.id.in_(candidate_ids))
    ).all()
    for candidate in candidates:
        db.delete(candidate)


def delete_files(files: List[Tuple[int, Path]]) -> Tuple[int, int, List[Path]]:
    """Delete CV files on disk. Returns (deleted, already_gone, failed_paths)."""
    deleted = 0
    already_gone = 0
    failed: List[Path] = []
    for _, path in files:
        try:
            if path.exists():
                path.unlink()
                deleted += 1
            else:
                already_gone += 1
        except OSError as exc:
            print(f"  ! could not remove {path}: {exc}", file=sys.stderr)
            failed.append(path)
    return deleted, already_gone, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually perform the delete. Without this flag the script "
        "only prints a preview and exits.",
    )
    parser.add_argument(
        "--purge-audit",
        action="store_true",
        help="Also delete audit_logs rows with action='hr.candidate.bulk_upload'.",
    )
    args = parser.parse_args()

    db: Session = SessionLocal()
    try:
        candidate_ids = _bulk_candidate_ids(db)
        audit_count = int(
            db.execute(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == BULK_UPLOAD_AUDIT_ACTION)
            ).scalar()
            or 0
        )
        files = _cv_file_paths(db, candidate_ids)
        _print_preview(db, candidate_ids, audit_count, files)

        if not args.confirm:
            print()
            print(" Dry run only. Re-run with --confirm to actually delete.")
            return 0

        if not candidate_ids and not (args.purge_audit and audit_count):
            print(" Nothing to do.")
            return 0

        print()
        print(" --confirm given. Deleting from the database now…")
        purge(db, candidate_ids)
        if args.purge_audit and audit_count:
            db.execute(
                delete(AuditLog).where(AuditLog.action == BULK_UPLOAD_AUDIT_ACTION)
            )
            print(f"  - audit_logs: deleted {audit_count} bulk-upload entries")
        db.commit()
        print(f"  - hr_candidates: deleted {len(candidate_ids)} rows "
              f"(plus all CASCADE children)")

        print(" Removing CV files from disk…")
        deleted, already_gone, failed = delete_files(files)
        print(f"  - files removed: {deleted}")
        print(f"  - already missing: {already_gone}")
        if failed:
            print(f"  - failed: {len(failed)} (see stderr above)")
            return 2

        print(" Done.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

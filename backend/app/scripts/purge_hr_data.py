"""One-shot: purge all HR candidate-side data for a fresh start.

Two-mode operation:

  * **dry-run** (default) — counts every row that *would* be deleted
    across the candidate dependency tree, plus how many R2 CV
    objects would be reaped (if ``--purge-r2``), and exits non-
    destructively.
  * **--apply** — runs the deletion inside a single transaction
    so a per-row failure halfway through rolls the whole purge back.

What it deletes (default scope):

  * ``hr_candidates`` and the entire cascade chain:
      - ``hr_candidate_documents`` (the CV bytes' DB rows)
      - ``hr_candidate_extracted_data``
      - ``hr_candidate_notes``
      - ``hr_candidate_tags``
      - ``hr_candidate_job_applications`` and:
          - ``hr_candidate_scores`` + breakdowns
          - ``hr_candidate_ai_reviews``
          - ``hr_candidate_status_history``
          - ``hr_interviews`` + feedbacks
          - ``hr_offer_tracking`` + status_history
          - ``hr_candidate_auto_reviews``
  * Assessment workflow per-candidate rows (cascade from candidate):
      - ``hr_assessment_invites``
      - ``hr_assessment_submissions``
      - ``hr_assessment_answers``

What it preserves (default):

  * ``hr_job_openings`` (templates HR keeps using)
  * ``hr_job_revisions`` / ``hr_job_approval_history``
  * ``hr_assessments`` / ``hr_assessment_questions`` /
    ``hr_assessment_choices`` (reusable assessment templates)
  * ``users`` / ``roles`` / ``permissions`` / settings tables
  * ``audit_logs`` / ``email_logs`` (history)
  * ``hr_scorecard_templates`` / ``hr_saved_candidate_searches``

Optional extras:

  * ``--purge-r2`` — also issues ``storage.delete_sync(key)`` for
    every ``CandidateDocument.file_path`` so the R2 bucket doesn't
    keep the orphaned CV bytes. Logs each delete. R2 failures
    are warnings, not aborts (the DB rows are already gone — a
    sweep can pick up the stragglers later).
  * ``--include-jobs`` — also drops every ``hr_job_openings`` and
    its revision/approval history. Useful only when you want to
    re-bootstrap the whole HR side from scratch.
  * ``--include-assessment-templates`` — also drops every
    ``hr_assessments`` row and its questions / choices.

Run locally:

    docker compose exec backend python -m app.scripts.purge_hr_data
    docker compose exec backend python -m app.scripts.purge_hr_data --apply --purge-r2

Run on EC2:

    docker compose -f docker-compose.prod.yml exec backend \\
        python -m app.scripts.purge_hr_data
    docker compose -f docker-compose.prod.yml exec backend \\
        python -m app.scripts.purge_hr_data --apply --purge-r2
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Iterable, List, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.hr_assessment import (
    Assessment,
    AssessmentAnswer,
    AssessmentChoice,
    AssessmentInvite,
    AssessmentQuestion,
    AssessmentSubmission,
)
from app.models.hr_ats import (
    Candidate,
    CandidateAIReview,
    CandidateAutoReview,
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
    JobApprovalHistory,
    JobOpening,
    JobRevision,
    OfferStatusHistory,
    OfferTracking,
)
from app.services.storage import get_storage


logger = logging.getLogger("purge_hr_data")


# Order matters: children before parents so SQLite (no DEFERRABLE
# FKs) doesn't trip on referential checks. PostgreSQL would happily
# accept any order inside a single transaction, but keeping the list
# child-first means the script behaves identically on both backends.
CANDIDATE_SCOPE: Tuple[Tuple[str, type], ...] = (
    # Assessment per-candidate rows
    ("hr_assessment_answers", AssessmentAnswer),
    ("hr_assessment_submissions", AssessmentSubmission),
    ("hr_assessment_invites", AssessmentInvite),
    # Per-application
    ("hr_offer_status_history", OfferStatusHistory),
    ("hr_offer_tracking", OfferTracking),
    ("hr_interview_feedbacks", InterviewFeedback),
    ("hr_interviews", Interview),
    ("hr_candidate_status_history", CandidateStatusHistory),
    ("hr_candidate_ai_reviews", CandidateAIReview),
    ("hr_candidate_auto_reviews", CandidateAutoReview),
    ("hr_candidate_score_breakdowns", CandidateScoreBreakdown),
    ("hr_candidate_scores", CandidateScore),
    ("hr_candidate_job_applications", CandidateJobApplication),
    # Per-candidate
    ("hr_candidate_notes", CandidateNote),
    ("hr_candidate_tags", CandidateTag),
    ("hr_candidate_extracted_data", CandidateExtractedData),
    ("hr_candidate_documents", CandidateDocument),
    ("hr_candidates", Candidate),
)

JOBS_SCOPE: Tuple[Tuple[str, type], ...] = (
    ("hr_job_approval_history", JobApprovalHistory),
    ("hr_job_revisions", JobRevision),
    ("hr_job_openings", JobOpening),
)

ASSESSMENT_TEMPLATE_SCOPE: Tuple[Tuple[str, type], ...] = (
    ("hr_assessment_choices", AssessmentChoice),
    ("hr_assessment_questions", AssessmentQuestion),
    ("hr_assessments", Assessment),
)


def _count(db: Session, scope: Iterable[Tuple[str, type]]) -> List[Tuple[str, int]]:
    rows: list[Tuple[str, int]] = []
    for label, model in scope:
        n = db.execute(select(func.count()).select_from(model)).scalar_one()
        rows.append((label, int(n or 0)))
    return rows


def _collect_cv_keys(db: Session) -> list[str]:
    """Every CV storage key currently referenced on a CandidateDocument.

    Snapshotted before deletion so an ``--apply --purge-r2`` pass can
    delete the bytes even after the DB rows are gone.
    """
    keys = db.execute(select(CandidateDocument.file_path)).scalars().all()
    return [k for k in keys if k]


def _delete_in_scope(db: Session, scope: Iterable[Tuple[str, type]]) -> None:
    for label, model in scope:
        result = db.execute(delete(model))
        logger.info("  deleted %s rows from %s", result.rowcount or 0, label)


def _purge_r2(keys: list[str]) -> Tuple[int, int]:
    """Try to delete every referenced CV key from the storage backend.

    Returns (deleted_count, failed_count). Failures are logged but
    not raised — the DB rows are gone either way; a failed R2 delete
    is a stranded object, not a data-integrity problem.
    """
    if not keys:
        return 0, 0
    storage = get_storage()
    deleted = failed = 0
    for key in keys:
        # CV file_paths can hold a legacy URL form
        # (``/api/v1/uploads/cvs/<file>``) instead of the modern
        # storage key. Normalise via the cv_storage helper so the
        # delete hits the right object regardless of which shape
        # the row carries.
        from app.services.cv_storage import _storage_key_from_legacy

        try:
            normalised = _storage_key_from_legacy(key)
        except FileNotFoundError:
            logger.warning("  skipping unrecognised file_path: %r", key)
            failed += 1
            continue

        try:
            storage.delete_sync(normalised)
            deleted += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("  R2 delete failed for %s: %s", normalised, exc)
            failed += 1
    return deleted, failed


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Purge HR candidate data for a fresh start. Defaults to "
            "dry-run; pass --apply to actually delete."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Actually delete. Without this flag the script only counts "
            "what would be deleted and exits."
        ),
    )
    parser.add_argument(
        "--purge-r2",
        action="store_true",
        help=(
            "Also delete the CV files from the storage backend (R2). "
            "Only honoured with --apply."
        ),
    )
    parser.add_argument(
        "--include-jobs",
        action="store_true",
        help=(
            "Also drop every hr_job_openings row + revisions + approval "
            "history. Off by default — HR usually wants to keep the job "
            "templates."
        ),
    )
    parser.add_argument(
        "--include-assessment-templates",
        action="store_true",
        help=(
            "Also drop every hr_assessments + questions + choices. Off "
            "by default — assessment templates are reusable across "
            "candidate cohorts."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
    )

    # Compose the full scope.
    scope: List[Tuple[str, type]] = list(CANDIDATE_SCOPE)
    if args.include_jobs:
        scope.extend(JOBS_SCOPE)
    if args.include_assessment_templates:
        scope.extend(ASSESSMENT_TEMPLATE_SCOPE)

    db = SessionLocal()
    try:
        # --- 1. Count -------------------------------------------------------
        counts = _count(db, scope)
        total = sum(n for _, n in counts)
        cv_keys = _collect_cv_keys(db)

        logger.info("=" * 64)
        logger.info("Pre-flight count — what would be deleted:")
        for label, n in counts:
            logger.info("  %-40s %8d", label, n)
        logger.info("  %-40s %8d", "(R2 CV objects)", len(cv_keys))
        logger.info("-" * 64)
        logger.info("  %-40s %8d", "TOTAL ROWS", total)
        logger.info("=" * 64)

        if not args.apply:
            logger.info("Dry-run. Pass --apply to actually delete.")
            return 0

        # --- 2. Apply -------------------------------------------------------
        logger.info("APPLY: deleting rows…")
        _delete_in_scope(db, scope)
        db.commit()
        logger.info("DB delete committed.")

        # --- 3. R2 -----------------------------------------------------------
        if args.purge_r2:
            logger.info("R2: deleting %d CV objects…", len(cv_keys))
            deleted, failed = _purge_r2(cv_keys)
            logger.info("R2 summary: %d deleted, %d failed.", deleted, failed)
        else:
            if cv_keys:
                logger.warning(
                    "Skipped R2 purge — %d CV objects are now orphaned. "
                    "Re-run with --purge-r2 to clean them, or sweep the "
                    "bucket by hand.",
                    len(cv_keys),
                )

        logger.info("Purge complete.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

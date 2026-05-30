"""One-shot CV→R2 migration script — behaviour tests.

Locks the contract the operator will rely on when running the script
in production:

  * dry-run reports what would happen + makes no DB or storage changes
  * --apply uploads bytes to the storage backend at the new key and
    rewrites ``CandidateDocument.file_path``
  * --apply --purge also unlinks the legacy local file
  * already-migrated rows (``file_path`` starts with ``career/cv/``) are
    skipped on re-runs
  * rows whose local file is missing report ``missing`` and the DB row
    is left alone — the operator can re-upload via the admin UI

Runs against the LocalStorageBackend (which is what the test
fixtures wire up); end-to-end coverage of the R2 backend is held by
``test_qr_codes.py`` + the existing storage smoke tests.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.models.hr_ats import Candidate, CandidateDocument


def _seed_legacy_cv(
    db_session: Session,
    tmp_path: Path,
    *,
    filename: str = "abc123def456.pdf",
    write_to_disk: bool = True,
) -> CandidateDocument:
    """Stand up a candidate + a legacy-shape CandidateDocument row.

    Pre-R2 the column held ``/api/v1/uploads/cvs/<file>`` and the
    bytes lived under ``{upload_dir}/cvs/<file>``. The fixture
    mirrors that exactly so the migration sees the real shape.
    """
    candidate = Candidate(full_name="Jane CV", email=f"{filename}@test.example")
    db_session.add(candidate)
    db_session.flush()

    doc = CandidateDocument(
        candidate_id=candidate.id,
        filename=filename,
        file_path=f"/api/v1/uploads/cvs/{filename}",
        mime_type="application/pdf",
        file_size=12,
        file_hash="0" * 64,
        is_primary=True,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    if write_to_disk:
        cvs_dir = tmp_path / "cvs"
        cvs_dir.mkdir(parents=True, exist_ok=True)
        (cvs_dir / filename).write_bytes(b"%PDF-fake-legacy-bytes\n")

    return doc


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


def test_dry_run_does_not_mutate(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    doc = _seed_legacy_cv(db_session, tmp_path)
    original_path = doc.file_path

    from app.scripts.migrate_cvs_to_r2 import _migrate_one

    outcome = _migrate_one(
        db_session, doc, tmp_path, apply=False, purge=False
    )
    assert outcome == "migrated"
    db_session.refresh(doc)
    # No DB rewrite in dry-run.
    assert doc.file_path == original_path
    # Local file still present.
    assert (tmp_path / "cvs" / "abc123def456.pdf").exists()


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def test_apply_rewrites_file_path_and_uploads_bytes(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services.storage import get_storage

    get_settings.cache_clear()
    doc = _seed_legacy_cv(db_session, tmp_path)

    from app.scripts.migrate_cvs_to_r2 import _migrate_one

    outcome = _migrate_one(
        db_session, doc, tmp_path, apply=True, purge=False
    )
    assert outcome == "migrated"
    db_session.refresh(doc)
    assert doc.file_path == "career/cv/abc123def456.pdf"

    # Bytes round-trip via the storage backend at the new key.
    assert get_storage().download_sync("career/cv/abc123def456.pdf").startswith(
        b"%PDF"
    )
    # Without --purge the legacy file is still on disk.
    assert (tmp_path / "cvs" / "abc123def456.pdf").exists()


def test_apply_with_purge_removes_legacy_file(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    doc = _seed_legacy_cv(db_session, tmp_path)

    from app.scripts.migrate_cvs_to_r2 import _migrate_one

    outcome = _migrate_one(
        db_session, doc, tmp_path, apply=True, purge=True
    )
    assert outcome == "migrated"
    assert not (tmp_path / "cvs" / "abc123def456.pdf").exists()


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_already_migrated_row_is_skipped(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    candidate = Candidate(full_name="Already Done", email="done@test.example")
    db_session.add(candidate)
    db_session.flush()
    doc = CandidateDocument(
        candidate_id=candidate.id,
        filename="zz.pdf",
        # Already on R2 — file_path is the storage key.
        file_path="career/cv/zz.pdf",
        mime_type="application/pdf",
        file_size=10,
        file_hash="z" * 64,
        is_primary=True,
    )
    db_session.add(doc)
    db_session.commit()

    from app.scripts.migrate_cvs_to_r2 import _migrate_one

    assert (
        _migrate_one(db_session, doc, tmp_path, apply=True, purge=True)
        == "skipped"
    )


# ---------------------------------------------------------------------------
# Missing local file
# ---------------------------------------------------------------------------


def test_missing_local_file_reports_missing_and_leaves_row_alone(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    doc = _seed_legacy_cv(db_session, tmp_path, write_to_disk=False)
    original_path = doc.file_path

    from app.scripts.migrate_cvs_to_r2 import _migrate_one

    assert (
        _migrate_one(db_session, doc, tmp_path, apply=True, purge=True)
        == "missing"
    )
    db_session.refresh(doc)
    # Row untouched so the operator's re-upload via the admin UI can
    # land on the same DB row.
    assert doc.file_path == original_path


# ---------------------------------------------------------------------------
# Re-run after a successful apply is a no-op
# ---------------------------------------------------------------------------


def test_apply_then_re_apply_is_skipped(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    doc = _seed_legacy_cv(db_session, tmp_path)

    from app.scripts.migrate_cvs_to_r2 import _migrate_one

    assert _migrate_one(db_session, doc, tmp_path, apply=True, purge=False) == "migrated"
    db_session.refresh(doc)
    # Second pass — the row's been rewritten to the modern key, so
    # the script short-circuits.
    assert _migrate_one(db_session, doc, tmp_path, apply=True, purge=False) == "skipped"

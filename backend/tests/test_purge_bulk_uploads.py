"""Tests for the `purge_bulk_uploads` cleanup script.

The script's main() opens its own SessionLocal, so the tests invoke
the helpers directly with the in-memory test session. This exercises
exactly the same DB delete + filesystem delete logic without binding
to PostgreSQL.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    Candidate,
    CandidateDocument,
    CandidateJobApplication,
    SOURCE_BULK_UPLOAD,
)
from app.scripts.purge_bulk_uploads import (
    _bulk_candidate_ids,
    _cv_file_paths,
    delete_files,
    purge,
)


@pytest.fixture
def fake_cvs_dir(tmp_path, monkeypatch):
    """Redirect the script's resolved CV dir to a temp folder.

    The script computes `Path(settings.upload_dir) / 'cvs'`. Pointing
    `upload_dir` at the tmp path keeps file operations sandboxed.
    """
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    cvs = tmp_path / "cvs"
    cvs.mkdir(parents=True, exist_ok=True)
    yield cvs
    get_settings.cache_clear()


def _add_bulk_candidate(
    db: Session, fake_cvs_dir: Path, *, name: str, filename: str
) -> Candidate:
    """Create a bulk-uploaded candidate + document row + on-disk file."""
    candidate = Candidate(full_name=name, source=SOURCE_BULK_UPLOAD)
    db.add(candidate)
    db.flush()

    doc = CandidateDocument(
        candidate_id=candidate.id,
        filename=filename,
        file_path=f"/api/v1/uploads/cvs/{filename}",
        file_size=42,
        mime_type="application/pdf",
        file_hash="abc" * 20,
        is_primary=True,
    )
    db.add(doc)

    app = CandidateJobApplication(
        candidate_id=candidate.id,
        status="cv_received",
        source=SOURCE_BULK_UPLOAD,
    )
    db.add(app)
    db.commit()

    # Write the actual CV bytes so the file delete has something to remove.
    (fake_cvs_dir / filename).write_bytes(b"%PDF-1.4 fake")
    return candidate


def test_dry_run_finds_nothing_when_db_empty(db_session: Session, fake_cvs_dir):
    ids = _bulk_candidate_ids(db_session)
    assert ids == []
    files = _cv_file_paths(db_session, ids)
    assert files == []


def test_identifies_bulk_uploaded_candidates(db_session: Session, fake_cvs_dir):
    bulk_alpha = _add_bulk_candidate(
        db_session, fake_cvs_dir, name="alpha", filename="aaaa1111.pdf"
    )
    bulk_beta = _add_bulk_candidate(
        db_session, fake_cvs_dir, name="beta", filename="bbbb2222.pdf"
    )
    # A normal (non-bulk) candidate must not be picked up.
    other = Candidate(full_name="manual", source="manual")
    db_session.add(other)
    db_session.commit()

    ids = _bulk_candidate_ids(db_session)
    assert set(ids) == {bulk_alpha.id, bulk_beta.id}


def test_cv_file_paths_resolve_under_uploads(db_session: Session, fake_cvs_dir):
    cand = _add_bulk_candidate(
        db_session, fake_cvs_dir, name="alpha", filename="aaaa1111.pdf"
    )
    files = _cv_file_paths(db_session, [cand.id])
    assert len(files) == 1
    doc_id, path = files[0]
    assert path.name == "aaaa1111.pdf"
    assert path.parent == fake_cvs_dir.resolve()
    assert path.exists()


def test_purge_deletes_db_rows_and_cascades(
    db_session: Session, fake_cvs_dir
):
    bulk = _add_bulk_candidate(
        db_session, fake_cvs_dir, name="alpha", filename="aaaa1111.pdf"
    )
    other = Candidate(full_name="manual", source="manual")
    db_session.add(other)
    db_session.commit()

    ids = _bulk_candidate_ids(db_session)
    purge(db_session, ids)
    db_session.commit()

    # Bulk candidate gone.
    assert db_session.get(Candidate, bulk.id) is None
    # Cascade removed the document + application.
    assert db_session.query(CandidateDocument).count() == 0
    assert db_session.query(CandidateJobApplication).count() == 0
    # Non-bulk candidate untouched.
    assert db_session.get(Candidate, other.id) is not None


def test_delete_files_removes_existing_and_tolerates_missing(
    db_session: Session, fake_cvs_dir
):
    a = _add_bulk_candidate(
        db_session, fake_cvs_dir, name="a", filename="aaaa1111.pdf"
    )
    b = _add_bulk_candidate(
        db_session, fake_cvs_dir, name="b", filename="bbbb2222.pdf"
    )
    # Pre-emptively delete one file so the second path is "missing on disk".
    (fake_cvs_dir / "bbbb2222.pdf").unlink()

    ids = _bulk_candidate_ids(db_session)
    files = _cv_file_paths(db_session, ids)
    deleted, already_gone, failed = delete_files(files)
    assert deleted == 1
    assert already_gone == 1
    assert failed == []
    # The remaining file actually went away.
    assert not (fake_cvs_dir / "aaaa1111.pdf").exists()


def test_full_dry_run_then_confirm(db_session: Session, fake_cvs_dir, capsys):
    """Two-phase: a print-only preview, then an explicit purge."""
    _add_bulk_candidate(
        db_session, fake_cvs_dir, name="alpha", filename="aaaa1111.pdf"
    )
    _add_bulk_candidate(
        db_session, fake_cvs_dir, name="beta", filename="bbbb2222.pdf"
    )

    # Dry run: identify targets.
    ids = _bulk_candidate_ids(db_session)
    files = _cv_file_paths(db_session, ids)
    assert len(ids) == 2
    assert len(files) == 2

    # Confirmed delete.
    purge(db_session, ids)
    db_session.commit()
    deleted, _, failed = delete_files(files)
    assert deleted == 2
    assert failed == []

    # Re-running finds nothing.
    assert _bulk_candidate_ids(db_session) == []

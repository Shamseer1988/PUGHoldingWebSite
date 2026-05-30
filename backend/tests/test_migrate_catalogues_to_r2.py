"""One-shot R2 migration script — behaviour tests.

Validates the script's contract end-to-end against the local-disk
storage backend (which gives us a real upload destination without
needing a live R2 account):

* A catalogue whose URLs still point at ``/api/v1/uploads/...``
  gets every file uploaded through the storage backend; the row +
  page URLs are rewritten to whatever the backend returns.
* A catalogue whose URLs already start with ``http`` is skipped
  (re-runs are idempotent).
* A page whose source file is missing on disk is left alone — the
  rest of the catalogue still migrates.
* QR brand logos follow the same migration path.
* ``--dry-run`` neither uploads bytes nor mutates the DB.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image
from sqlalchemy.orm import Session

from app.models.marketing import Catalogue, CataloguePage


def _tiny_webp() -> bytes:
    img = Image.new("RGB", (8, 8), (33, 99, 33))
    buf = io.BytesIO()
    img.save(buf, format="WEBP")
    return buf.getvalue()


def _tiny_png() -> bytes:
    img = Image.new("RGB", (8, 8), (200, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _seed_local_catalogue(
    db_session: Session, tmp_path, *, slug: str = "legacy", pages: int = 2
) -> Catalogue:
    """Stand up a catalogue + page rows in the pre-R2 shape: URLs
    point at ``/api/v1/uploads/...`` and the files actually exist
    under ``tmp_path / catalogues / {id} /``."""
    row = Catalogue(
        slug=slug,
        title="Legacy",
        page_count=pages,
        pdf_url="/api/v1/uploads/catalogues/__temp__/source.pdf",
        cover_image_url="/api/v1/uploads/catalogues/__temp__/page_001.thumb.webp",
    )
    db_session.add(row)
    db_session.flush()

    # The URL had a temporary placeholder until we knew the row id;
    # rewrite to the actual id now.
    row.pdf_url = f"/api/v1/uploads/catalogues/{row.id}/source.pdf"
    row.cover_image_url = (
        f"/api/v1/uploads/catalogues/{row.id}/page_001.thumb.webp"
    )

    cat_dir = tmp_path / "catalogues" / str(row.id)
    cat_dir.mkdir(parents=True, exist_ok=True)
    (cat_dir / "source.pdf").write_bytes(b"%PDF-fake-source-bytes\n")

    for n in range(1, pages + 1):
        page_bytes = _tiny_webp()
        thumb_bytes = _tiny_webp()
        (cat_dir / f"page_{n:03d}.webp").write_bytes(page_bytes)
        (cat_dir / f"page_{n:03d}.thumb.webp").write_bytes(thumb_bytes)
        db_session.add(
            CataloguePage(
                catalogue_id=row.id,
                page_number=n,
                image_url=f"/api/v1/uploads/catalogues/{row.id}/page_{n:03d}.webp",
                thumbnail_url=f"/api/v1/uploads/catalogues/{row.id}/page_{n:03d}.thumb.webp",
                width=8,
                height=8,
                file_size_bytes=len(page_bytes),
            )
        )
    db_session.commit()
    db_session.refresh(row)
    return row


def _patch_session_local(monkeypatch, db_session: Session) -> None:
    """The script reaches for its own ``SessionLocal``; bend it to the
    test session so we observe the same DB rows."""
    from contextlib import contextmanager

    @contextmanager
    def _nothing():
        yield

    class _Wrapper:
        def __call__(self) -> Session:
            return db_session

    # The script calls ``SessionLocal()`` and later ``.close()``;
    # patch the class with a callable that returns our session and a
    # no-op ``close`` so we don't kill the fixture session.
    class _SessionProxy:
        def __init__(self, target: Session) -> None:
            self._target = target

        def __getattr__(self, name):
            return getattr(self._target, name)

        def close(self) -> None:  # noqa: D401
            """Don't actually close the fixture session."""

    def _factory() -> _SessionProxy:
        return _SessionProxy(db_session)

    monkeypatch.setattr(
        "app.scripts.migrate_catalogues_to_r2.SessionLocal", _factory
    )


# ---------------------------------------------------------------------------
# Catalogue migration
# ---------------------------------------------------------------------------


def test_migrates_local_catalogue_to_storage(
    db_session: Session, tmp_path, monkeypatch
):
    """Happy path: a legacy catalogue's source PDF + every page +
    every thumbnail end up in storage under the deterministic keys
    the new processor uses, and the row URLs are rewritten to point
    there."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services.storage import get_storage

    get_settings.cache_clear()
    cat = _seed_local_catalogue(db_session, tmp_path, pages=2)

    from app.scripts.migrate_catalogues_to_r2 import (
        _migrate_catalogue,
        _migrate_qr_logo,
    )

    outcome = _migrate_catalogue(
        db_session, cat, tmp_path, dry_run=False
    )
    assert outcome == "migrated"
    db_session.refresh(cat)

    # Row URL is now whatever the storage backend returned. The
    # local backend formats as ``/api/v1/uploads/...``; that's still
    # what we want — the bytes really did go through ``upload_sync``.
    storage = get_storage()
    assert storage.download_sync(f"catalogues/{cat.id}/source.pdf").startswith(
        b"%PDF-fake"
    )
    assert storage.download_sync(f"catalogues/{cat.id}/page_001.webp") == _tiny_webp_for_compare(
        cat, 1, tmp_path
    )
    # Page rows rewritten.
    pages = sorted(cat.pages, key=lambda p: p.page_number)
    assert len(pages) == 2
    for n, page in enumerate(pages, start=1):
        assert page.image_url.endswith(f"/page_{n:03d}.webp")
        assert page.thumbnail_url.endswith(f"/page_{n:03d}.thumb.webp")
    # Cover image set to page 1 thumbnail.
    assert cat.cover_image_url == pages[0].thumbnail_url

    # NOTE: with the local-disk backend the URL the storage returns
    # still starts with ``/api/v1/uploads/`` (same shape as before),
    # so a hypothetical second pass would not skip — it would just
    # overwrite the same bytes. The re-run idempotency we actually
    # care about (R2 in production) is covered by
    # ``test_migrate_skips_already_r2_url``.


def _tiny_webp_for_compare(cat: Catalogue, page_num: int, tmp_path) -> bytes:
    """Read the same bytes we wrote during _seed_local_catalogue so
    the upload-roundtrip assertion is byte-exact."""
    return (
        tmp_path
        / "catalogues"
        / str(cat.id)
        / f"page_{page_num:03d}.webp"
    ).read_bytes()


def test_migrate_reports_missing_source_pdf(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    cat = _seed_local_catalogue(db_session, tmp_path)
    # Delete the source PDF so the script's existence check kicks in.
    (tmp_path / "catalogues" / str(cat.id) / "source.pdf").unlink()

    from app.scripts.migrate_catalogues_to_r2 import _migrate_catalogue

    assert (
        _migrate_catalogue(db_session, cat, tmp_path, dry_run=False)
        == "missing"
    )
    # Row URLs untouched.
    db_session.refresh(cat)
    assert cat.pdf_url.startswith("/api/v1/uploads/")


def test_migrate_skips_already_r2_url(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    cat = _seed_local_catalogue(db_session, tmp_path)
    cat.pdf_url = "https://media.example.com/catalogues/9/source.pdf"
    db_session.commit()

    from app.scripts.migrate_catalogues_to_r2 import _migrate_catalogue

    assert (
        _migrate_catalogue(db_session, cat, tmp_path, dry_run=False)
        == "skipped"
    )


def test_migrate_leaves_page_alone_when_file_missing(
    db_session: Session, tmp_path, monkeypatch
):
    """Source PDF migrates fine but page 2's WebP is missing — the
    script logs a warning and leaves that page's URL alone instead
    of bailing the whole catalogue."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    cat = _seed_local_catalogue(db_session, tmp_path, pages=2)
    (tmp_path / "catalogues" / str(cat.id) / "page_002.webp").unlink()

    from app.scripts.migrate_catalogues_to_r2 import _migrate_catalogue

    assert (
        _migrate_catalogue(db_session, cat, tmp_path, dry_run=False)
        == "migrated"
    )
    db_session.refresh(cat)

    pages = sorted(cat.pages, key=lambda p: p.page_number)
    # Page 1 was migrated (URL no longer starts with /api/v1/uploads/
    # only because the local backend still returns that prefix — what
    # really matters is the storage_sync call happened, which we
    # assert below).
    from app.services.storage import get_storage

    storage = get_storage()
    assert storage.download_sync(
        f"catalogues/{cat.id}/page_001.webp"
    ), "page 1 should have round-tripped through storage"

    # Page 2's URL stays as the legacy local form because we didn't
    # touch it.
    assert pages[1].image_url.startswith("/api/v1/uploads/")


def test_dry_run_does_not_upload_or_mutate(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    cat = _seed_local_catalogue(db_session, tmp_path)
    original_pdf_url = cat.pdf_url

    from app.scripts.migrate_catalogues_to_r2 import _migrate_catalogue

    assert (
        _migrate_catalogue(db_session, cat, tmp_path, dry_run=True)
        == "migrated"
    )
    db_session.refresh(cat)
    # Row URL unchanged + page URLs unchanged — that's the
    # observable contract of ``--dry-run``. We can't usefully assert
    # "storage wasn't touched" under the local backend because the
    # seeded source.pdf already lives at the same path the backend
    # would write to; in production R2 the same code path would
    # genuinely leave the bucket untouched.
    assert cat.pdf_url == original_pdf_url
    for page in cat.pages:
        assert page.image_url.startswith("/api/v1/uploads/")
        assert page.thumbnail_url.startswith("/api/v1/uploads/")


# ---------------------------------------------------------------------------
# QR-logo migration
# ---------------------------------------------------------------------------


def test_migrates_local_qr_logo(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings
    from app.services.storage import get_storage

    get_settings.cache_clear()
    cat = _seed_local_catalogue(db_session, tmp_path)
    cat.qr_logo_url = f"/api/v1/uploads/qr-logos/{cat.id}.png"
    db_session.commit()
    qr_dir = tmp_path / "qr-logos"
    qr_dir.mkdir()
    png_bytes = _tiny_png()
    (qr_dir / f"{cat.id}.png").write_bytes(png_bytes)

    from app.scripts.migrate_catalogues_to_r2 import _migrate_qr_logo

    assert (
        _migrate_qr_logo(db_session, cat, tmp_path, dry_run=False)
        == "migrated"
    )
    db_session.refresh(cat)
    assert get_storage().download_sync(f"qr-logos/{cat.id}.png") == png_bytes


def test_skips_qr_logo_when_no_url(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    cat = _seed_local_catalogue(db_session, tmp_path)
    assert cat.qr_logo_url is None

    from app.scripts.migrate_catalogues_to_r2 import _migrate_qr_logo

    assert (
        _migrate_qr_logo(db_session, cat, tmp_path, dry_run=False)
        == "skipped"
    )


def test_qr_logo_missing_file_reports_missing(
    db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    cat = _seed_local_catalogue(db_session, tmp_path)
    # URL on the row points at a logo that doesn't exist on disk.
    cat.qr_logo_url = f"/api/v1/uploads/qr-logos/{cat.id}.png"
    db_session.commit()

    from app.scripts.migrate_catalogues_to_r2 import _migrate_qr_logo

    assert (
        _migrate_qr_logo(db_session, cat, tmp_path, dry_run=False)
        == "missing"
    )


# ---------------------------------------------------------------------------
# End-to-end ``main()``
# ---------------------------------------------------------------------------


def test_main_walks_every_catalogue_and_exits_zero(
    db_session: Session, tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    _seed_local_catalogue(db_session, tmp_path, slug="a", pages=1)
    _seed_local_catalogue(db_session, tmp_path, slug="b", pages=2)

    _patch_session_local(monkeypatch, db_session)

    from app.scripts.migrate_catalogues_to_r2 import main

    # Argparse reads sys.argv — clear it for the run.
    monkeypatch.setattr("sys.argv", ["migrate_catalogues_to_r2"])
    assert main() == 0

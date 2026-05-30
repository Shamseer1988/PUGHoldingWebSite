"""Public ``GET /api/v1/offers/catalogues/{id}/download`` — R2-safe path.

Before the storage-backend rewrite this endpoint read the PDF off
local disk via a string-split on ``/api/v1/uploads/`` + ``Path``,
which 404s as soon as ``pdf_url`` is an R2 ``https://…`` URL. These
tests lock the new contract: the endpoint fetches via the storage
backend by deterministic key, increments ``download_count`` only on
a successful fetch, and emits a sane ``Content-Disposition`` even
when the original filename contains hostile characters.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.marketing import Catalogue
from app.services.catalogue_processor import source_pdf_key
from app.services.storage import get_storage


PUBLIC = "/api/v1/offers"


def _make_catalogue(
    db_session: Session,
    *,
    slug: str = "summer-2026",
    pdf_url: str = "https://media.example.com/catalogues/1/source.pdf",
    pdf_original_filename: str | None = "Summer Flyer 2026.pdf",
    is_active: bool = True,
) -> Catalogue:
    row = Catalogue(
        slug=slug,
        title="Summer Flyer",
        page_count=2,
        pdf_url=pdf_url,
        pdf_original_filename=pdf_original_filename,
        is_active=is_active,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _seed_pdf_in_storage(catalogue_id: int, pdf_bytes: bytes) -> None:
    """Push the catalogue's source PDF into whatever storage backend
    the test is running against (local-disk under tmp during tests).
    Mirrors what the processor would have done on upload."""
    get_storage().upload_sync(
        source_pdf_key(catalogue_id), pdf_bytes, "application/pdf"
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_download_returns_pdf_with_friendly_filename(
    client: TestClient, db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    cat = _make_catalogue(db_session)
    pdf_bytes = b"%PDF-1.4 fake summer flyer body\n"
    _seed_pdf_in_storage(cat.id, pdf_bytes)

    r = client.get(f"{PUBLIC}/catalogues/{cat.id}/download")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert (
        r.headers["content-disposition"]
        == 'attachment; filename="Summer Flyer 2026.pdf"'
    )
    assert r.content == pdf_bytes

    db_session.refresh(cat)
    assert cat.download_count == 1


def test_download_falls_back_to_slug_filename(
    client: TestClient, db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    cat = _make_catalogue(
        db_session, slug="winter-edit", pdf_original_filename=None
    )
    _seed_pdf_in_storage(cat.id, b"%PDF-1.4 fallback\n")

    r = client.get(f"{PUBLIC}/catalogues/{cat.id}/download")
    assert r.status_code == 200
    assert (
        r.headers["content-disposition"]
        == 'attachment; filename="winter-edit.pdf"'
    )


def test_download_sanitises_quotes_and_control_chars_in_filename(
    client: TestClient, db_session: Session, tmp_path, monkeypatch
):
    """A hostile or just-malformed ``pdf_original_filename`` can't
    break the ``Content-Disposition`` quoted-string."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    cat = _make_catalogue(
        db_session,
        pdf_original_filename='evil"; drop-table\n.pdf',
    )
    _seed_pdf_in_storage(cat.id, b"%PDF-1.4 hostile\n")

    r = client.get(f"{PUBLIC}/catalogues/{cat.id}/download")
    assert r.status_code == 200
    disposition = r.headers["content-disposition"]
    # No raw quote injected into the value, no newline.
    assert '"; drop' not in disposition
    assert "\n" not in disposition
    # And the structure is still a valid attachment header.
    assert disposition.startswith('attachment; filename="')
    assert disposition.endswith('.pdf"')


# ---------------------------------------------------------------------------
# 404 paths
# ---------------------------------------------------------------------------


def test_download_404_when_catalogue_inactive(
    client: TestClient, db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    cat = _make_catalogue(db_session, is_active=False)
    _seed_pdf_in_storage(cat.id, b"%PDF-1.4 inactive\n")

    r = client.get(f"{PUBLIC}/catalogues/{cat.id}/download")
    assert r.status_code == 404
    db_session.refresh(cat)
    assert cat.download_count == 0


def test_download_404_when_catalogue_missing(client: TestClient):
    assert (
        client.get(f"{PUBLIC}/catalogues/999999/download").status_code == 404
    )


def test_download_404_when_no_pdf_url(
    client: TestClient, db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    cat = _make_catalogue(db_session, pdf_url="")
    r = client.get(f"{PUBLIC}/catalogues/{cat.id}/download")
    assert r.status_code == 404


def test_download_404_when_storage_missing_object(
    client: TestClient, db_session: Session, tmp_path, monkeypatch
):
    """Row carries a pdf_url but the storage backend doesn't have the
    object — exactly the scenario that bit us on prod when the
    backend container's local upload dir got wiped on rebuild.
    Should surface a clean 404 rather than a 500."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    cat = _make_catalogue(db_session)
    # Deliberately do NOT seed bytes into storage.
    r = client.get(f"{PUBLIC}/catalogues/{cat.id}/download")
    assert r.status_code == 404
    db_session.refresh(cat)
    assert cat.download_count == 0


# ---------------------------------------------------------------------------
# URL form independence
# ---------------------------------------------------------------------------


def test_download_works_when_pdf_url_is_legacy_local_form(
    client: TestClient, db_session: Session, tmp_path, monkeypatch
):
    """A pre-R2 row whose ``pdf_url`` is ``/api/v1/uploads/...`` still
    downloads correctly — because the endpoint looks up by
    deterministic storage key, not by parsing the URL."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()

    cat = _make_catalogue(
        db_session, pdf_url="/api/v1/uploads/catalogues/1/source.pdf"
    )
    _seed_pdf_in_storage(cat.id, b"%PDF legacy\n")

    r = client.get(f"{PUBLIC}/catalogues/{cat.id}/download")
    assert r.status_code == 200
    assert r.content == b"%PDF legacy\n"

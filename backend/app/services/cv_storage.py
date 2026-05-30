"""CV file storage helpers.

Validates MIME type + size, computes a SHA-256 hash, pushes the bytes
through :mod:`app.services.storage` under
``career/cv/{hash_prefix}.{ext}``, and returns the storage **key**
(the string that gets persisted on ``CandidateDocument.file_path``).

The key is content-addressed, not application-scoped, because
``store_cv_bytes`` is called BEFORE the candidate / application rows
are created — the apply endpoint stores the file first, then runs
``ingest_candidate_application`` which links the key to the DB. This
gives us natural dedup for free: the same CV uploaded twice
collapses to one object, which keeps R2 storage costs predictable.

CVs are private — never linked publicly. HR fetches them through a
backend endpoint that ``302``-redirects to a fresh, short-lived
pre-signed URL via :func:`cv_download_url`. The CV parser still
takes a filesystem path (pdfminer / python-docx / pytesseract), so
:func:`read_cv_bytes` + :func:`stage_cv_locally` exist to bridge
in-process consumers (auto-review, bulk reports) to the new R2-backed
storage without touching the parser internals.

Bulk ZIP uploads iterate inner files of supported types and return
a list of metadata + skip records for unsupported entries.
"""
from __future__ import annotations

import contextlib
import hashlib
import tempfile
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from PIL import Image, UnidentifiedImageError

from app.services.storage import get_storage


# Image extensions that get re-baked through Pillow before storage so
# any embedded EXIF metadata, color profiles, or stego-style hidden
# chunks are stripped. PDF / DOC(X) bytes are left untouched — the
# downstream parser needs them intact, and the format is structured
# enough that we'd rather fail-closed at parse time than re-encode.
_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}


# MIME → extension whitelist for CVs.
ALLOWED_CV_MIME = {
    "application/pdf": "pdf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "image/png": "png",
    "image/jpeg": "jpg",
}
# Some clients send octet-stream — also accept by file extension.
ALLOWED_CV_EXT = {"pdf", "doc", "docx", "png", "jpg", "jpeg"}

MAX_CV_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_ZIP_BYTES = 50 * 1024 * 1024  # 50 MB


# Key prefix for every CV stored, regardless of whether the
# uploader was the public career page, an HR single upload, or an
# HR bulk ZIP. Lives alongside ``catalogues/``, ``cms/``, etc. in the
# R2 bucket — see ``docs`` for the full key catalogue.
CV_KEY_PREFIX = "career/cv"


@dataclass(slots=True)
class CvFileMetadata:
    """Return value of :func:`store_cv_bytes`.

    ``url`` is the **storage key** — historically this was a relative
    URL ``/api/v1/uploads/cvs/<hash>.<ext>`` because CVs lived on
    local disk and FastAPI's StaticFiles mount served them directly.
    Post-R2 the field still carries a string that gets stored
    verbatim on ``CandidateDocument.file_path``, but the string is
    now a storage backend key like ``career/cv/<hash>.<ext>``. The
    name is kept for back-compat with every consumer that already
    reads ``meta.url``.
    """

    url: str
    filename: str  # stored filename (hash + ext)
    original_name: str
    size: int
    mime_type: str
    file_hash: str  # sha256
    extension: str


class CvUploadError(Exception):
    """Raised for client-facing upload errors (bad type / too large / empty)."""


def _ext_from_name(name: str) -> str:
    suffix = Path(name).suffix.lower().lstrip(".")
    return suffix


def _resolve_ext(mime_type: str | None, original_name: str) -> str:
    if mime_type and mime_type in ALLOWED_CV_MIME:
        return ALLOWED_CV_MIME[mime_type]
    ext = _ext_from_name(original_name)
    if ext in ALLOWED_CV_EXT:
        return "jpg" if ext == "jpeg" else ext
    raise CvUploadError(
        f"Unsupported CV file type ({mime_type or 'unknown'} / "
        f"{original_name}). Allowed: PDF, DOC, DOCX, PNG, JPG."
    )


def _rebake_image_bytes(data: bytes, ext: str) -> bytes:
    """Round-trip image bytes through Pillow to strip EXIF/metadata
    and reject malformed files.

    A successful re-encode confirms the file really is the image type
    its extension claims and produces clean bytes (no hidden chunks,
    no scripts in metadata). On any decode error we raise
    ``CvUploadError`` so the uploader sees a 400 rather than the
    server storing a hostile payload.
    """
    try:
        img = Image.open(BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise CvUploadError(
            "Uploaded image could not be decoded — refusing to store."
        ) from exc

    pillow_fmt = "JPEG" if ext == "jpg" else ext.upper()
    out = BytesIO()
    # If the source has an alpha channel and we're writing JPEG, drop
    # it — JPEG can't represent alpha and Pillow otherwise raises.
    if pillow_fmt == "JPEG" and img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    img.save(out, format=pillow_fmt)
    return out.getvalue()


def store_cv_bytes(
    data: bytes,
    original_name: str,
    mime_type: str | None,
) -> CvFileMetadata:
    """Persist a single CV file and return its metadata.

    Identical content is deduplicated naturally — the SHA-256 prefix
    becomes the filename so re-uploads collapse to the same object.

    Image uploads (PNG / JPG) are re-baked through Pillow first so any
    EXIF, ICC profile, or stego-style metadata chunks are dropped and
    we don't store a hostile payload that happens to have a valid
    image header.
    """
    if not data:
        raise CvUploadError("Empty upload")
    if len(data) > MAX_CV_BYTES:
        raise CvUploadError(
            f"CV is too large ({len(data)} bytes). Max {MAX_CV_BYTES}."
        )

    ext = _resolve_ext(mime_type, original_name)

    # Image rebake (security): forces decode + re-encode and strips
    # metadata. PDF/DOC/DOCX bytes are stored as-is for the downstream
    # parser.
    if ext in _IMAGE_EXTENSIONS:
        data = _rebake_image_bytes(data, ext)

    file_hash = hashlib.sha256(data).hexdigest()
    filename = f"{file_hash[:16]}.{ext}"
    key = f"{CV_KEY_PREFIX}/{filename}"

    # Push to the storage backend (R2 in production, local disk in
    # dev). ``upload_sync`` is idempotent — R2 silently overwrites
    # the same key, local disk just rewrites the file. Either way
    # the content-addressed key means we never accumulate near-
    # duplicate copies of the same CV.
    storage = get_storage()
    storage.upload_sync(key, data, _content_type_for(ext, mime_type))

    return CvFileMetadata(
        url=key,
        filename=filename,
        original_name=original_name,
        size=len(data),
        mime_type=mime_type or "",
        file_hash=file_hash,
        extension=ext,
    )


# ---------------------------------------------------------------------------
# Read-side helpers — bridge the storage backend to consumers that still
# need bytes (parser, exports). Everything that reads a CV should go
# through one of these so the storage layer stays the single source of
# truth.
# ---------------------------------------------------------------------------


def read_cv_bytes(file_path: str) -> bytes:
    """Fetch CV bytes by storage key.

    ``file_path`` is whatever was stored on
    ``CandidateDocument.file_path`` — for new uploads that's the
    storage key (``career/cv/<hash>.<ext>``); for pre-migration rows
    it can still be the legacy ``/api/v1/uploads/cvs/<file>`` URL,
    which :func:`_storage_key_from_legacy` normalises.

    Raises ``FileNotFoundError`` when the object is missing from
    storage so callers can render a clean 404.
    """
    key = _storage_key_from_legacy(file_path)
    return get_storage().download_sync(key)


def cv_download_url(file_path: str, expires_in: int = 600) -> str:
    """Return a short-lived URL the browser can fetch the CV from.

    On R2: a real pre-signed GET URL bound to ``expires_in`` seconds
    (default 10 min — long enough for HR to click → load → print,
    short enough that a shared URL doesn't leak indefinitely). On
    the local backend: the legacy ``/api/v1/uploads/...`` URL the
    StaticFiles mount serves.
    """
    key = _storage_key_from_legacy(file_path)
    return get_storage().presigned_url(key, expires_in=expires_in)


@contextlib.contextmanager
def stage_cv_locally(file_path: str) -> Iterator[Path]:
    """Materialise a CV to a temp file on local disk so the parser
    libraries (pdfminer / python-docx / pytesseract) can open it
    with the path-based API they expect.

    Cleans the temp file on exit. Use as::

        with stage_cv_locally(doc.file_path) as p:
            text = extract_text(p, extension=doc.file_extension)

    Avoid letting the temp file outlive the ``with`` block — the
    point is to keep R2 bytes out of long-lived local state.
    """
    data = read_cv_bytes(file_path)
    suffix = "." + (Path(file_path).suffix.lstrip(".") or "bin")
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(data)
        tmp.flush()
        tmp.close()
        yield Path(tmp.name)
    finally:
        with contextlib.suppress(OSError):
            Path(tmp.name).unlink(missing_ok=True)


def _storage_key_from_legacy(file_path: str) -> str:
    """Normalise a ``CandidateDocument.file_path`` to a storage key.

    Three shapes flow through here in practice:

      * ``career/cv/<hash>.<ext>`` — modern key (post-migration), used as-is.
      * ``/api/v1/uploads/cvs/<file>`` — pre-R2 legacy URL.
      * ``cvs/<file>`` — same legacy layout without the StaticFiles
        prefix (some test fixtures dropped the leading mount).

    We map every legacy form to ``career/cv/<basename>`` because the
    migration script uploads the existing files to that key. After
    migration runs, every DB row's ``file_path`` is in the modern
    form and this function is a no-op for them.
    """
    s = (file_path or "").strip()
    if not s:
        raise FileNotFoundError("Empty CV file_path")
    if s.startswith(CV_KEY_PREFIX + "/"):
        return s
    legacy_prefix = "/api/v1/uploads/cvs/"
    if s.startswith(legacy_prefix):
        return f"{CV_KEY_PREFIX}/{s[len(legacy_prefix):]}"
    if s.startswith("cvs/"):
        return f"{CV_KEY_PREFIX}/{s[len('cvs/'):]}"
    # Last-resort: assume the whole string is the basename.
    return f"{CV_KEY_PREFIX}/{Path(s).name}"


def _content_type_for(ext: str, mime_type: Optional[str]) -> str:
    """Resolve the Content-Type R2 should serve the file with.

    Prefer the uploader-declared MIME when it's in our allowlist;
    fall back to the extension lookup so the edge sets a sensible
    header even when the client sent ``application/octet-stream``.
    """
    if mime_type and mime_type in ALLOWED_CV_MIME:
        return mime_type
    return {
        "pdf": "application/pdf",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
    }.get(ext, "application/octet-stream")


@dataclass(slots=True)
class BulkExtractResult:
    files: List[CvFileMetadata]
    skipped: List[Tuple[str, str]]  # (entry_name, reason)


def extract_cvs_from_zip(data: bytes) -> BulkExtractResult:
    """Walk a ZIP and persist every supported CV file inside.

    Unsupported / oversize entries are reported in the `skipped` list
    instead of raising — the caller can present per-file status to HR.
    Directories and macOS resource forks are ignored silently.
    """
    if len(data) > MAX_ZIP_BYTES:
        raise CvUploadError(
            f"ZIP is too large ({len(data)} bytes). Max {MAX_ZIP_BYTES}."
        )

    try:
        zf = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise CvUploadError("ZIP file is not valid or is corrupted") from exc

    files: List[CvFileMetadata] = []
    skipped: List[Tuple[str, str]] = []

    for info in zf.infolist():
        # Skip directories, macOS metadata files, and dotfiles.
        if info.is_dir():
            continue
        name = info.filename
        base = Path(name).name
        if base.startswith(".") or "__MACOSX" in name:
            continue
        ext = _ext_from_name(base)
        if ext not in ALLOWED_CV_EXT:
            skipped.append((name, f"Unsupported file type ({ext or 'unknown'})"))
            continue

        try:
            with zf.open(info) as fp:
                payload = fp.read()
        except Exception as exc:  # noqa: BLE001
            skipped.append((name, f"Could not read entry: {exc}"))
            continue

        if not payload:
            skipped.append((name, "Empty file"))
            continue
        if len(payload) > MAX_CV_BYTES:
            skipped.append((name, f"File too large ({len(payload)} bytes)"))
            continue

        try:
            meta = store_cv_bytes(payload, base, None)
        except CvUploadError as exc:
            skipped.append((name, str(exc)))
            continue

        files.append(meta)

    return BulkExtractResult(files=files, skipped=skipped)

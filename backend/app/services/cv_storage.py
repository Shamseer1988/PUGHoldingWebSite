"""CV file storage helpers (Phase 10).

Mirrors the image upload pattern from Phase B8.5: validates MIME type
and size, computes a SHA-256 hash, stores the file under
``<upload_dir>/cvs/<hash_prefix>.<ext>``, and returns a public URL.

Single-file uploads return one CvFileMetadata. Bulk ZIP uploads iterate
inner files of supported types and return a list of metadata + skip
records for unsupported entries.
"""
from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import List, Tuple

from app.core.config import get_settings


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


@dataclass(slots=True)
class CvFileMetadata:
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


def store_cv_bytes(
    data: bytes,
    original_name: str,
    mime_type: str | None,
) -> CvFileMetadata:
    """Persist a single CV file and return its metadata.

    Identical content is deduplicated naturally — the SHA-256 prefix
    becomes the filename so re-uploads collapse to the same object.
    """
    if not data:
        raise CvUploadError("Empty upload")
    if len(data) > MAX_CV_BYTES:
        raise CvUploadError(
            f"CV is too large ({len(data)} bytes). Max {MAX_CV_BYTES}."
        )

    ext = _resolve_ext(mime_type, original_name)

    file_hash = hashlib.sha256(data).hexdigest()
    filename = f"{file_hash[:16]}.{ext}"

    settings = get_settings()
    base = Path(settings.upload_dir) / "cvs"
    base.mkdir(parents=True, exist_ok=True)
    target = base / filename
    if not target.exists():
        target.write_bytes(data)

    return CvFileMetadata(
        url=f"/api/v1/uploads/cvs/{filename}",
        filename=filename,
        original_name=original_name,
        size=len(data),
        mime_type=mime_type or "",
        file_hash=file_hash,
        extension=ext,
    )


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

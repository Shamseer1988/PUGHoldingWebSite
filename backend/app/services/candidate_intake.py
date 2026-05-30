"""Candidate intake service (Phase 10 + Phase 11 parsing).

Owns the rules that turn a raw CV submission (public form or HR upload)
into a Candidate + CandidateDocument + CandidateJobApplication, with
duplicate detection.

Duplicate rules (Phase 10):
1. **File hash match** — if an existing document has the same SHA-256
   content as the incoming file, link to that document's candidate.
2. **Email match** — case-insensitive equality on the email column.
3. **Mobile match** — exact match on the normalized digits-only form
   of the mobile number.

If any of the above matches, we **reuse** the existing candidate
(updating fields that the new submission provides) and add the new
CV as an additional document. A new application row is created for
the requested job opening; if an application for the same job already
exists, the duplicate is rejected.

Phase 11: after the document row is persisted we run the CV parser on
the file bytes, persist a ``CandidateExtractedData`` row, and merge the
extracted fields into the Candidate (without overwriting anything the
HR user already entered).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.hr_ats import (
    SOURCE_BULK_UPLOAD,
    SOURCE_MANUAL_UPLOAD,
    SOURCE_PUBLIC_FORM,
    STATUS_CV_RECEIVED,
    Candidate,
    CandidateDocument,
    CandidateExtractedData,
    CandidateJobApplication,
    JobOpening,
)
from app.services.cv_parser import CvParseError, ParsedCv, parse_cv
from app.services.cv_storage import CvFileMetadata
from app.services.candidate_scoring import compute_score, upsert_score


logger = logging.getLogger(__name__)


VALID_SOURCES = {SOURCE_PUBLIC_FORM, SOURCE_MANUAL_UPLOAD, SOURCE_BULK_UPLOAD}


class DuplicateApplicationError(Exception):
    """Raised when the same candidate already applied to the same job."""

    def __init__(self, candidate_id: int, application_id: int) -> None:
        super().__init__("Duplicate application for this job opening")
        self.candidate_id = candidate_id
        self.application_id = application_id


@dataclass(slots=True)
class IntakeForm:
    """Form payload normalised across public + HR + bulk surfaces."""

    full_name: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    nationality: Optional[str] = None
    current_location: Optional[str] = None
    current_designation: Optional[str] = None
    total_experience_years: Optional[float] = None
    expected_salary: Optional[int] = None
    notice_period: Optional[str] = None
    visa_status: Optional[str] = None
    cover_letter: Optional[str] = None
    job_slug: Optional[str] = None
    source: str = SOURCE_PUBLIC_FORM


@dataclass(slots=True)
class IntakeResult:
    candidate: Candidate
    document: CandidateDocument
    application: CandidateJobApplication
    was_existing_candidate: bool


# ---------------------------------------------------------------------------
# Normalisers + finders
# ---------------------------------------------------------------------------


def normalize_mobile(mobile: Optional[str]) -> Optional[str]:
    """Reduce to digits only (drops spaces, dashes, plus signs)."""
    if not mobile:
        return None
    digits = "".join(c for c in mobile if c.isdigit())
    return digits or None


def normalize_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    return email.strip().lower() or None


def find_existing_candidate(
    db: Session,
    *,
    file_hash: Optional[str],
    email: Optional[str],
    mobile: Optional[str],
) -> Optional[Candidate]:
    # 1. File-hash match (find via existing document)
    if file_hash:
        existing_doc = (
            db.execute(
                select(CandidateDocument).where(
                    CandidateDocument.file_hash == file_hash
                )
            )
            .scalars()
            .first()
        )
        if existing_doc is not None and existing_doc.candidate is not None:
            return existing_doc.candidate

    # 2. Email match (case-insensitive)
    if email:
        existing = (
            db.execute(
                select(Candidate).where(
                    func.lower(Candidate.email) == email.lower(),
                    Candidate.is_archived.is_(False),
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            return existing

    # 3. Mobile match (digits only, in-Python compare)
    if mobile:
        normalized = normalize_mobile(mobile)
        if normalized:
            rows = (
                db.execute(
                    select(Candidate).where(
                        Candidate.mobile.is_not(None),
                        Candidate.is_archived.is_(False),
                    )
                )
                .scalars()
                .all()
            )
            for c in rows:
                if normalize_mobile(c.mobile) == normalized:
                    return c

    return None


# ---------------------------------------------------------------------------
# Main intake
# ---------------------------------------------------------------------------


def ingest_candidate_application(
    db: Session,
    *,
    form: IntakeForm,
    file_meta: CvFileMetadata,
    uploaded_by_id: Optional[int] = None,
    created_by_id: Optional[int] = None,
) -> IntakeResult:
    """Persist a new candidate / document / application atomically.

    Caller is responsible for committing the session (so audit-log
    helpers can attach their entries to the same transaction).
    """
    if form.source not in VALID_SOURCES:
        raise ValueError(f"Invalid intake source: {form.source}")

    email = normalize_email(form.email)
    mobile = form.mobile.strip() if form.mobile else None

    existing = find_existing_candidate(
        db, file_hash=file_meta.file_hash, email=email, mobile=mobile
    )
    was_existing = existing is not None

    if existing is None:
        candidate = Candidate(
            full_name=form.full_name.strip(),
            email=email,
            mobile=mobile,
            nationality=form.nationality,
            current_location=form.current_location,
            current_designation=form.current_designation,
            total_experience_years=form.total_experience_years,
            expected_salary=form.expected_salary,
            notice_period=form.notice_period,
            visa_status=form.visa_status,
            source=form.source,
            created_by_id=created_by_id,
        )
        db.add(candidate)
        db.flush()
    else:
        candidate = existing
        # Fill in fields the existing candidate is missing — don't
        # overwrite data we already have.
        _merge(candidate, "full_name", form.full_name.strip())
        _merge(candidate, "email", email)
        _merge(candidate, "mobile", mobile)
        _merge(candidate, "nationality", form.nationality)
        _merge(candidate, "current_location", form.current_location)
        _merge(candidate, "current_designation", form.current_designation)
        _merge(candidate, "total_experience_years", form.total_experience_years)
        _merge(candidate, "expected_salary", form.expected_salary)
        _merge(candidate, "notice_period", form.notice_period)
        _merge(candidate, "visa_status", form.visa_status)

    # Resolve the job opening (if any) and ensure no duplicate application.
    job: Optional[JobOpening] = None
    if form.job_slug:
        job = (
            db.execute(select(JobOpening).where(JobOpening.slug == form.job_slug))
            .scalars()
            .first()
        )

    if job is not None:
        existing_app = (
            db.execute(
                select(CandidateJobApplication).where(
                    CandidateJobApplication.candidate_id == candidate.id,
                    CandidateJobApplication.job_opening_id == job.id,
                )
            )
            .scalars()
            .first()
        )
        if existing_app is not None:
            raise DuplicateApplicationError(
                candidate_id=candidate.id, application_id=existing_app.id
            )

    application = CandidateJobApplication(
        candidate_id=candidate.id,
        job_opening_id=job.id if job is not None else None,
        status=STATUS_CV_RECEIVED,
        source=form.source,
        cover_letter=form.cover_letter,
    )
    db.add(application)

    # Attach the new CV document. Reuse the existing row if the same
    # file hash already exists for this candidate.
    existing_doc = next(
        (d for d in candidate.documents if d.file_hash == file_meta.file_hash),
        None,
    )
    is_new_document = existing_doc is None
    if existing_doc is not None:
        document = existing_doc
    else:
        # When attaching a new primary document, demote previous primaries.
        for d in candidate.documents:
            d.is_primary = False
        document = CandidateDocument(
            candidate_id=candidate.id,
            filename=file_meta.filename,
            file_path=file_meta.url,
            mime_type=file_meta.mime_type,
            file_size=file_meta.size,
            file_hash=file_meta.file_hash,
            is_primary=True,
            uploaded_by_id=uploaded_by_id,
        )
        db.add(document)

    db.flush()

    # Phase 11 — parse the freshly stored CV and merge structured data
    # into the candidate. Failures are non-fatal: HR can still see and
    # edit the candidate manually.
    if is_new_document:
        try:
            parsed = _parse_document(file_meta)
        except CvParseError as exc:
            logger.warning("CV parse failed for %s: %s", file_meta.filename, exc)
            parsed = None
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected CV parse error for %s: %s", file_meta.filename, exc)
            parsed = None
        if parsed is not None:
            _persist_extracted_data(db, candidate, parsed)
            _merge_parsed_into_candidate(candidate, parsed)
            db.flush()

    # Phase 12 — compute the rule-based score for this application.
    if job is not None:
        try:
            result = compute_score(candidate=candidate, job=job)
            upsert_score(db, application=application, result=result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Candidate scoring failed: %s", exc)

    return IntakeResult(
        candidate=candidate,
        document=document,
        application=application,
        was_existing_candidate=was_existing,
    )


def _merge(candidate: Candidate, attr: str, new_value) -> None:
    """Fill an attribute on the candidate only if it's currently empty."""
    current = getattr(candidate, attr)
    if (current is None or current == "") and new_value not in (None, ""):
        setattr(candidate, attr, new_value)


# ---------------------------------------------------------------------------
# Phase 11 — CV parsing helpers
# ---------------------------------------------------------------------------


def _parse_document(file_meta: CvFileMetadata) -> Optional[ParsedCv]:
    """Fetch the CV bytes from storage and run the parser.

    The parser (pdfminer / python-docx / pytesseract) needs a real
    filesystem path, so :func:`stage_cv_locally` materialises the
    R2 (or local) bytes into a temp file that's cleaned up on exit.
    Missing objects log + return None — the caller treats it as a
    soft "no data" rather than an error.
    """
    from app.services.cv_storage import stage_cv_locally

    try:
        with stage_cv_locally(file_meta.url) as path:
            return parse_cv(path, extension=file_meta.extension)
    except FileNotFoundError:
        logger.warning("CV missing from storage: %s", file_meta.url)
        return None


def _persist_extracted_data(
    db: Session, candidate: Candidate, parsed: ParsedCv
) -> CandidateExtractedData:
    row = candidate.extracted_data
    if row is None:
        row = CandidateExtractedData(candidate_id=candidate.id)
        db.add(row)
    row.skills = ", ".join(parsed.skills) if parsed.skills else None
    row.education = parsed.education_as_json() or None
    row.certifications = parsed.certifications or None
    row.languages = parsed.languages or None
    row.previous_companies = parsed.companies_as_json() or None
    row.full_text = parsed.full_text or None
    row.parser_version = parsed.parser_version
    candidate.extracted_data = row
    return row


def _merge_parsed_into_candidate(candidate: Candidate, parsed: ParsedCv) -> None:
    """Fill empty Candidate columns with values discovered in the CV."""
    if parsed.name:
        _merge_if_unknown(candidate, "full_name", parsed.name)
    _merge(candidate, "email", _normalize_email_value(parsed.email))
    _merge(candidate, "mobile", parsed.mobile)
    _merge(candidate, "nationality", parsed.nationality)
    _merge(candidate, "current_location", parsed.current_location)
    _merge(candidate, "current_designation", parsed.current_designation)
    _merge(candidate, "current_company", parsed.current_company)
    _merge(candidate, "total_experience_years", parsed.total_experience_years)
    _merge(candidate, "gcc_experience_years", parsed.gcc_experience_years)
    _merge(candidate, "qatar_experience_years", parsed.qatar_experience_years)
    _merge(candidate, "expected_salary", parsed.expected_salary)
    _merge(candidate, "notice_period", parsed.notice_period)
    _merge(candidate, "visa_status", parsed.visa_status)


def _normalize_email_value(email: Optional[str]) -> Optional[str]:
    return normalize_email(email)


# Names: bulk upload starts everyone as "Unknown" or the file stem
# ("ahmed_resume" → "ahmed resume"). When the parser finds a better
# candidate, replace that placeholder.
_PLACEHOLDER_NAMES = {"unknown", "candidate", "cv", "resume"}


def _merge_if_unknown(candidate: Candidate, attr: str, new_value) -> None:
    current = getattr(candidate, attr)
    if not new_value:
        return
    if current is None or current == "":
        setattr(candidate, attr, new_value)
        return
    # Treat very short or placeholder names from bulk upload as overrideable.
    if attr == "full_name":
        normalised = current.strip().lower()
        if normalised in _PLACEHOLDER_NAMES or len(normalised) <= 2:
            setattr(candidate, attr, new_value)


def reparse_candidate_cv(db: Session, candidate: Candidate) -> Optional[ParsedCv]:
    """Re-run the parser on the candidate's current primary document.

    Returns ``None`` if there's no document to parse or extraction
    fails. Caller is responsible for committing the session.
    """
    primary = next((d for d in candidate.documents if d.is_primary), None) or (
        candidate.documents[0] if candidate.documents else None
    )
    if primary is None:
        return None

    file_meta = CvFileMetadata(
        url=primary.file_path,
        filename=primary.filename,
        original_name=primary.filename,
        size=primary.file_size or 0,
        mime_type=primary.mime_type or "",
        file_hash=primary.file_hash or "",
        extension=Path(primary.filename).suffix.lstrip(".").lower(),
    )
    try:
        parsed = _parse_document(file_meta)
    except CvParseError as exc:
        logger.warning("CV reparse failed for candidate %s: %s", candidate.id, exc)
        return None
    if parsed is None:
        return None
    _persist_extracted_data(db, candidate, parsed)
    _merge_parsed_into_candidate(candidate, parsed)
    db.flush()
    return parsed

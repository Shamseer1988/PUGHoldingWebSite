"""Candidate intake service (Phase 10).

Owns the rules that turn a raw CV submission (public form or HR upload)
into a Candidate + CandidateDocument + CandidateJobApplication, with
duplicate detection.

Duplicate rules (Phase 10):
1. **File hash match** — if an existing document has the same SHA-256
   content as the incoming file, link to that document's candidate.
2. **Email match** — case-insensitive equality on the email column.
3. **Mobile match** — exact match on the normalized digits-only form
   of the mobile number.
4. (Phase 11+) Similar-name fuzzy matching can be layered on later.

If any of the above matches, we **reuse** the existing candidate
(updating fields that the new submission provides) and add the new
CV as an additional document. A new application row is created for
the requested job opening; if an application for the same job already
exists, the duplicate is rejected.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.hr_ats import (
    SOURCE_BULK_UPLOAD,
    SOURCE_MANUAL_UPLOAD,
    SOURCE_PUBLIC_FORM,
    STATUS_CV_RECEIVED,
    Candidate,
    CandidateDocument,
    CandidateJobApplication,
    JobOpening,
)
from app.services.cv_storage import CvFileMetadata


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

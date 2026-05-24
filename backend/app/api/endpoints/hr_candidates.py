"""HR ATS candidate endpoints (Phase 10 + Phase 11 parsing).

- POST  /hr/candidates/upload                   single-CV manual upload by HR
- POST  /hr/candidates/bulk-upload              ZIP containing many CVs
- GET   /hr/candidates                          list with simple filters
- GET   /hr/candidates/{id}                     single candidate
- PATCH /hr/candidates/{id}                     HR manual edit of candidate fields
- GET   /hr/candidates/{id}/extracted-data      structured CV data
- PATCH /hr/candidates/{id}/extracted-data      HR manual edit of extracted fields
- POST  /hr/candidates/{id}/parse-cv            re-run the parser on the primary CV
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context, require_hr_admin
from app.core.database import get_db
from app.models.auth import User
from app.models.hr_ats import (
    SOURCE_BULK_UPLOAD,
    SOURCE_MANUAL_UPLOAD,
    Candidate,
    CandidateExtractedData,
    CandidateJobApplication,
    JobOpening,
)
from app.schemas.hr_ats import (
    ApplicationSubmissionResponse,
    BulkUploadResult,
    BulkUploadSkip,
    CandidateExtractedDataRead,
    CandidateExtractedDataUpdate,
    CandidateListItem,
    CandidateRead,
    CandidateUpdate,
    CvReparseResult,
)
from app.services.audit_log import record_audit
from app.services.candidate_intake import (
    DuplicateApplicationError,
    IntakeForm,
    ingest_candidate_application,
    reparse_candidate_cv,
)
from app.services.cv_storage import (
    CvUploadError,
    extract_cvs_from_zip,
    store_cv_bytes,
)


router = APIRouter(
    prefix="/hr/candidates",
    tags=["HR ATS - Candidates"],
    dependencies=[Depends(require_hr_admin)],
)


# ---------------------------------------------------------------------------
# List + detail
# ---------------------------------------------------------------------------


@router.get("", response_model=List[CandidateListItem])
def list_candidates(
    db: Session = Depends(get_db),
    include_archived: bool = Query(default=False),
    q: Optional[str] = Query(default=None, max_length=200),
) -> List[Candidate]:
    stmt = select(Candidate).order_by(desc(Candidate.created_at), desc(Candidate.id))
    if not include_archived:
        stmt = stmt.where(Candidate.is_archived.is_(False))
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            (func.lower(Candidate.full_name).like(like))
            | (func.lower(Candidate.email).like(like))
            | (Candidate.mobile.like(f"%{q}%"))
        )
    return db.execute(stmt).scalars().all()


@router.get("/{candidate_id}", response_model=CandidateRead)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


# ---------------------------------------------------------------------------
# Single CV upload
# ---------------------------------------------------------------------------


@router.post(
    "/upload",
    response_model=ApplicationSubmissionResponse,
    status_code=201,
)
async def upload_candidate(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
    file: UploadFile = File(...),
    full_name: str = Form(..., min_length=1, max_length=255),
    email: Optional[str] = Form(default=None, max_length=255),
    mobile: Optional[str] = Form(default=None, max_length=40),
    nationality: Optional[str] = Form(default=None, max_length=120),
    current_location: Optional[str] = Form(default=None, max_length=255),
    current_designation: Optional[str] = Form(default=None, max_length=255),
    total_experience_years: Optional[float] = Form(default=None, ge=0, le=70),
    expected_salary: Optional[int] = Form(default=None, ge=0),
    notice_period: Optional[str] = Form(default=None, max_length=120),
    visa_status: Optional[str] = Form(default=None, max_length=120),
    job_slug: Optional[str] = Form(default=None, max_length=200),
) -> ApplicationSubmissionResponse:
    payload = await file.read()
    try:
        meta = store_cv_bytes(payload, file.filename or "cv", file.content_type)
    except CvUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    form = IntakeForm(
        full_name=full_name,
        email=email,
        mobile=mobile,
        nationality=nationality,
        current_location=current_location,
        current_designation=current_designation,
        total_experience_years=total_experience_years,
        expected_salary=expected_salary,
        notice_period=notice_period,
        visa_status=visa_status,
        job_slug=job_slug,
        source=SOURCE_MANUAL_UPLOAD,
    )

    try:
        result = ingest_candidate_application(
            db,
            form=form,
            file_meta=meta,
            uploaded_by_id=user.id,
            created_by_id=user.id,
        )
    except DuplicateApplicationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "This candidate has already applied to that job. "
                "Open their profile to track the existing application."
            ),
        ) from exc

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.candidate.manual_upload",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="candidate",
        target_id=str(result.candidate.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "application_id": result.application.id,
            "job_slug": job_slug,
            "was_existing_candidate": result.was_existing_candidate,
            "file_hash": meta.file_hash,
        },
        commit=False,
    )
    db.commit()

    return ApplicationSubmissionResponse(
        candidate_id=result.candidate.id,
        application_id=result.application.id,
        was_existing_candidate=result.was_existing_candidate,
        job_title=(
            result.application.job_opening.title
            if result.application.job_opening is not None
            else None
        ),
        job_slug=(
            result.application.job_opening.slug
            if result.application.job_opening is not None
            else None
        ),
    )


# ---------------------------------------------------------------------------
# Bulk ZIP upload
# ---------------------------------------------------------------------------


@router.post(
    "/bulk-upload",
    response_model=BulkUploadResult,
    status_code=201,
)
async def bulk_upload_candidates(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
    file: UploadFile = File(..., description="ZIP archive of CV files"),
    job_slug: Optional[str] = Form(default=None, max_length=200),
) -> BulkUploadResult:
    """Extract every supported CV from a ZIP and create candidates.

    Phase 10 creates placeholder candidates named after the file stem.
    Phase 11's CV parser will backfill actual extracted_data (name,
    email, mobile, skills, etc.) for each one.
    """
    payload = await file.read()
    try:
        bundle = extract_cvs_from_zip(payload)
    except CvUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    skipped = [BulkUploadSkip(name=n, reason=r) for n, r in bundle.skipped]
    created_count = 0
    matched_count = 0
    duplicate_app_count = 0
    candidate_ids: List[int] = []

    for meta in bundle.files:
        # Placeholder name = filename without extension, prettified a bit.
        stem = meta.original_name.rsplit(".", 1)[0].strip()
        full_name = stem.replace("_", " ").replace("-", " ").strip() or "Unknown"

        form = IntakeForm(
            full_name=full_name,
            email=None,
            mobile=None,
            job_slug=job_slug,
            source=SOURCE_BULK_UPLOAD,
        )

        try:
            result = ingest_candidate_application(
                db,
                form=form,
                file_meta=meta,
                uploaded_by_id=user.id,
                created_by_id=user.id,
            )
        except DuplicateApplicationError:
            db.rollback()
            duplicate_app_count += 1
            skipped.append(
                BulkUploadSkip(
                    name=meta.original_name,
                    reason="Duplicate application for this job (skipped)",
                )
            )
            continue

        if result.was_existing_candidate:
            matched_count += 1
        else:
            created_count += 1
        candidate_ids.append(result.candidate.id)

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.candidate.bulk_upload",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="candidate_bulk",
        target_id=None,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "total_files": len(bundle.files) + len(bundle.skipped),
            "created_candidates": created_count,
            "matched_existing_candidates": matched_count,
            "duplicate_applications_skipped": duplicate_app_count,
            "skipped_count": len(skipped),
            "job_slug": job_slug,
        },
        commit=False,
    )
    db.commit()

    return BulkUploadResult(
        total_files=len(bundle.files) + len(bundle.skipped),
        created_candidates=created_count,
        matched_existing_candidates=matched_count,
        duplicate_applications_skipped=duplicate_app_count,
        skipped_files=skipped,
        candidate_ids=candidate_ids,
    )


# ---------------------------------------------------------------------------
# Phase 11 — Manual edits + CV parser
# ---------------------------------------------------------------------------


def _get_candidate_or_404(db: Session, candidate_id: int) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidate


@router.patch("/{candidate_id}", response_model=CandidateRead)
def update_candidate(
    candidate_id: int,
    payload: CandidateUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> Candidate:
    candidate = _get_candidate_or_404(db, candidate_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return candidate

    changed: list[str] = []
    for field_name, value in updates.items():
        if isinstance(value, str):
            value = value.strip() or None
        if getattr(candidate, field_name) != value:
            setattr(candidate, field_name, value)
            changed.append(field_name)

    if changed:
        ctx = get_request_context(request)
        record_audit(
            db,
            action="hr.candidate.update",
            actor_id=user.id,
            actor_email=user.email,
            scope="hr",
            target_type="candidate",
            target_id=str(candidate.id),
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
            details={"fields": changed},
            commit=False,
        )
    db.commit()
    db.refresh(candidate)
    return candidate


@router.get(
    "/{candidate_id}/extracted-data",
    response_model=CandidateExtractedDataRead,
)
def get_extracted_data(
    candidate_id: int, db: Session = Depends(get_db)
) -> CandidateExtractedData:
    candidate = _get_candidate_or_404(db, candidate_id)
    data = candidate.extracted_data
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No extracted data for this candidate yet. Re-run the CV "
                "parser from the candidate profile to populate it."
            ),
        )
    return data


@router.patch(
    "/{candidate_id}/extracted-data",
    response_model=CandidateExtractedDataRead,
)
def update_extracted_data(
    candidate_id: int,
    payload: CandidateExtractedDataUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> CandidateExtractedData:
    candidate = _get_candidate_or_404(db, candidate_id)
    data = candidate.extracted_data
    if data is None:
        data = CandidateExtractedData(candidate_id=candidate.id)
        db.add(data)

    updates = payload.model_dump(exclude_unset=True)
    changed: list[str] = []
    for field_name, value in updates.items():
        if isinstance(value, str):
            value = value.strip() or None
        if getattr(data, field_name) != value:
            setattr(data, field_name, value)
            changed.append(field_name)

    if changed:
        ctx = get_request_context(request)
        record_audit(
            db,
            action="hr.candidate.extracted_data.update",
            actor_id=user.id,
            actor_email=user.email,
            scope="hr",
            target_type="candidate_extracted_data",
            target_id=str(candidate.id),
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
            details={"fields": changed},
            commit=False,
        )
    db.commit()
    db.refresh(data)
    return data


@router.post("/{candidate_id}/parse-cv", response_model=CvReparseResult)
def reparse_candidate_cv_endpoint(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> CvReparseResult:
    """Re-run the CV parser on the candidate's primary document.

    Existing manual edits to the Candidate row are preserved — the
    parser only fills fields that are currently empty.
    """
    candidate = _get_candidate_or_404(db, candidate_id)
    if not candidate.documents:
        raise HTTPException(
            status_code=400,
            detail="Candidate has no uploaded CV to parse.",
        )

    parsed = reparse_candidate_cv(db, candidate)
    if parsed is None:
        db.rollback()
        return CvReparseResult(
            candidate=CandidateRead.model_validate(candidate),
            parsed=False,
            detail=(
                "CV could not be parsed. Confirm the file is a valid PDF, "
                "DOCX, or image; legacy .doc files must be re-saved as DOCX."
            ),
        )

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.candidate.cv_parse",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="candidate",
        target_id=str(candidate.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"parser_version": parsed.parser_version},
        commit=False,
    )
    db.commit()
    db.refresh(candidate)
    return CvReparseResult(
        candidate=CandidateRead.model_validate(candidate),
        parsed=True,
        parser_version=parsed.parser_version,
    )

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

from datetime import datetime, timezone
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
from sqlalchemy.orm import Session, object_session

from app.auth.dependencies import get_request_context, require_hr_admin
from app.core.database import get_db
from app.models.auth import User
from app.models.hr_ats import (
    SOURCE_BULK_UPLOAD,
    SOURCE_MANUAL_UPLOAD,
    AISetting,
    Candidate,
    CandidateExtractedData,
    CandidateJobApplication,
    CandidateScore,
    JobOpening,
)
from app.schemas.hr_ats import (
    AIReviewGenerateResult,
    ApplicationSubmissionResponse,
    BulkUploadResult,
    BulkUploadSkip,
    CandidateAIReviewPreview,
    CandidateAIReviewRead,
    CandidateApplicationSummary,
    CandidateDocumentRead,
    CandidateExtractedDataRead,
    CandidateExtractedDataUpdate,
    CandidateListItem,
    CandidateRead,
    CandidateScoreBreakdownRead,
    CandidateScoreOverride,
    CandidateScoreRead,
    CandidateStatusChange,
    CandidateStatusHistoryRead,
    CandidateUpdate,
    CvReparseResult,
    InterviewSummaryForApplication,
    StatusOption,
    StatusPipelineMeta,
)
from app.services.interview_management import (
    INTERVIEW_MODE_LABELS,
    INTERVIEW_STATUS_LABELS,
)
from app.services.candidate_workflow import (
    InvalidTransitionError,
    MissingReasonError,
    PermissionDeniedError,
    ALLOWED_TRANSITIONS,
    FINAL_STATUSES,
    PIPELINE_ORDER,
    STATUS_LABELS,
    allowed_next_statuses,
    change_status,
)
from app.ai.candidate_review import (
    AIConfigError,
    AIDisabledError,
    AIProviderError,
    generate_review,
    persist_review,
    resolve_config,
)
from app.services.audit_log import record_audit
from app.services.candidate_intake import (
    DuplicateApplicationError,
    IntakeForm,
    ingest_candidate_application,
    reparse_candidate_cv,
)
from app.services.candidate_search import CandidateFilters, search_candidates
from app.services.candidate_scoring import (
    TOTAL_MAX,
    apply_manual_override,
    clear_manual_override,
    compute_score,
    upsert_score,
)
from app.services.cv_storage import (
    CvUploadError,
    extract_cvs_from_zip,
    store_cv_bytes,
)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def _serialize_application(
    app: CandidateJobApplication,
    *,
    actor: Optional[User] = None,
    interviewer_lookup: Optional[dict[int, User]] = None,
) -> CandidateApplicationSummary:
    score = (
        CandidateScoreRead.model_validate(app.score) if app.score is not None else None
    )
    if score is not None and app.score is not None and app.score.breakdown is not None:
        score.breakdown = CandidateScoreBreakdownRead.model_validate(app.score.breakdown)
    ai_preview = (
        CandidateAIReviewPreview.model_validate(app.ai_review)
        if app.ai_review is not None
        else None
    )
    is_superuser = bool(actor and actor.is_superuser)
    next_statuses = sorted(
        allowed_next_statuses(app.status, actor_is_superuser=is_superuser)
    )

    interviewer_lookup = interviewer_lookup or {}
    interview_rows: List[InterviewSummaryForApplication] = []
    next_interview_at: Optional[object] = None
    now = datetime.now(timezone.utc)
    for iv in app.interviews:
        interviewer = interviewer_lookup.get(iv.interviewer_id) if iv.interviewer_id else None
        interview_rows.append(
            InterviewSummaryForApplication(
                id=iv.id,
                round_name=iv.round_name,
                round_number=iv.round_number,
                scheduled_at=iv.scheduled_at,
                duration_minutes=iv.duration_minutes,
                mode=iv.mode,
                mode_label=INTERVIEW_MODE_LABELS.get(iv.mode, iv.mode),
                location_or_link=iv.location_or_link,
                status=iv.status,
                status_label=INTERVIEW_STATUS_LABELS.get(iv.status, iv.status),
                interviewer_id=iv.interviewer_id,
                interviewer_email=interviewer.email if interviewer else None,
                interviewer_name=interviewer.full_name if interviewer else None,
                has_feedback=bool(iv.feedback),
                latest_recommendation=(
                    iv.feedback[0].recommendation if iv.feedback else None
                ),
            )
        )
        if iv.status == "scheduled":
            scheduled_at_aware = (
                iv.scheduled_at
                if iv.scheduled_at.tzinfo is not None
                else iv.scheduled_at.replace(tzinfo=timezone.utc)
            )
            if scheduled_at_aware >= now and (
                next_interview_at is None or scheduled_at_aware < next_interview_at
            ):
                next_interview_at = scheduled_at_aware

    return CandidateApplicationSummary(
        id=app.id,
        status=app.status,
        status_label=STATUS_LABELS.get(app.status, app.status),
        job_opening_id=app.job_opening_id,
        job_title=app.job_opening.title if app.job_opening is not None else None,
        applied_at=app.applied_at,
        source=app.source,
        last_rejection_reason=app.last_rejection_reason,
        score=score,
        ai_review=ai_preview,
        history_count=len(app.status_history) if app.status_history is not None else 0,
        allowed_next_statuses=next_statuses,
        interviews=interview_rows,
        interview_count=len(interview_rows),
        next_interview_at=next_interview_at,
    )


def _serialize_candidate(
    candidate: Candidate, *, actor: Optional[User] = None
) -> CandidateRead:
    interviewer_ids = {
        iv.interviewer_id
        for app in candidate.applications
        for iv in app.interviews
        if iv.interviewer_id
    }
    interviewer_lookup: dict[int, User] = {}
    if interviewer_ids:
        rows = (
            object_session(candidate)
            .execute(select(User).where(User.id.in_(interviewer_ids)))
            .scalars()
            .all()
        )
        interviewer_lookup = {u.id: u for u in rows}

    applications = [
        _serialize_application(a, actor=actor, interviewer_lookup=interviewer_lookup)
        for a in candidate.applications
    ]
    scores = [a.score.total for a in candidate.applications if a.score is not None]
    return CandidateRead(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        mobile=candidate.mobile,
        nationality=candidate.nationality,
        current_location=candidate.current_location,
        current_designation=candidate.current_designation,
        current_company=candidate.current_company,
        total_experience_years=candidate.total_experience_years,
        gcc_experience_years=candidate.gcc_experience_years,
        qatar_experience_years=candidate.qatar_experience_years,
        expected_salary=candidate.expected_salary,
        notice_period=candidate.notice_period,
        visa_status=candidate.visa_status,
        availability=candidate.availability,
        is_blacklisted=candidate.is_blacklisted,
        is_archived=candidate.is_archived,
        source=candidate.source,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
        documents=[CandidateDocumentRead.model_validate(d) for d in candidate.documents],
        extracted_data=(
            CandidateExtractedDataRead.model_validate(candidate.extracted_data)
            if candidate.extracted_data is not None
            else None
        ),
        applications=applications,
        top_score=max(scores) if scores else None,
    )


def _serialize_list_item(
    candidate: Candidate,
    top_score: Optional[int],
    latest_status: Optional[str] = None,
) -> CandidateListItem:
    return CandidateListItem(
        id=candidate.id,
        full_name=candidate.full_name,
        email=candidate.email,
        mobile=candidate.mobile,
        current_designation=candidate.current_designation,
        total_experience_years=candidate.total_experience_years,
        source=candidate.source,
        is_blacklisted=candidate.is_blacklisted,
        is_archived=candidate.is_archived,
        created_at=candidate.created_at,
        top_score=top_score,
        latest_status=latest_status,
        latest_status_label=STATUS_LABELS.get(latest_status) if latest_status else None,
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
    nationality: Optional[str] = Query(default=None, max_length=120),
    location: Optional[str] = Query(default=None, max_length=255),
    experience_min: Optional[float] = Query(default=None, ge=0, le=70),
    experience_max: Optional[float] = Query(default=None, ge=0, le=70),
    salary_min: Optional[int] = Query(default=None, ge=0),
    salary_max: Optional[int] = Query(default=None, ge=0),
    visa: Optional[str] = Query(default=None, max_length=120),
    notice_period: Optional[str] = Query(default=None, max_length=120),
    education: Optional[str] = Query(default=None, max_length=120),
    language: Optional[str] = Query(default=None, max_length=80),
    skill: Optional[str] = Query(default=None, max_length=120),
    job_slug: Optional[str] = Query(default=None, max_length=200),
    department: Optional[str] = Query(default=None, max_length=120),
    status: Optional[str] = Query(default=None, max_length=40),
    score_min: Optional[int] = Query(default=None, ge=0, le=100),
    score_max: Optional[int] = Query(default=None, ge=0, le=100),
    uploaded_from: Optional[datetime] = Query(default=None),
    uploaded_to: Optional[datetime] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> List[CandidateListItem]:
    """Advanced server-side search.

    Accepts every Phase-16 filter; falls back to the previous behaviour
    when no extra params are supplied (only `q` + `include_archived`).
    """
    filters = CandidateFilters(
        q=q,
        include_archived=include_archived,
        nationality=nationality,
        location=location,
        experience_min=experience_min,
        experience_max=experience_max,
        salary_min=salary_min,
        salary_max=salary_max,
        visa=visa,
        notice_period=notice_period,
        education=education,
        language=language,
        skill=skill,
        job_slug=job_slug,
        department=department,
        status=status,
        score_min=score_min,
        score_max=score_max,
        uploaded_from=uploaded_from,
        uploaded_to=uploaded_to,
        limit=limit,
    )
    rows = search_candidates(db, filters)
    return [
        _serialize_list_item(r.candidate, r.top_score, r.latest_status)
        for r in rows
    ]


@router.get("/{candidate_id}", response_model=CandidateRead)
def get_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> CandidateRead:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return _serialize_candidate(candidate, actor=user)


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
) -> CandidateRead:
    candidate = _get_candidate_or_404(db, candidate_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return _serialize_candidate(candidate, actor=user)

    changed: list[str] = []
    for field_name, value in updates.items():
        if isinstance(value, str):
            value = value.strip() or None
        if getattr(candidate, field_name) != value:
            setattr(candidate, field_name, value)
            changed.append(field_name)

    # Phase 12: when scoring inputs change, re-run the engine on each
    # application that has an open job opening (manual overrides are
    # preserved by upsert_score).
    if changed and _changes_affect_score(changed):
        for app in candidate.applications:
            if app.job_opening is None:
                continue
            try:
                result = compute_score(candidate=candidate, job=app.job_opening)
                upsert_score(db, application=app, result=result)
            except Exception:  # noqa: BLE001
                pass

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
    return _serialize_candidate(candidate, actor=user)


_SCORING_RELEVANT_FIELDS = {
    "nationality",
    "current_location",
    "current_designation",
    "current_company",
    "total_experience_years",
    "gcc_experience_years",
    "qatar_experience_years",
    "expected_salary",
    "notice_period",
    "visa_status",
}


def _changes_affect_score(changed: list[str]) -> bool:
    return any(field in _SCORING_RELEVANT_FIELDS for field in changed)


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
            candidate=_serialize_candidate(candidate, actor=user),
            parsed=False,
            detail=(
                "CV could not be parsed. Confirm the file is a valid PDF, "
                "DOCX, or image; legacy .doc files must be re-saved as DOCX."
            ),
        )

    # Phase 12 — re-run scoring now that the extracted data has refreshed.
    for app in candidate.applications:
        if app.job_opening is None:
            continue
        try:
            result = compute_score(candidate=candidate, job=app.job_opening)
            upsert_score(db, application=app, result=result)
        except Exception:  # noqa: BLE001
            pass

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
        candidate=_serialize_candidate(candidate, actor=user),
        parsed=True,
        parser_version=parsed.parser_version,
    )


# ---------------------------------------------------------------------------
# Phase 12 — Candidate score endpoints
# ---------------------------------------------------------------------------


def _get_application_or_404(
    db: Session, candidate_id: int, application_id: int
) -> CandidateJobApplication:
    candidate = _get_candidate_or_404(db, candidate_id)
    app = next((a for a in candidate.applications if a.id == application_id), None)
    if app is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found for this candidate.",
        )
    return app


def _serialize_score(score: CandidateScore) -> CandidateScoreRead:
    payload = CandidateScoreRead.model_validate(score)
    if score.breakdown is not None:
        payload.breakdown = CandidateScoreBreakdownRead.model_validate(score.breakdown)
    return payload


@router.get(
    "/{candidate_id}/applications/{application_id}/score",
    response_model=CandidateScoreRead,
)
def get_application_score(
    candidate_id: int,
    application_id: int,
    db: Session = Depends(get_db),
) -> CandidateScoreRead:
    app = _get_application_or_404(db, candidate_id, application_id)
    if app.score is None:
        raise HTTPException(
            status_code=404,
            detail="No score yet — run POST .../score/recompute to generate one.",
        )
    return _serialize_score(app.score)


@router.post(
    "/{candidate_id}/applications/{application_id}/score/recompute",
    response_model=CandidateScoreRead,
)
def recompute_application_score(
    candidate_id: int,
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> CandidateScoreRead:
    app = _get_application_or_404(db, candidate_id, application_id)
    if app.job_opening is None:
        raise HTTPException(
            status_code=400,
            detail="Application is not linked to a job opening — cannot score.",
        )
    result = compute_score(candidate=app.candidate, job=app.job_opening)
    # When the score is currently manually overridden, recompute still
    # refreshes the breakdown for transparency but keeps the override.
    score = upsert_score(db, application=app, result=result)

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.candidate.score.recompute",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="candidate_score",
        target_id=str(score.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "candidate_id": candidate_id,
            "application_id": application_id,
            "total": score.total,
            "computed_total": result.total,
            "kept_override": score.is_manual_override,
        },
        commit=False,
    )
    db.commit()
    db.refresh(score)
    return _serialize_score(score)


@router.post(
    "/{candidate_id}/applications/{application_id}/score/override",
    response_model=CandidateScoreRead,
)
def override_application_score(
    candidate_id: int,
    application_id: int,
    payload: CandidateScoreOverride,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> CandidateScoreRead:
    app = _get_application_or_404(db, candidate_id, application_id)
    if app.score is None:
        # Compute first so the breakdown is populated for context.
        if app.job_opening is not None:
            result = compute_score(candidate=app.candidate, job=app.job_opening)
            upsert_score(db, application=app, result=result)
            db.flush()
        else:
            # No job → still create an empty score row so we can override it.
            new = CandidateScore(application_id=app.id, total=0)
            db.add(new)
            db.flush()

    previous_total = app.score.total if app.score else 0
    try:
        apply_manual_override(
            db,
            score=app.score,
            new_total=payload.total,
            reason=payload.reason,
            overridden_by_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.candidate.score.override",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="candidate_score",
        target_id=str(app.score.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "candidate_id": candidate_id,
            "application_id": application_id,
            "previous_total": previous_total,
            "new_total": payload.total,
            "reason": payload.reason,
        },
        commit=False,
    )
    db.commit()
    db.refresh(app.score)
    return _serialize_score(app.score)


@router.delete(
    "/{candidate_id}/applications/{application_id}/score/override",
    response_model=CandidateScoreRead,
)
def clear_application_score_override(
    candidate_id: int,
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> CandidateScoreRead:
    app = _get_application_or_404(db, candidate_id, application_id)
    if app.score is None:
        raise HTTPException(status_code=404, detail="No score to clear.")
    if not app.score.is_manual_override:
        return _serialize_score(app.score)

    # Recompute fresh so we can restore the engine total.
    auto_total: Optional[int] = None
    if app.job_opening is not None:
        result = compute_score(candidate=app.candidate, job=app.job_opening)
        upsert_score(db, application=app, result=result, preserve_manual_override=True)
        auto_total = result.total

    previous_total = app.score.total
    clear_manual_override(db, score=app.score, auto_total=auto_total)

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.candidate.score.override.clear",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="candidate_score",
        target_id=str(app.score.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "candidate_id": candidate_id,
            "application_id": application_id,
            "previous_total": previous_total,
            "restored_total": app.score.total,
        },
        commit=False,
    )
    db.commit()
    db.refresh(app.score)
    return _serialize_score(app.score)


# ---------------------------------------------------------------------------
# Phase 13 — AI candidate review endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/{candidate_id}/applications/{application_id}/ai-review",
    response_model=CandidateAIReviewRead,
)
def get_application_ai_review(
    candidate_id: int,
    application_id: int,
    db: Session = Depends(get_db),
) -> CandidateAIReviewRead:
    app = _get_application_or_404(db, candidate_id, application_id)
    if app.ai_review is None:
        raise HTTPException(
            status_code=404,
            detail="No AI review yet — run POST .../ai-review to generate one.",
        )
    return CandidateAIReviewRead.model_validate(app.ai_review)


@router.post(
    "/{candidate_id}/applications/{application_id}/ai-review",
    response_model=AIReviewGenerateResult,
)
def generate_application_ai_review(
    candidate_id: int,
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> AIReviewGenerateResult:
    app = _get_application_or_404(db, candidate_id, application_id)
    setting = db.get(AISetting, 1)
    config = resolve_config(setting)

    try:
        result = generate_review(
            candidate=app.candidate,
            application=app,
            job=app.job_opening,
            config=config,
        )
    except AIDisabledError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AIConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    review = persist_review(app, result)
    db.flush()

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.candidate.ai_review.generate",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="candidate_ai_review",
        target_id=str(review.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "candidate_id": candidate_id,
            "application_id": application_id,
            "mode": config.mode,
            "model_name": result.model_name,
            "recommendation": result.recommendation,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
        },
        commit=False,
    )
    db.commit()
    db.refresh(review)
    return AIReviewGenerateResult(
        review=CandidateAIReviewRead.model_validate(review),
        mode=config.mode,
        model_name=result.model_name,
    )


@router.delete(
    "/{candidate_id}/applications/{application_id}/ai-review",
    status_code=204,
)
def delete_application_ai_review(
    candidate_id: int,
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
):
    from fastapi import Response

    app = _get_application_or_404(db, candidate_id, application_id)
    if app.ai_review is None:
        return Response(status_code=204)

    review_id = app.ai_review.id
    db.delete(app.ai_review)
    app.ai_review = None

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.candidate.ai_review.delete",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="candidate_ai_review",
        target_id=str(review_id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "candidate_id": candidate_id,
            "application_id": application_id,
        },
        commit=False,
    )
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Phase 14 — Workflow / status pipeline endpoints
# ---------------------------------------------------------------------------


def _serialize_history(
    entries: List, *, email_by_id: dict[int, str]
) -> List[CandidateStatusHistoryRead]:
    return [
        CandidateStatusHistoryRead(
            id=h.id,
            application_id=h.application_id,
            old_status=h.old_status,
            new_status=h.new_status,
            changed_by_id=h.changed_by_id,
            changed_by_email=email_by_id.get(h.changed_by_id) if h.changed_by_id else None,
            remarks=h.remarks,
            rejection_reason=h.rejection_reason,
            blacklist_approval=h.blacklist_approval,
            created_at=h.created_at,
        )
        for h in entries
    ]


def _email_lookup(db: Session, user_ids: List[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = (
        db.execute(select(User.id, User.email).where(User.id.in_(set(user_ids))))
        .all()
    )
    return {uid: email for uid, email in rows}


@router.get("/workflow/meta", response_model=StatusPipelineMeta)
def get_workflow_meta() -> StatusPipelineMeta:
    """Public-to-HR metadata used by the status changer UI."""
    return StatusPipelineMeta(
        statuses=[
            StatusOption(
                value=status,
                label=STATUS_LABELS[status],
                is_final=status in FINAL_STATUSES,
            )
            for status in PIPELINE_ORDER
        ],
        transitions={
            current: sorted(targets)
            for current, targets in ALLOWED_TRANSITIONS.items()
        },
    )


@router.get(
    "/{candidate_id}/applications/{application_id}/status-history",
    response_model=List[CandidateStatusHistoryRead],
)
def list_status_history(
    candidate_id: int,
    application_id: int,
    db: Session = Depends(get_db),
) -> List[CandidateStatusHistoryRead]:
    app = _get_application_or_404(db, candidate_id, application_id)
    user_ids = [h.changed_by_id for h in app.status_history if h.changed_by_id]
    emails = _email_lookup(db, user_ids)
    return _serialize_history(list(app.status_history), email_by_id=emails)


@router.post(
    "/{candidate_id}/applications/{application_id}/status",
    response_model=CandidateRead,
)
def change_application_status(
    candidate_id: int,
    application_id: int,
    payload: CandidateStatusChange,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_hr_admin),
) -> CandidateRead:
    app = _get_application_or_404(db, candidate_id, application_id)
    previous = app.status

    try:
        result = change_status(
            db,
            application=app,
            new_status=payload.new_status,
            actor=user,
            remarks=payload.remarks,
            rejection_reason=payload.rejection_reason,
            blacklist_approval=payload.blacklist_approval,
        )
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MissingReasonError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.candidate.status.change",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="candidate_application",
        target_id=str(app.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "candidate_id": candidate_id,
            "application_id": application_id,
            "previous_status": previous,
            "new_status": result.new_status,
            "remarks": payload.remarks,
            "rejection_reason": payload.rejection_reason,
            "blacklist_approval": payload.blacklist_approval,
        },
        commit=False,
    )
    db.commit()
    db.refresh(app.candidate)
    return _serialize_candidate(app.candidate, actor=user)

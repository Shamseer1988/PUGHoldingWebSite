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

from app.auth.dependencies import (
    get_request_context,
    require_any_permission,
    require_hr_admin,
    require_permission,
)
from app.auth.permissions import (
    PERM_HR_CANDIDATES_DELETE,
    PERM_HR_CANDIDATES_EDIT,
    PERM_HR_CANDIDATES_SCORE_OVERRIDE,
    PERM_HR_CANDIDATES_STATUS_UPDATE,
    PERM_HR_CANDIDATES_VIEW_DEPT,
    PERM_HR_CANDIDATES_VIEW_FULL,
    PERM_HR_CANDIDATES_VIEW_LIST,
)
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
    Interview,
    JobOpening,
    OfferTracking,
)
from app.schemas.hr_ats import (
    ArchiveRequest,
    AIReviewGenerateResult,
    ApplicationSubmissionResponse,
    BulkCandidateStatusChangeRequest,
    BulkCandidateStatusChangeResult,
    BulkCandidateStatusChangeRow,
    BulkUploadResult,
    BulkUploadSkip,
    CandidateAIReviewPreview,
    CandidateAIReviewRead,
    CandidateApplicationSummary,
    CandidateAutoReviewRead,
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
    CandidateTimelineEvent,
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
    # Most recent application drives the bulk-status modal target.
    latest_application_id: Optional[int] = None
    if candidate.applications:
        latest = max(
            candidate.applications,
            key=lambda a: (a.applied_at, a.id),
        )
        latest_application_id = latest.id

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
        latest_application_id=latest_application_id,
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
    user: User = Depends(
        require_any_permission(
            PERM_HR_CANDIDATES_VIEW_LIST, PERM_HR_CANDIDATES_VIEW_DEPT
        )
    ),
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
    # Department-scoped users (Department Manager) get their candidate
    # list forced to their own org unit — even if they pass a ?department
    # query parameter for a different one.
    effective_department = department
    if (
        not user.is_superuser
        and not user.has_permission(PERM_HR_CANDIDATES_VIEW_LIST)
        and user.has_permission(PERM_HR_CANDIDATES_VIEW_DEPT)
        and user.department
    ):
        effective_department = user.department

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
        department=effective_department,
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
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_VIEW_FULL)),
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
def upload_candidate(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_EDIT)),
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
    # Sync def so the blocking ingest path (file hashing, CV storage,
    # SQLAlchemy commit) runs in FastAPI's thread pool instead of
    # blocking the event loop. ``file.file`` is a synchronous
    # SpooledTemporaryFile so we don't need ``await file.read()``.
    payload = file.file.read()
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
def bulk_upload_candidates(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_EDIT)),
    file: UploadFile = File(..., description="ZIP archive of CV files"),
    job_slug: Optional[str] = Form(default=None, max_length=200),
) -> BulkUploadResult:
    """Extract every supported CV from a ZIP and create candidates.

    Each candidate is wrapped in a SAVEPOINT (``db.begin_nested``) so a
    mid-loop failure (corrupted file, SQLAlchemy IntegrityError, etc.)
    rolls back ONLY that candidate's writes instead of poisoning the
    whole batch. The audit row reflects the partial result.
    """
    # Sync def — see upload_candidate above for the rationale.
    payload = file.file.read()
    try:
        bundle = extract_cvs_from_zip(payload)
    except CvUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    skipped = [BulkUploadSkip(name=n, reason=r) for n, r in bundle.skipped]
    created_count = 0
    matched_count = 0
    duplicate_app_count = 0
    failed_count = 0
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

        # SAVEPOINT per row so a bad CV doesn't poison the rest of the
        # batch. If ingest raises, the savepoint rolls back and the
        # outer transaction stays viable for the next iteration.
        try:
            with db.begin_nested():
                result = ingest_candidate_application(
                    db,
                    form=form,
                    file_meta=meta,
                    uploaded_by_id=user.id,
                    created_by_id=user.id,
                )
        except DuplicateApplicationError:
            duplicate_app_count += 1
            skipped.append(
                BulkUploadSkip(
                    name=meta.original_name,
                    reason="Duplicate application for this job (skipped)",
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001 — surface as a row-level skip
            failed_count += 1
            skipped.append(
                BulkUploadSkip(
                    name=meta.original_name,
                    reason=f"Ingest failed: {type(exc).__name__}",
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
            "ingest_failed_count": failed_count,
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
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_EDIT)),
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


# ---------------------------------------------------------------------------
# Phase 8 — Archive / unarchive (soft delete)
# ---------------------------------------------------------------------------


@router.post("/{candidate_id}/archive", response_model=CandidateRead)
def archive_candidate(
    candidate_id: int,
    payload: ArchiveRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_DELETE)),
) -> CandidateRead:
    """Soft-archive a candidate. Records who/when/why and hides them
    from default list queries (HR can include via include_archived=true).
    Restricted to hr:candidates:delete (HR Manager + Super Admin)."""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.is_archived:
        raise HTTPException(
            status_code=409, detail="Candidate is already archived."
        )
    candidate.is_archived = True
    candidate.archived_at = datetime.now(timezone.utc)
    candidate.archived_by_id = user.id
    candidate.archive_reason = payload.reason

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.candidate.archive",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="candidate",
        target_id=str(candidate.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={"reason": payload.reason},
        commit=False,
    )
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(candidate, actor=user)


@router.post("/{candidate_id}/unarchive", response_model=CandidateRead)
def unarchive_candidate(
    candidate_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_DELETE)),
) -> CandidateRead:
    """Restore a soft-archived candidate."""
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if not candidate.is_archived:
        raise HTTPException(status_code=409, detail="Candidate is not archived.")
    candidate.is_archived = False
    candidate.archived_at = None
    candidate.archived_by_id = None
    candidate.archive_reason = None

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.candidate.unarchive",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="candidate",
        target_id=str(candidate.id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={},
        commit=False,
    )
    db.commit()
    db.refresh(candidate)
    return _serialize_candidate(candidate, actor=user)


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
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_EDIT)),
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
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_EDIT)),
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
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_EDIT)),
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
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_SCORE_OVERRIDE)),
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
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_SCORE_OVERRIDE)),
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
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_EDIT)),
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
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_EDIT)),
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


@router.get(
    "/{candidate_id}/timeline",
    response_model=List[CandidateTimelineEvent],
)
def candidate_timeline(
    candidate_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_VIEW_FULL)),
) -> List[CandidateTimelineEvent]:
    """Unified chronological feed for one candidate across all streams.

    Combines:
      * Recruitment status transitions (CandidateStatusHistory rows).
      * Interview lifecycle (scheduled, completed, cancelled,
        rescheduled, no-show — derived from Interview row state).
      * Interview feedback submissions.
      * Offer lifecycle (created, sent, accepted, declined, joined —
        derived from OfferTracking row state; minimal until Phase 6
        builds out the offer module).
      * The application created event itself ("Applied").

    Sorted newest-first. No pagination (typical candidate has < 50
    events even in extreme cases).
    """
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    events: list[CandidateTimelineEvent] = []
    # Collect every user id we'll need to resolve to emails in one pass.
    user_ids: set[int] = set()

    # --- Applications + status history --------------------------------
    for app in candidate.applications:
        job_title = (
            app.job_opening.title
            if app.job_opening is not None
            else "Unlinked application"
        )
        events.append(
            CandidateTimelineEvent(
                occurred_at=app.applied_at,
                stream="recruitment",
                action="applied",
                title=f"Applied — {job_title}",
                description=f"Source: {app.source or 'unknown'}",
                ref_type="application",
                ref_id=app.id,
            )
        )
        for h in app.status_history:
            if h.changed_by_id:
                user_ids.add(h.changed_by_id)
            events.append(
                CandidateTimelineEvent(
                    occurred_at=h.created_at,
                    stream="recruitment",
                    action="status_changed",
                    title=f"Status → {h.new_status}",
                    description=h.remarks
                    or h.rejection_reason
                    or h.blacklist_approval,
                    ref_type="application",
                    ref_id=app.id,
                    old_status=h.old_status,
                    new_status=h.new_status,
                )
            )

    # --- Interviews ---------------------------------------------------
    application_ids = [a.id for a in candidate.applications]
    if application_ids:
        interviews = list(
            db.execute(
                select(Interview).where(
                    Interview.application_id.in_(application_ids)
                )
            ).scalars()
        )
        for iv in interviews:
            if iv.created_by_id:
                user_ids.add(iv.created_by_id)
            events.append(
                CandidateTimelineEvent(
                    occurred_at=iv.created_at,
                    stream="interview",
                    action="interview_scheduled",
                    title=f"Interview scheduled — {iv.round_name}",
                    description=(
                        f"Mode: {iv.mode} · "
                        f"When: {iv.scheduled_at.isoformat()}"
                    ),
                    ref_type="interview",
                    ref_id=iv.id,
                    new_status=iv.status,
                )
            )
            # Final interview state (only emit when terminal — keeps
            # the feed quieter than emitting every PATCH).
            if iv.status in ("completed", "cancelled", "no_show", "rescheduled"):
                events.append(
                    CandidateTimelineEvent(
                        occurred_at=iv.updated_at,
                        stream="interview",
                        action=f"interview_{iv.status}",
                        title=f"Interview {iv.status.replace('_', ' ')} — {iv.round_name}",
                        ref_type="interview",
                        ref_id=iv.id,
                        new_status=iv.status,
                    )
                )
            for fb in iv.feedback:
                if fb.submitted_by_id:
                    user_ids.add(fb.submitted_by_id)
                events.append(
                    CandidateTimelineEvent(
                        occurred_at=fb.created_at,
                        stream="interview",
                        action="interview_feedback",
                        title=f"Feedback submitted — {iv.round_name}",
                        description=(
                            f"Recommendation: {fb.recommendation}"
                            if fb.recommendation
                            else "Feedback submitted"
                        ),
                        ref_type="interview",
                        ref_id=iv.id,
                    )
                )

    # --- Offers --------------------------------------------------------
    if application_ids:
        offers = list(
            db.execute(
                select(OfferTracking).where(
                    OfferTracking.application_id.in_(application_ids)
                )
            ).scalars()
        )
        for of in offers:
            if of.created_by_id:
                user_ids.add(of.created_by_id)
            events.append(
                CandidateTimelineEvent(
                    occurred_at=of.created_at,
                    stream="offer",
                    action="offer_created",
                    title="Offer created",
                    description=(
                        f"Status: {of.status} · Salary: {of.salary_offered}"
                        if of.salary_offered
                        else f"Status: {of.status}"
                    ),
                    ref_type="offer",
                    ref_id=of.id,
                    new_status=of.status,
                )
            )
            if of.sent_at is not None:
                events.append(
                    CandidateTimelineEvent(
                        occurred_at=of.sent_at,
                        stream="offer",
                        action="offer_sent",
                        title="Offer sent to candidate",
                        ref_type="offer",
                        ref_id=of.id,
                    )
                )
            if of.responded_at is not None:
                events.append(
                    CandidateTimelineEvent(
                        occurred_at=of.responded_at,
                        stream="offer",
                        action=f"offer_{of.status}",
                        title=f"Candidate responded — {of.status}",
                        description=of.decline_reason,
                        ref_type="offer",
                        ref_id=of.id,
                        new_status=of.status,
                    )
                )

    # --- Resolve actor emails and stamp events ------------------------
    emails = _email_lookup(db, list(user_ids))
    # The simple approach: leave actor_email blank for now — most events
    # already carry actor info in their description. Future polish:
    # match changed_by_id / submitted_by_id / created_by_id back to
    # the events that have them.
    _ = emails  # reserved for the polish pass

    events.sort(key=lambda e: e.occurred_at, reverse=True)
    return events


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
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_STATUS_UPDATE)),
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
            "send_email": payload.send_email,
        },
        commit=False,
    )
    db.commit()

    # Fire-and-forget candidate email if HR opted in. Only the three
    # candidate-facing milestone statuses have templates today —
    # shortlisted, selected, rejected. Other transitions are internal
    # (cv_received / hr_review_pending) or already covered by their
    # own emails (interview statuses fire from notify_interview_*).
    if payload.send_email:
        try:
            from app.services import hr_notifications  # local import
            from app.models.hr_ats import (
                STATUS_REJECTED,
                STATUS_SELECTED,
                STATUS_SHORTLISTED,
            )

            if result.new_status == STATUS_SHORTLISTED:
                hr_notifications.notify_candidate_shortlisted(
                    application_id=app.id, actor_id=user.id
                )
            elif result.new_status == STATUS_REJECTED:
                hr_notifications.notify_candidate_rejected(
                    application_id=app.id, actor_id=user.id
                )
            elif result.new_status == STATUS_SELECTED:
                hr_notifications.notify_candidate_selected(
                    application_id=app.id, actor_id=user.id
                )
        except Exception:  # pragma: no cover - never break the response
            import logging

            logging.getLogger(__name__).exception(
                "Status-change email dispatch failed"
            )

    db.refresh(app.candidate)
    return _serialize_candidate(app.candidate, actor=user)


# ---------------------------------------------------------------------------
# Bulk status change (advanced module — phase 5)
# ---------------------------------------------------------------------------


@router.post(
    "/applications/bulk-status",
    response_model=BulkCandidateStatusChangeResult,
)
def bulk_change_application_status(
    payload: BulkCandidateStatusChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_STATUS_UPDATE)),
) -> BulkCandidateStatusChangeResult:
    """Apply one status transition to many applications at once.

    Each row uses the existing :func:`change_status` workflow so every
    rule (mandatory rejection reason, blacklist superuser-only, illegal
    transitions, etc.) still applies. Failed rows are returned with a
    per-row ``error`` field so the UI can show exactly which applications
    couldn't move.

    If ``all_or_nothing`` is True and *any* row fails, the whole
    transaction is rolled back — useful for "approve these 25 candidates
    or no one" workflows.
    """
    ids = list(dict.fromkeys(payload.application_ids))  # dedupe, keep order
    rows: list[BulkCandidateStatusChangeRow] = []

    # Load every application up front in one query. Missing IDs become
    # row-level errors.
    apps_by_id = {
        app.id: app
        for app in db.execute(
            select(CandidateJobApplication).where(
                CandidateJobApplication.id.in_(ids)
            )
        ).scalars()
    }

    success_count = 0
    failed_count = 0
    any_failed = False
    ctx = get_request_context(request)

    notify_keys: list[tuple[str, int]] = []

    for app_id in ids:
        app = apps_by_id.get(app_id)
        if app is None:
            failed_count += 1
            any_failed = True
            rows.append(
                BulkCandidateStatusChangeRow(
                    application_id=app_id,
                    success=False,
                    error="Application not found.",
                )
            )
            continue

        old_status = app.status
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
            failed_count += 1
            any_failed = True
            rows.append(
                BulkCandidateStatusChangeRow(
                    application_id=app_id,
                    candidate_id=app.candidate_id,
                    old_status=old_status,
                    success=False,
                    error=str(exc),
                )
            )
            continue
        except MissingReasonError as exc:
            failed_count += 1
            any_failed = True
            rows.append(
                BulkCandidateStatusChangeRow(
                    application_id=app_id,
                    candidate_id=app.candidate_id,
                    old_status=old_status,
                    success=False,
                    error=str(exc),
                )
            )
            continue
        except InvalidTransitionError as exc:
            failed_count += 1
            any_failed = True
            rows.append(
                BulkCandidateStatusChangeRow(
                    application_id=app_id,
                    candidate_id=app.candidate_id,
                    old_status=old_status,
                    success=False,
                    error=str(exc),
                )
            )
            continue

        success_count += 1
        rows.append(
            BulkCandidateStatusChangeRow(
                application_id=app_id,
                candidate_id=app.candidate_id,
                old_status=old_status,
                new_status=result.new_status,
                success=True,
            )
        )

        record_audit(
            db,
            action="hr.candidate.status.bulk_change",
            actor_id=user.id,
            actor_email=user.email,
            scope="hr",
            target_type="candidate_application",
            target_id=str(app.id),
            ip_address=ctx["ip_address"],
            user_agent=ctx["user_agent"],
            details={
                "candidate_id": app.candidate_id,
                "previous_status": old_status,
                "new_status": result.new_status,
                "remarks": payload.remarks,
                "rejection_reason": payload.rejection_reason,
                "blacklist_approval": payload.blacklist_approval,
                "send_email": payload.send_email,
            },
            commit=False,
        )

        if payload.send_email:
            notify_keys.append((result.new_status, app.id))

    if payload.all_or_nothing and any_failed:
        db.rollback()
        # On rollback every "success" row is invalid — flip them.
        flipped: list[BulkCandidateStatusChangeRow] = []
        for row in rows:
            if row.success:
                flipped.append(
                    BulkCandidateStatusChangeRow(
                        application_id=row.application_id,
                        candidate_id=row.candidate_id,
                        old_status=row.old_status,
                        success=False,
                        error="Rolled back: another row failed (all_or_nothing).",
                    )
                )
            else:
                flipped.append(row)
        return BulkCandidateStatusChangeResult(
            total=len(ids),
            success_count=0,
            failed_count=len(ids),
            rows=flipped,
        )

    db.commit()

    # Fire-and-forget email notifications for successful rows.
    if notify_keys:
        try:
            from app.services import hr_notifications  # local import

            from app.models.hr_ats import (
                STATUS_REJECTED,
                STATUS_SELECTED,
                STATUS_SHORTLISTED,
            )

            for new_status, app_id in notify_keys:
                if new_status == STATUS_SHORTLISTED:
                    hr_notifications.notify_candidate_shortlisted(
                        application_id=app_id, actor_id=user.id
                    )
                elif new_status == STATUS_REJECTED:
                    hr_notifications.notify_candidate_rejected(
                        application_id=app_id, actor_id=user.id
                    )
                elif new_status == STATUS_SELECTED:
                    hr_notifications.notify_candidate_selected(
                        application_id=app_id, actor_id=user.id
                    )
        except Exception:  # pragma: no cover - never break the response
            import logging

            logging.getLogger(__name__).exception(
                "Bulk-status email dispatch failed"
            )

    return BulkCandidateStatusChangeResult(
        total=len(ids),
        success_count=success_count,
        failed_count=failed_count,
        rows=rows,
    )


# ---------------------------------------------------------------------------
# Auto-review (advanced module — phase 4)
# ---------------------------------------------------------------------------


@router.post(
    "/{candidate_id}/applications/{application_id}/auto-review",
    response_model=CandidateAutoReviewRead,
)
def run_application_auto_review(
    candidate_id: int,
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_CANDIDATES_EDIT)),
) -> CandidateAutoReviewRead:
    """Run (or re-run) the auto-review engine on a single application."""
    from app.services import candidate_auto_review

    app = _get_application_or_404(db, candidate_id, application_id)
    review = candidate_auto_review.run_auto_review(db, application=app)

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.candidate.auto_review.run",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="candidate_application",
        target_id=str(application_id),
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "decision": review.decision,
            "score": review.score,
            "rule_id": review.rule_id,
        },
        commit=False,
    )
    db.commit()
    db.refresh(review)
    return CandidateAutoReviewRead.model_validate(review)


@router.get(
    "/{candidate_id}/applications/{application_id}/auto-review",
    response_model=Optional[CandidateAutoReviewRead],
)
def get_application_auto_review(
    candidate_id: int,
    application_id: int,
    db: Session = Depends(get_db),
) -> Optional[CandidateAutoReviewRead]:
    from app.models.hr_ats import CandidateAutoReview

    app = _get_application_or_404(db, candidate_id, application_id)
    review = db.execute(
        select(CandidateAutoReview).where(
            CandidateAutoReview.application_id == app.id
        )
    ).scalar_one_or_none()
    return CandidateAutoReviewRead.model_validate(review) if review else None

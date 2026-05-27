"""HR reports + exports endpoints (Phase 16).

  GET /hr/reports/types                — metadata for the picker
  GET /hr/reports/{type}               — JSON report
  GET /hr/reports/{type}/export        — CSV / XLSX / PDF download
  GET /hr/reports/options/jobs         — distinct (slug, title, department)
  GET /hr/reports/options/departments  — distinct department names

All endpoints accept the same Phase-16 filter query parameters as
``GET /hr/candidates`` so a saved filter set can drive any report.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_request_context,
    require_any_permission,
    require_hr_admin,
    require_permission,
)
from app.auth.permissions import (
    PERM_HR_REPORTS_EXPORT,
    PERM_HR_REPORTS_VIEW_ALL,
    PERM_HR_REPORTS_VIEW_DEPT,
    PERM_HR_REPORTS_VIEW_MINE,
)
from app.core.database import get_db
from app.models.auth import User
from app.services.audit_log import record_audit
from app.services.candidate_search import (
    CandidateFilters,
    collect_distinct_departments,
    collect_distinct_job_options,
)
from app.services.hr_export import export_csv, export_pdf, export_xlsx
from app.services.hr_reports import (
    REPORT_TYPES,
    available_reports_for_scope,
    run_report,
)


router = APIRouter(
    prefix="/hr/reports",
    tags=["HR ATS - Reports"],
    dependencies=[Depends(require_hr_admin)],
)


# ---------------------------------------------------------------------------
# Metadata + dropdown options
# ---------------------------------------------------------------------------


_REPORT_VIEW_DEP = require_any_permission(
    PERM_HR_REPORTS_VIEW_ALL,
    PERM_HR_REPORTS_VIEW_DEPT,
    PERM_HR_REPORTS_VIEW_MINE,
)


def _effective_scope(user: User) -> str:
    """Phase 9 — resolve the highest report scope the user holds.

    Returns 'all' / 'dept' / 'mine' / 'none'. Used by the /types
    endpoint to filter the report catalog and by /{type} to enforce
    that the user can actually run the requested key.
    """
    if user.is_superuser or user.has_permission(PERM_HR_REPORTS_VIEW_ALL):
        return "all"
    if user.has_permission(PERM_HR_REPORTS_VIEW_DEPT):
        return "dept"
    if user.has_permission(PERM_HR_REPORTS_VIEW_MINE):
        return "mine"
    return "none"


@router.get("/types")
def list_report_types(
    user: User = Depends(_REPORT_VIEW_DEP),
) -> list[dict]:
    scope = _effective_scope(user)
    return [
        {
            "key": r.key,
            "title": r.title,
            "description": r.description,
            "icon": r.icon,
            "min_scope": r.min_scope,
        }
        for r in available_reports_for_scope(scope)
    ]


@router.get("/options/jobs")
def job_options(
    db: Session = Depends(get_db),
    user: User = Depends(_REPORT_VIEW_DEP),
) -> list[dict]:
    return [
        {"slug": slug, "title": title, "department": department}
        for slug, title, department in collect_distinct_job_options(db)
    ]


@router.get("/options/departments")
def department_options(
    db: Session = Depends(get_db),
    user: User = Depends(_REPORT_VIEW_DEP),
) -> list[str]:
    return collect_distinct_departments(db)


# ---------------------------------------------------------------------------
# Filter-bundle resolver — shared by JSON + export endpoints
# ---------------------------------------------------------------------------


def _filters_from_query(
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
    include_archived: bool = Query(default=False),
    limit: int = Query(default=500, ge=1, le=2000),
) -> CandidateFilters:
    return CandidateFilters(
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


# ---------------------------------------------------------------------------
# Report endpoints — JSON + export
# ---------------------------------------------------------------------------


def _assert_can_run(user: User, report_type: str) -> None:
    """Phase 9 — enforce that the user's scope covers this report's
    min_scope. Stops a user with only view_mine from calling an
    all-scope report by typing the URL."""
    rt = next((r for r in REPORT_TYPES if r.key == report_type), None)
    if rt is None:
        raise HTTPException(status_code=404, detail=f"Unknown report: {report_type}")
    scope = _effective_scope(user)
    allowed = [r.key for r in available_reports_for_scope(scope)]
    if report_type not in allowed:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Report '{report_type}' requires {rt.min_scope}-scope access"
                f" — your effective scope is '{scope}'."
            ),
        )


@router.get("/{report_type}")
def get_report(
    report_type: str,
    filters: CandidateFilters = Depends(_filters_from_query),
    db: Session = Depends(get_db),
    user: User = Depends(_REPORT_VIEW_DEP),
) -> dict:
    _assert_can_run(user, report_type)
    try:
        report = run_report(db, report_type, filters, actor_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "type": report.type,
        "title": report.title,
        "description": report.description,
        "generated_at": report.generated_at.isoformat(),
        "columns": report.columns,
        "rows": report.rows,
        "summary": report.summary,
    }


@router.get("/{report_type}/export")
def export_report(
    report_type: str,
    request: Request,
    format: str = Query(default="csv", pattern=r"^(csv|xlsx|pdf)$"),
    filters: CandidateFilters = Depends(_filters_from_query),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PERM_HR_REPORTS_EXPORT)),
) -> StreamingResponse:
    _assert_can_run(user, report_type)
    try:
        report = run_report(db, report_type, filters, actor_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if format == "csv":
        data, mime, filename = export_csv(report)
    elif format == "xlsx":
        data, mime, filename = export_xlsx(report)
    else:
        data, mime, filename = export_pdf(report)

    ctx = get_request_context(request)
    record_audit(
        db,
        action="hr.reports.export",
        actor_id=user.id,
        actor_email=user.email,
        scope="hr",
        target_type="hr_report",
        target_id=report.type,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details={
            "format": format,
            "rows": len(report.rows),
            "filters": {
                k: (v.isoformat() if isinstance(v, datetime) else v)
                for k, v in dataclasses.asdict(filters).items()
                if v not in (None, "", False)
            },
        },
        commit=True,
    )

    import io

    return StreamingResponse(
        io.BytesIO(data),
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )

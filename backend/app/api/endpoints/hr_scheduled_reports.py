"""Scheduled report digest CRUD + manual-trigger endpoints (Feature F4)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_request_context, require_permission
from app.auth.permissions import PERM_HR_REPORTS_VIEW_ALL
from app.core.database import get_db
from app.models.auth import User
from app.models.hr_ats import ScheduledReport
from app.schemas.scheduled_report import (
    VALID_FREQUENCIES,
    ScheduledReportCreate,
    ScheduledReportRead,
    ScheduledReportRunResult,
    ScheduledReportUpdate,
)
from app.services.audit_log import record_audit
from app.services.hr_reports import REPORT_TYPES
from app.services.scheduled_reports import dispatch_scheduled_report
from app.services.user_lookup import users_by_id


router = APIRouter(
    prefix="/hr/scheduled-reports",
    tags=["HR - Scheduled Reports"],
    dependencies=[Depends(require_permission(PERM_HR_REPORTS_VIEW_ALL))],
)


_REPORT_KEYS = {rt.key for rt in REPORT_TYPES}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_report_type(report_type: str) -> None:
    if report_type not in _REPORT_KEYS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown report_type '{report_type}'. "
                f"Valid keys: {sorted(_REPORT_KEYS)[:8]}…"
            ),
        )


def _serialize(
    row: ScheduledReport,
    *,
    owner_lookup: dict[int, User],
) -> ScheduledReportRead:
    owner = owner_lookup.get(row.owner_id) if row.owner_id else None
    return ScheduledReportRead(
        id=row.id,
        owner_id=row.owner_id,
        owner_email=owner.email if owner else None,
        name=row.name,
        description=row.description,
        report_type=row.report_type,
        frequency=row.frequency,
        recipients=list(row.recipients or []),
        params=row.params,
        is_active=row.is_active,
        last_run_at=row.last_run_at,
        last_run_status=row.last_run_status,
        last_error=row.last_error,
        last_row_count=row.last_row_count,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _audit(
    db: Session,
    actor: User,
    request: Request,
    *,
    action: str,
    target_id: Optional[int],
    details: Optional[dict] = None,
) -> None:
    ctx = get_request_context(request)
    record_audit(
        db,
        action=action,
        actor_id=actor.id,
        actor_email=actor.email,
        scope="hr",
        target_type="scheduled_report",
        target_id=str(target_id) if target_id is not None else None,
        ip_address=ctx["ip_address"],
        user_agent=ctx["user_agent"],
        details=details,
        commit=False,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=List[ScheduledReportRead])
def list_scheduled_reports(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_REPORTS_VIEW_ALL)),
    include_inactive: bool = False,
) -> list[ScheduledReportRead]:
    stmt = select(ScheduledReport).order_by(
        ScheduledReport.is_active.desc(), ScheduledReport.name
    )
    if not include_inactive:
        stmt = stmt.where(ScheduledReport.is_active.is_(True))
    rows = db.execute(stmt).scalars().all()
    owner_lookup = users_by_id(db, [r.owner_id for r in rows])
    return [_serialize(r, owner_lookup=owner_lookup) for r in rows]


@router.post(
    "",
    response_model=ScheduledReportRead,
    status_code=status.HTTP_201_CREATED,
)
def create_scheduled_report(
    payload: ScheduledReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_REPORTS_VIEW_ALL)),
) -> ScheduledReportRead:
    _validate_report_type(payload.report_type)
    if payload.frequency not in VALID_FREQUENCIES:
        raise HTTPException(
            status_code=422,
            detail=f"frequency must be one of {sorted(VALID_FREQUENCIES)}",
        )

    row = ScheduledReport(
        owner_id=actor.id,
        name=payload.name.strip(),
        description=(payload.description or "").strip() or None,
        report_type=payload.report_type,
        frequency=payload.frequency,
        recipients=[str(r) for r in payload.recipients],
        params=payload.params,
        is_active=payload.is_active,
    )
    db.add(row)
    db.flush()
    _audit(
        db,
        actor,
        request,
        action="hr.scheduled_report.create",
        target_id=row.id,
        details={
            "name": row.name,
            "report_type": row.report_type,
            "frequency": row.frequency,
            "recipient_count": len(row.recipients),
        },
    )
    db.commit()
    db.refresh(row)
    return _serialize(row, owner_lookup=users_by_id(db, [row.owner_id]))


@router.patch(
    "/{report_id}", response_model=ScheduledReportRead
)
def update_scheduled_report(
    report_id: int,
    payload: ScheduledReportUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_REPORTS_VIEW_ALL)),
) -> ScheduledReportRead:
    row = db.get(ScheduledReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Scheduled report not found")

    updates = payload.model_dump(exclude_unset=True)
    if "report_type" in updates and updates["report_type"] is not None:
        _validate_report_type(updates["report_type"])
    if "frequency" in updates and updates["frequency"] is not None:
        if updates["frequency"] not in VALID_FREQUENCIES:
            raise HTTPException(
                status_code=422,
                detail=f"frequency must be one of {sorted(VALID_FREQUENCIES)}",
            )
    if "recipients" in updates and updates["recipients"] is not None:
        updates["recipients"] = [str(r) for r in updates["recipients"]]

    changed: list[str] = []
    for key, value in updates.items():
        if value is None and key not in ("description", "params"):
            continue
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed.append(key)

    if changed:
        _audit(
            db,
            actor,
            request,
            action="hr.scheduled_report.update",
            target_id=row.id,
            details={"fields": changed},
        )
    db.commit()
    db.refresh(row)
    return _serialize(row, owner_lookup=users_by_id(db, [row.owner_id]))


@router.delete(
    "/{report_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_scheduled_report(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_REPORTS_VIEW_ALL)),
) -> Response:
    row = db.get(ScheduledReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    _audit(
        db,
        actor,
        request,
        action="hr.scheduled_report.delete",
        target_id=row.id,
        details={"name": row.name},
    )
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{report_id}/run", response_model=ScheduledReportRunResult
)
def run_now(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission(PERM_HR_REPORTS_VIEW_ALL)),
) -> ScheduledReportRunResult:
    """Force-run the schedule immediately. Useful for previewing the
    email a recipient would see, or for the operator to refire after
    fixing a configuration error."""
    row = db.get(ScheduledReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    result = dispatch_scheduled_report(db, row)
    _audit(
        db,
        actor,
        request,
        action="hr.scheduled_report.run_now",
        target_id=row.id,
        details={
            "row_count": result.row_count,
            "delivered": len(result.delivered),
            "failed": len(result.failed),
        },
    )
    db.commit()
    return ScheduledReportRunResult(
        scheduled_report_id=row.id,
        name=row.name,
        recipients=list(row.recipients or []),
        delivered_count=len(result.delivered),
        row_count=result.row_count,
        error=result.error,
    )


__all__ = ["router"]

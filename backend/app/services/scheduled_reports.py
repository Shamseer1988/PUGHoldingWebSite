"""Scheduled report digest helpers (Feature F4).

Two responsibilities:

1. ``is_due`` — given a schedule's frequency and last_run_at, decide
   whether the daily job should fire it today. Pure function; easy
   to unit-test.

2. ``dispatch_scheduled_report`` — render the report into an HTML
   table (and a brief plain-text summary), send to every recipient
   via the existing email service, and stamp the ``last_run_*``
   columns on the schedule row.

The CRON job in ``app/jobs/report_digests.py`` is the production
caller; the manual "Run now" endpoint reuses the same dispatch
function so manual + scheduled runs go through identical code.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from typing import Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.hr_ats import (
    SCHEDULED_REPORT_FREQ_DAILY,
    SCHEDULED_REPORT_FREQ_MONTHLY,
    SCHEDULED_REPORT_FREQ_WEEKLY,
    SCHEDULED_REPORT_STATUS_FAILED,
    SCHEDULED_REPORT_STATUS_SUCCESS,
    ScheduledReport,
)
from app.services.candidate_search import CandidateFilters
from app.services.email import EmailService
from app.services.hr_reports import Report, run_report


logger = logging.getLogger(__name__)


# Soft cap on rows embedded inline in the email body. Emails over a
# few hundred rows get clipped at the recipient's mail client anyway;
# the summary line and link back to the dashboard handle the rest.
MAX_INLINE_ROWS = 100


# ---------------------------------------------------------------------------
# Cadence
# ---------------------------------------------------------------------------


def is_due(
    frequency: str,
    last_run_at: Optional[datetime],
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Return True if a schedule with this frequency + last_run_at
    should fire on ``now`` (defaults to current UTC time).

    Daily   — never fired today.
    Weekly  — never fired this ISO week.
    Monthly — never fired this calendar month.
    """
    cur = now or datetime.now(timezone.utc)
    if last_run_at is None:
        return True
    # Compare in UTC; the scheduler runs in UTC by default.
    last = last_run_at if last_run_at.tzinfo else last_run_at.replace(tzinfo=timezone.utc)
    if frequency == SCHEDULED_REPORT_FREQ_DAILY:
        return last.date() < cur.date()
    if frequency == SCHEDULED_REPORT_FREQ_WEEKLY:
        cur_year, cur_week, _ = cur.isocalendar()
        last_year, last_week, _ = last.isocalendar()
        return (last_year, last_week) < (cur_year, cur_week)
    if frequency == SCHEDULED_REPORT_FREQ_MONTHLY:
        return (last.year, last.month) < (cur.year, cur.month)
    return False


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_report_html(report: Report) -> str:
    """Format a Report as a simple HTML email body."""
    rows_preview = report.rows[:MAX_INLINE_ROWS]
    truncated = len(report.rows) - len(rows_preview)

    head = "".join(
        f"<th style='padding:6px 10px;background:#f8f5ec;border:1px solid #e5e0cc;text-align:left;font-size:12px;'>{escape(str(c))}</th>"
        for c in report.columns
    )
    body_rows = []
    for row in rows_preview:
        cells = "".join(
            f"<td style='padding:6px 10px;border:1px solid #ece7d5;font-size:12px;'>{escape(str(c) if c is not None else '')}</td>"
            for c in row
        )
        body_rows.append(f"<tr>{cells}</tr>")
    body = "".join(body_rows) or (
        "<tr><td colspan='100' style='padding:12px;color:#6b7280;font-size:12px;'>"
        "No matching rows in the source data.</td></tr>"
    )

    summary_lines = []
    for k, v in (report.summary or {}).items():
        summary_lines.append(
            f"<li><strong>{escape(str(k))}:</strong> {escape(str(v))}</li>"
        )
    summary_html = (
        f"<ul style='margin:8px 0 16px;padding:0 0 0 18px;font-size:13px;color:#374151;'>"
        f"{''.join(summary_lines)}</ul>"
        if summary_lines
        else ""
    )

    truncated_note = (
        f"<p style='color:#92400e;font-size:12px;'>Showing the first "
        f"{len(rows_preview)} of {len(report.rows)} rows — "
        f"{truncated} more available in the HR portal.</p>"
        if truncated > 0
        else ""
    )

    return (
        f"<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial;'>"
        f"<h2 style='color:#5a4a17;margin:0 0 6px;'>{escape(report.title)}</h2>"
        f"<p style='color:#6b7280;margin:0 0 12px;font-size:13px;'>{escape(report.description)}</p>"
        f"<p style='color:#6b7280;font-size:12px;'>Generated "
        f"{report.generated_at.strftime('%d %b %Y %H:%M UTC')}</p>"
        f"{summary_html}"
        f"<table cellspacing='0' cellpadding='0' style='border-collapse:collapse;width:100%;'>"
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{body}</tbody>"
        f"</table>"
        f"{truncated_note}"
        f"</div>"
    )


def render_report_text(report: Report) -> str:
    """Plain-text fallback for clients that don't render HTML."""
    lines = [
        report.title,
        "=" * len(report.title),
        report.description,
        f"Generated: {report.generated_at.strftime('%d %b %Y %H:%M UTC')}",
        f"Rows: {len(report.rows)}",
        "",
    ]
    if report.summary:
        lines.append("Summary:")
        for k, v in report.summary.items():
            lines.append(f"  {k}: {v}")
        lines.append("")
    if report.rows:
        lines.append("\t".join(report.columns))
        for row in report.rows[:MAX_INLINE_ROWS]:
            lines.append("\t".join("" if c is None else str(c) for c in row))
        if len(report.rows) > MAX_INLINE_ROWS:
            lines.append(
                f"... {len(report.rows) - MAX_INLINE_ROWS} more rows omitted ..."
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DispatchResult:
    row_count: int
    delivered: list[str]
    failed: list[str]
    error: Optional[str] = None


def dispatch_scheduled_report(
    db: Session, schedule: ScheduledReport
) -> DispatchResult:
    """Generate the report, send to every recipient, and stamp the
    ``last_run_*`` columns. Always commits the schedule row; mail
    failures are recorded in ``last_error`` rather than raised.
    """
    delivered: list[str] = []
    failed: list[str] = []
    error: Optional[str] = None
    row_count = 0

    try:
        filters = _filters_from_params(schedule.params or {})
        report = run_report(
            db,
            schedule.report_type,
            filters,
            actor_id=schedule.owner_id,
        )
        row_count = len(report.rows)
        subject = f"[PUG HR] {report.title}"
        body_html = render_report_html(report)
        body_text = render_report_text(report)

        for recipient in schedule.recipients or []:
            try:
                EmailService.send_simple(
                    db,
                    to_email=recipient,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html,
                )
                delivered.append(recipient)
            except Exception as exc:  # noqa: BLE001 — keep going
                logger.warning(
                    "Scheduled report %s failed to deliver to %s: %r",
                    schedule.id,
                    recipient,
                    exc,
                )
                failed.append(recipient)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        logger.exception(
            "Scheduled report %s failed: %s", schedule.id, error
        )

    # --- Stamp bookkeeping ---
    schedule.last_run_at = datetime.now(timezone.utc)
    schedule.last_row_count = row_count
    if error or failed:
        schedule.last_run_status = SCHEDULED_REPORT_STATUS_FAILED
        # Surface only the last delivery problem in the row to keep the
        # column compact; the full set is logged.
        schedule.last_error = (
            error
            or f"Delivery failed to: {', '.join(failed[:5])}"
            + (" + more" if len(failed) > 5 else "")
        )
    else:
        schedule.last_run_status = SCHEDULED_REPORT_STATUS_SUCCESS
        schedule.last_error = None
    db.commit()

    return DispatchResult(
        row_count=row_count,
        delivered=delivered,
        failed=failed,
        error=error,
    )


def _filters_from_params(params: dict) -> CandidateFilters:
    """Build a CandidateFilters dataclass from the schedule's params
    payload, dropping unknown keys silently."""
    allowed = CandidateFilters.__dataclass_fields__.keys()
    clean = {k: v for k, v in params.items() if k in allowed}
    for key in ("uploaded_from", "uploaded_to"):
        if isinstance(clean.get(key), str):
            try:
                clean[key] = datetime.fromisoformat(clean[key])
            except ValueError:
                clean.pop(key, None)
    return CandidateFilters(**clean)


# ---------------------------------------------------------------------------
# CRON entry point (called from app.jobs.report_digests)
# ---------------------------------------------------------------------------


def run_due_schedules() -> dict:
    """Find every active schedule whose cadence is satisfied and
    dispatch it. Opens its own DB session — APScheduler fires this on
    a background thread so the FastAPI per-request session machinery
    is not available.

    Returns a small summary dict for observability + tests.
    """
    fired = 0
    skipped = 0
    failed = 0
    with SessionLocal() as db:
        rows = (
            db.query(ScheduledReport).filter(ScheduledReport.is_active.is_(True)).all()
        )
        for row in rows:
            if not is_due(row.frequency, row.last_run_at):
                skipped += 1
                continue
            result = dispatch_scheduled_report(db, row)
            fired += 1
            if result.error or result.failed:
                failed += 1
    return {"fired": fired, "skipped": skipped, "failed": failed}


__all__ = [
    "DispatchResult",
    "dispatch_scheduled_report",
    "is_due",
    "render_report_html",
    "render_report_text",
    "run_due_schedules",
]

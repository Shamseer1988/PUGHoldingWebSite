"""Branded HTML email templates for the advanced HR module.

Each template renders to a (subject, html_body, text_body) triple. The
HTML uses inline styles so it survives Outlook / Gmail / Apple Mail
rendering. The text body is a plain-text fallback for clients that
prefer it (and for accessibility).

Templates are intentionally tiny pure-Python f-strings rather than a
template engine — there are only a dozen of them and they share a
common HEADER/FOOTER pair. If the surface grows, swap this for Jinja2
under :mod:`app.services.email_templates_jinja`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Template keys (also used as EmailLog.template_key — keep them stable)
# ---------------------------------------------------------------------------

TPL_JOB_SUBMITTED = "job_submitted_for_approval"
TPL_JOB_APPROVED = "job_approved_published"
TPL_JOB_REJECTED = "job_rejected"
TPL_JOB_REVISION_REQUESTED = "job_revision_requested"
TPL_JOB_PUBLISHED = "job_published"
TPL_CANDIDATE_APPLICATION_RECEIVED = "candidate_application_received"
TPL_CANDIDATE_SHORTLISTED = "candidate_shortlisted"
TPL_CANDIDATE_REJECTED = "candidate_rejected"
TPL_CANDIDATE_SELECTED = "candidate_selected"
TPL_INTERVIEW_SCHEDULED = "interview_scheduled"
TPL_INTERVIEW_RESCHEDULED = "interview_rescheduled"
TPL_INTERVIEW_CANCELLED = "interview_cancelled"


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    html: str
    text: str


# ---------------------------------------------------------------------------
# Shared chrome
# ---------------------------------------------------------------------------


def _header(brand_logo_url: Optional[str], title: str) -> str:
    logo_block = ""
    if brand_logo_url:
        logo_block = (
            f'<img src="{_esc(brand_logo_url)}" alt="PUG Holding" '
            f'style="max-height:48px;display:block;margin:0 auto 16px auto;" />'
        )
    return (
        '<div style="background:#17382f;padding:24px;text-align:center;">'
        f"{logo_block}"
        f'<h1 style="margin:0;color:#f6f3eb;font-family:Inter,Arial,sans-serif;'
        f'font-size:20px;font-weight:600;letter-spacing:0.02em;">{_esc(title)}</h1>'
        "</div>"
    )


def _footer(footer_text: Optional[str]) -> str:
    text = footer_text or (
        "© Paris United Group Holding. "
        "This is an automated notification — please do not reply."
    )
    return (
        '<div style="background:#f6f3eb;padding:16px 24px;text-align:center;'
        'color:#61736b;font-family:Inter,Arial,sans-serif;font-size:12px;'
        'line-height:1.5;border-top:1px solid #e4e0d6;">'
        f"{_esc(text)}"
        "</div>"
    )


def _wrap(
    *,
    title: str,
    body_html: str,
    brand_logo_url: Optional[str] = None,
    footer_text: Optional[str] = None,
) -> str:
    return (
        '<div style="background:#ffffff;font-family:Inter,Arial,sans-serif;'
        'color:#17382f;max-width:640px;margin:0 auto;border:1px solid #e4e0d6;'
        'border-radius:12px;overflow:hidden;">'
        f"{_header(brand_logo_url, title)}"
        '<div style="padding:24px;font-size:14px;line-height:1.6;">'
        f"{body_html}"
        "</div>"
        f"{_footer(footer_text)}"
        "</div>"
    )


def _btn(label: str, url: Optional[str]) -> str:
    if not url:
        return ""
    return (
        f'<p style="margin:20px 0;text-align:center;">'
        f'<a href="{_esc(url)}" style="background:#17382f;color:#f6f3eb;'
        f'text-decoration:none;padding:10px 20px;border-radius:6px;'
        f'display:inline-block;font-weight:600;">{_esc(label)}</a>'
        "</p>"
    )


def _kv(label: str, value: Optional[str]) -> str:
    if value is None or value == "":
        return ""
    return (
        f'<p style="margin:6px 0;"><strong style="color:#61736b;">'
        f"{_esc(label)}:</strong> {_esc(str(value))}</p>"
    )


def _esc(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ---------------------------------------------------------------------------
# Renderers — one function per template_key
# ---------------------------------------------------------------------------


def _ctx(template_key: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Shared chrome context — read from ctx, fall back to None."""
    return {
        "brand_logo_url": ctx.get("brand_logo_url"),
        "footer_text": ctx.get("email_footer_text"),
    }


def render(template_key: str, ctx: Dict[str, Any]) -> RenderedEmail:
    """Render a template by key. Raises KeyError on unknown keys."""
    renderer = _RENDERERS.get(template_key)
    if renderer is None:
        raise KeyError(f"Unknown email template '{template_key}'")
    return renderer(ctx)


# --- Job approval workflow templates --------------------------------------


def _r_job_submitted(ctx: Dict[str, Any]) -> RenderedEmail:
    job_title = ctx.get("job_title", "(untitled)")
    job_dept = ctx.get("job_department", "")
    job_company = ctx.get("job_company", "")
    actor = ctx.get("actor_email", "an HR Executive")
    approval_url = ctx.get("approval_url")
    subject = f"[PUG HR] Job pending your approval — {job_title}"

    body = (
        f'<p>Hi,</p>'
        f"<p>A new job opening has been submitted for approval by <strong>"
        f"{_esc(actor)}</strong>:</p>"
        f"{_kv('Position', job_title)}"
        f"{_kv('Department', job_dept)}"
        f"{_kv('Company', job_company)}"
        f"<p>Please review it in the HR Admin Portal.</p>"
        f"{_btn('Open in HR Portal', approval_url)}"
    )
    html = _wrap(title="Job pending approval", body_html=body, **_ctx(TPL_JOB_SUBMITTED, ctx))
    text = (
        f"A new job opening has been submitted for approval by {actor}.\n"
        f"Position: {job_title}\n"
        f"Department: {job_dept}\n"
        f"Company: {job_company}\n"
        f"Please review it in the HR Admin Portal."
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_job_approved(ctx: Dict[str, Any]) -> RenderedEmail:
    job_title = ctx.get("job_title", "(untitled)")
    approver = ctx.get("actor_email", "the HR Manager")
    job_url = ctx.get("public_job_url")
    subject = f"[PUG HR] Job approved & published — {job_title}"

    body = (
        f"<p>Good news! The job opening <strong>{_esc(job_title)}</strong> "
        f"has been approved and is now live on the public careers page.</p>"
        f"{_kv('Approved by', approver)}"
        f"{_btn('View public listing', job_url)}"
    )
    html = _wrap(title="Job approved", body_html=body, **_ctx(TPL_JOB_APPROVED, ctx))
    text = (
        f"The job opening '{job_title}' has been approved and published.\n"
        f"Approved by: {approver}"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_job_rejected(ctx: Dict[str, Any]) -> RenderedEmail:
    job_title = ctx.get("job_title", "(untitled)")
    reviewer = ctx.get("actor_email", "the HR Manager")
    reason = ctx.get("reason", "(no reason supplied)")
    edit_url = ctx.get("edit_url")
    subject = f"[PUG HR] Job rejected — {job_title}"

    body = (
        f"<p>The job opening <strong>{_esc(job_title)}</strong> was reviewed "
        f"and rejected.</p>"
        f"{_kv('Reviewed by', reviewer)}"
        f"<p style='margin:12px 0;'><strong style='color:#61736b;'>Reason:</strong></p>"
        f"<blockquote style='margin:0;padding:8px 12px;border-left:3px solid #b65a3c;"
        f"background:#f6f3eb;color:#3a4842;white-space:pre-wrap;'>{_esc(reason)}</blockquote>"
        f"{_btn('Edit the job', edit_url)}"
    )
    html = _wrap(title="Job rejected", body_html=body, **_ctx(TPL_JOB_REJECTED, ctx))
    text = (
        f"The job opening '{job_title}' was rejected by {reviewer}.\n"
        f"Reason: {reason}"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_job_revision_requested(ctx: Dict[str, Any]) -> RenderedEmail:
    job_title = ctx.get("job_title", "(untitled)")
    reviewer = ctx.get("actor_email", "the HR Manager")
    reason = ctx.get("reason", "")
    edit_url = ctx.get("edit_url")
    subject = f"[PUG HR] Revision requested — {job_title}"

    body = (
        f"<p>The HR Manager requested changes to <strong>{_esc(job_title)}"
        f"</strong>:</p>"
        f"{_kv('Reviewer', reviewer)}"
        + (
            f"<p style='margin:12px 0;'><strong style='color:#61736b;'>Notes:"
            f"</strong></p>"
            f"<blockquote style='margin:0;padding:8px 12px;border-left:3px solid "
            f"#c89132;background:#f6f3eb;color:#3a4842;white-space:pre-wrap;'>"
            f"{_esc(reason)}</blockquote>"
            if reason
            else ""
        )
        + _btn("Edit the job", edit_url)
    )
    html = _wrap(
        title="Revision requested",
        body_html=body,
        **_ctx(TPL_JOB_REVISION_REQUESTED, ctx),
    )
    text = (
        f"The HR Manager requested changes to '{job_title}'.\n"
        f"Reviewer: {reviewer}\n"
        + (f"Notes: {reason}" if reason else "")
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_job_published(ctx: Dict[str, Any]) -> RenderedEmail:
    job_title = ctx.get("job_title", "(untitled)")
    actor = ctx.get("actor_email", "")
    job_url = ctx.get("public_job_url")
    subject = f"[PUG HR] Job published — {job_title}"

    body = (
        f"<p>The job opening <strong>{_esc(job_title)}</strong> is now live "
        f"on the public careers page.</p>"
        f"{_kv('Actioned by', actor)}"
        f"{_btn('View public listing', job_url)}"
    )
    html = _wrap(title="Job published", body_html=body, **_ctx(TPL_JOB_PUBLISHED, ctx))
    text = f"The job opening '{job_title}' is now live on the public careers page."
    return RenderedEmail(subject=subject, html=html, text=text)


# --- Candidate templates ---------------------------------------------------


def _r_candidate_application_received(ctx: Dict[str, Any]) -> RenderedEmail:
    candidate_name = ctx.get("candidate_name", "there")
    job_title = ctx.get("job_title")
    subject = "[PUG] We received your application"

    job_line = (
        f"<p>You applied for the <strong>{_esc(job_title)}</strong> role.</p>"
        if job_title
        else "<p>Your CV is now in our talent pool.</p>"
    )
    body = (
        f"<p>Hi {_esc(candidate_name)},</p>"
        f"<p>Thank you for your interest in joining Paris United Group Holding. "
        f"We've successfully received your application.</p>"
        f"{job_line}"
        f"<p>Our HR team will review your CV and reach out if your profile "
        f"matches an open opportunity.</p>"
        f"<p>Warm regards,<br/>The PUG HR Team</p>"
    )
    html = _wrap(
        title="Application received",
        body_html=body,
        **_ctx(TPL_CANDIDATE_APPLICATION_RECEIVED, ctx),
    )
    text = (
        f"Hi {candidate_name},\n\n"
        "Thank you for applying to Paris United Group Holding. "
        "We've received your application and will be in touch if your "
        "profile matches an open opportunity.\n\n"
        "— The PUG HR Team"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_candidate_shortlisted(ctx: Dict[str, Any]) -> RenderedEmail:
    candidate_name = ctx.get("candidate_name", "there")
    job_title = ctx.get("job_title", "the position")
    subject = f"[PUG] You've been shortlisted — {job_title}"

    body = (
        f"<p>Hi {_esc(candidate_name)},</p>"
        f"<p>Great news — you've been <strong>shortlisted</strong> for the "
        f"<strong>{_esc(job_title)}</strong> role at Paris United Group Holding.</p>"
        f"<p>Our team will be in touch shortly to discuss the next steps.</p>"
        f"<p>Warm regards,<br/>The PUG HR Team</p>"
    )
    html = _wrap(
        title="You've been shortlisted",
        body_html=body,
        **_ctx(TPL_CANDIDATE_SHORTLISTED, ctx),
    )
    text = (
        f"Hi {candidate_name},\n\n"
        f"Great news — you've been shortlisted for the {job_title} role. "
        "Our team will be in touch shortly.\n\n"
        "— The PUG HR Team"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_candidate_rejected(ctx: Dict[str, Any]) -> RenderedEmail:
    candidate_name = ctx.get("candidate_name", "there")
    job_title = ctx.get("job_title", "this role")
    subject = "[PUG] Update on your application"

    body = (
        f"<p>Hi {_esc(candidate_name)},</p>"
        f"<p>Thank you for taking the time to apply for the "
        f"<strong>{_esc(job_title)}</strong> role at Paris United Group Holding.</p>"
        f"<p>After careful review, we won't be moving forward with your "
        f"application this time. We genuinely appreciate the effort you put "
        f"into reaching out and will keep your CV on file for future openings.</p>"
        f"<p>Warm regards,<br/>The PUG HR Team</p>"
    )
    html = _wrap(
        title="Update on your application",
        body_html=body,
        **_ctx(TPL_CANDIDATE_REJECTED, ctx),
    )
    text = (
        f"Hi {candidate_name},\n\n"
        f"Thank you for applying for the {job_title} role. After careful "
        "review we won't be moving forward at this time, but we will keep "
        "your CV on file.\n\n"
        "— The PUG HR Team"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_candidate_selected(ctx: Dict[str, Any]) -> RenderedEmail:
    candidate_name = ctx.get("candidate_name", "there")
    job_title = ctx.get("job_title", "the position")
    subject = f"[PUG] Offer in progress — {job_title}"

    body = (
        f"<p>Hi {_esc(candidate_name)},</p>"
        f"<p>Congratulations — we'd like to offer you the "
        f"<strong>{_esc(job_title)}</strong> role at Paris United Group Holding.</p>"
        f"<p>Our HR team will reach out shortly with the formal offer letter "
        f"and onboarding details.</p>"
        f"<p>Warm regards,<br/>The PUG HR Team</p>"
    )
    html = _wrap(
        title="Offer in progress",
        body_html=body,
        **_ctx(TPL_CANDIDATE_SELECTED, ctx),
    )
    text = (
        f"Hi {candidate_name},\n\n"
        f"Congratulations — we'd like to offer you the {job_title} role.\n\n"
        "— The PUG HR Team"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


# --- Interview templates ---------------------------------------------------


def _fmt_dt(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%A, %d %B %Y at %H:%M (%Z)").rstrip()
    return str(value) if value else ""


def _r_interview_scheduled(ctx: Dict[str, Any]) -> RenderedEmail:
    candidate_name = ctx.get("candidate_name", "there")
    job_title = ctx.get("job_title", "the position")
    round_name = ctx.get("round_name", "")
    when = _fmt_dt(ctx.get("scheduled_at"))
    duration = ctx.get("duration_minutes")
    mode = ctx.get("mode", "")
    location_or_link = ctx.get("location_or_link", "")
    meeting_link = ctx.get("meeting_link")
    interviewer = ctx.get("interviewer_name") or ctx.get("interviewer_email", "")
    note = ctx.get("email_note", "")
    subject = f"[PUG] Interview scheduled — {job_title}"

    mode_label = {
        "online": "Online",
        "phone": "Phone",
        "in_person": "In person",
    }.get(mode, mode.title() if mode else "")

    body = (
        f"<p>Hi {_esc(candidate_name)},</p>"
        f"<p>Your interview for the <strong>{_esc(job_title)}</strong> role "
        f"has been scheduled.</p>"
        f"{_kv('Round', round_name)}"
        f"{_kv('Date & time', when)}"
        + (f"{_kv('Duration', f'{duration} minutes')}" if duration else "")
        + f"{_kv('Mode', mode_label)}"
        + (
            f"{_kv('Location', location_or_link)}"
            if mode == "in_person" and location_or_link
            else ""
        )
        + (
            f"{_kv('Interviewer', interviewer)}"
            if interviewer
            else ""
        )
        + _btn("Join Google Meet", meeting_link)
        + (
            f"<p style='margin:12px 0;'><strong style='color:#61736b;'>"
            f"Note from HR:</strong></p>"
            f"<blockquote style='margin:0;padding:8px 12px;border-left:3px solid "
            f"#17382f;background:#f6f3eb;color:#3a4842;white-space:pre-wrap;'>"
            f"{_esc(note)}</blockquote>"
            if note
            else ""
        )
        + "<p>Please reply to this email if you need to reschedule.</p>"
        + "<p>Warm regards,<br/>The PUG HR Team</p>"
    )
    html = _wrap(
        title="Interview scheduled",
        body_html=body,
        **_ctx(TPL_INTERVIEW_SCHEDULED, ctx),
    )
    text = (
        f"Hi {candidate_name},\n\n"
        f"Your interview for the {job_title} role has been scheduled.\n"
        f"Round: {round_name}\n"
        f"Date & time: {when}\n"
        f"Mode: {mode_label}\n"
        + (f"Location: {location_or_link}\n" if mode == "in_person" else "")
        + (f"Meeting link: {meeting_link}\n" if meeting_link else "")
        + (f"Interviewer: {interviewer}\n" if interviewer else "")
        + (f"\nNote from HR:\n{note}\n" if note else "")
        + "\nPlease reply to this email if you need to reschedule.\n\n"
        "— The PUG HR Team"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_interview_rescheduled(ctx: Dict[str, Any]) -> RenderedEmail:
    rendered = _r_interview_scheduled(ctx)
    subject = rendered.subject.replace("scheduled", "rescheduled")
    title_swap = "Interview rescheduled"
    html = rendered.html.replace("Interview scheduled", title_swap)
    text = rendered.text.replace("has been scheduled", "has been rescheduled")
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_interview_cancelled(ctx: Dict[str, Any]) -> RenderedEmail:
    candidate_name = ctx.get("candidate_name", "there")
    job_title = ctx.get("job_title", "the position")
    when = _fmt_dt(ctx.get("scheduled_at"))
    subject = f"[PUG] Interview cancelled — {job_title}"

    body = (
        f"<p>Hi {_esc(candidate_name)},</p>"
        f"<p>Unfortunately your interview for the <strong>{_esc(job_title)}"
        f"</strong> role"
        + (f" scheduled for <strong>{_esc(when)}</strong>" if when else "")
        + " has been cancelled.</p>"
        f"<p>Our HR team will reach out shortly if a new slot becomes "
        f"available.</p>"
        f"<p>Warm regards,<br/>The PUG HR Team</p>"
    )
    html = _wrap(
        title="Interview cancelled",
        body_html=body,
        **_ctx(TPL_INTERVIEW_CANCELLED, ctx),
    )
    text = (
        f"Hi {candidate_name},\n\n"
        f"Your interview for the {job_title} role has been cancelled. "
        "We'll be in touch if a new slot becomes available.\n\n"
        "— The PUG HR Team"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


_RENDERERS = {
    TPL_JOB_SUBMITTED: _r_job_submitted,
    TPL_JOB_APPROVED: _r_job_approved,
    TPL_JOB_REJECTED: _r_job_rejected,
    TPL_JOB_REVISION_REQUESTED: _r_job_revision_requested,
    TPL_JOB_PUBLISHED: _r_job_published,
    TPL_CANDIDATE_APPLICATION_RECEIVED: _r_candidate_application_received,
    TPL_CANDIDATE_SHORTLISTED: _r_candidate_shortlisted,
    TPL_CANDIDATE_REJECTED: _r_candidate_rejected,
    TPL_CANDIDATE_SELECTED: _r_candidate_selected,
    TPL_INTERVIEW_SCHEDULED: _r_interview_scheduled,
    TPL_INTERVIEW_RESCHEDULED: _r_interview_rescheduled,
    TPL_INTERVIEW_CANCELLED: _r_interview_cancelled,
}


def available_template_keys() -> tuple[str, ...]:
    return tuple(sorted(_RENDERERS.keys()))

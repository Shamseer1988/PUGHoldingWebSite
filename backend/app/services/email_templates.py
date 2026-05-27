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
# Phase 11 — interview-feedback + full offer-lifecycle notifications.
TPL_INTERVIEW_FEEDBACK_SUBMITTED = "interview_feedback_submitted"
TPL_OFFER_APPROVAL_REQUESTED = "offer_approval_requested"
TPL_OFFER_APPROVED = "offer_approved"
TPL_OFFER_ISSUED = "offer_issued"
TPL_OFFER_ACCEPTED = "offer_accepted"
TPL_OFFER_DECLINED = "offer_declined"
TPL_OFFER_JOINED = "offer_joined"
# Contact-inbox ticket reply (Phase B of the Contact-Us upgrade).
TPL_CONTACT_REPLY = "contact_reply_branded"


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
        + _btn("Join meeting", meeting_link)
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


# ---------------------------------------------------------------------------
# Phase 11 — interview feedback + offer lifecycle templates
# ---------------------------------------------------------------------------


def _r_interview_feedback_submitted(ctx: Dict[str, Any]) -> RenderedEmail:
    """Internal email to HR Manager / Executive when an interviewer
    submits feedback. Tells them which round, the recommendation, and
    where to read the full notes."""
    candidate_name = ctx.get("candidate_name", "the candidate")
    job_title = ctx.get("job_title", "the role")
    round_name = ctx.get("round_name", "")
    interviewer = ctx.get("interviewer_email", "the interviewer")
    recommendation = ctx.get("recommendation", "submitted")
    rating = ctx.get("rating")
    subject = f"[PUG] Interview feedback submitted — {candidate_name} ({job_title})"
    body = (
        f"<p>Hi team,</p>"
        f"<p><strong>{_esc(interviewer)}</strong> just submitted feedback for "
        f"<strong>{_esc(candidate_name)}</strong> after the "
        f"<strong>{_esc(round_name)}</strong> round of <strong>{_esc(job_title)}</strong>.</p>"
        + _kv("Recommendation", str(recommendation))
        + (_kv("Rating", f"{rating} / 5") if rating else "")
        + "<p>Open the interview in the HR portal to read the full feedback.</p>"
        + "<p>— The PUG HR system</p>"
    )
    html = _wrap(
        title="Interview feedback submitted",
        body_html=body,
        **_ctx(TPL_INTERVIEW_FEEDBACK_SUBMITTED, ctx),
    )
    text = (
        f"{interviewer} submitted feedback for {candidate_name} "
        f"after the {round_name} round of {job_title}.\n"
        f"Recommendation: {recommendation}\n"
        + (f"Rating: {rating} / 5\n" if rating else "")
        + "Open the HR portal for the full notes.\n"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_offer_approval_requested(ctx: Dict[str, Any]) -> RenderedEmail:
    """Internal email to HR Manager when HR Admin submits an offer for
    approval. Includes the candidate / role / salary so the manager
    can decide without opening the portal."""
    candidate_name = ctx.get("candidate_name", "the candidate")
    job_title = ctx.get("job_title", "the role")
    salary = ctx.get("salary_offered")
    joining_date = ctx.get("joining_date")
    subject = f"[PUG] Offer needs approval — {candidate_name} ({job_title})"
    body = (
        f"<p>Hi HR Manager,</p>"
        f"<p>An offer for <strong>{_esc(candidate_name)}</strong> "
        f"({_esc(job_title)}) is waiting for your approval.</p>"
        + (_kv("Salary", str(salary)) if salary else "")
        + (_kv("Joining date", str(joining_date)) if joining_date else "")
        + "<p>Approve, request changes, or reject in the HR portal under "
        + "<strong>Offers → Pending approval</strong>.</p>"
        + "<p>— The PUG HR system</p>"
    )
    html = _wrap(
        title="Offer needs approval",
        body_html=body,
        **_ctx(TPL_OFFER_APPROVAL_REQUESTED, ctx),
    )
    text = (
        f"Offer for {candidate_name} ({job_title}) is waiting for approval.\n"
        + (f"Salary: {salary}\n" if salary else "")
        + (f"Joining date: {joining_date}\n" if joining_date else "")
        + "Approve in the HR portal under Offers → Pending approval.\n"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_offer_approved(ctx: Dict[str, Any]) -> RenderedEmail:
    """Internal email to HR Admin telling them an offer is cleared to
    issue."""
    candidate_name = ctx.get("candidate_name", "the candidate")
    job_title = ctx.get("job_title", "the role")
    actor_email = ctx.get("actor_email", "an HR Manager")
    subject = f"[PUG] Offer approved — {candidate_name} ({job_title})"
    body = (
        f"<p>Hi HR team,</p>"
        f"<p><strong>{_esc(actor_email)}</strong> approved the offer for "
        f"<strong>{_esc(candidate_name)}</strong> ({_esc(job_title)}). "
        f"You can now issue the offer letter to the candidate.</p>"
        + "<p>— The PUG HR system</p>"
    )
    html = _wrap(
        title="Offer approved",
        body_html=body,
        **_ctx(TPL_OFFER_APPROVED, ctx),
    )
    text = (
        f"{actor_email} approved the offer for {candidate_name} ({job_title}). "
        f"Ready to issue.\n"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_offer_issued(ctx: Dict[str, Any]) -> RenderedEmail:
    """Candidate-facing offer letter notification. Carries position +
    salary + joining date + the offer-letter reference number."""
    candidate_name = ctx.get("candidate_name", "there")
    job_title = ctx.get("job_title", "the role")
    position = ctx.get("position") or job_title
    salary = ctx.get("salary_offered")
    joining_date = ctx.get("joining_date")
    letter_no = ctx.get("offer_letter_number")
    work_location = ctx.get("work_location")
    subject = f"[PUG] Your offer letter — {job_title}"
    body = (
        f"<p>Dear {_esc(candidate_name)},</p>"
        f"<p>Congratulations! We're pleased to extend an offer for the "
        f"<strong>{_esc(position)}</strong> position at Paris United Group "
        f"Holding.</p>"
        + (_kv("Offer letter number", str(letter_no)) if letter_no else "")
        + (_kv("Salary offered", str(salary)) if salary else "")
        + (_kv("Joining date", str(joining_date)) if joining_date else "")
        + (_kv("Work location", str(work_location)) if work_location else "")
        + "<p>Please review and respond to HR with your decision. We're "
        + "looking forward to having you on board.</p>"
        + "<p>Warm regards,<br/>The PUG HR Team</p>"
    )
    html = _wrap(
        title="Your offer letter",
        body_html=body,
        **_ctx(TPL_OFFER_ISSUED, ctx),
    )
    text = (
        f"Dear {candidate_name},\n\n"
        f"We're pleased to extend an offer for the {position} position.\n"
        + (f"Letter no: {letter_no}\n" if letter_no else "")
        + (f"Salary: {salary}\n" if salary else "")
        + (f"Joining date: {joining_date}\n" if joining_date else "")
        + (f"Work location: {work_location}\n" if work_location else "")
        + "\nPlease respond to HR with your decision.\n\n"
        + "— The PUG HR Team"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_offer_accepted(ctx: Dict[str, Any]) -> RenderedEmail:
    """Internal email to HR team after HR records a candidate's
    acceptance. Surfaces the joining date so they can prep onboarding."""
    candidate_name = ctx.get("candidate_name", "the candidate")
    job_title = ctx.get("job_title", "the role")
    joining_date = ctx.get("joining_date")
    subject = f"[PUG] Offer accepted — {candidate_name} ({job_title})"
    body = (
        f"<p>Good news — <strong>{_esc(candidate_name)}</strong> accepted "
        f"the offer for <strong>{_esc(job_title)}</strong>.</p>"
        + (
            _kv("Joining date", str(joining_date))
            if joining_date
            else "<p>No joining date confirmed yet — follow up with the candidate.</p>"
        )
        + "<p>Kick off the onboarding workflow when ready.</p>"
        + "<p>— The PUG HR system</p>"
    )
    html = _wrap(
        title="Offer accepted",
        body_html=body,
        **_ctx(TPL_OFFER_ACCEPTED, ctx),
    )
    text = (
        f"{candidate_name} accepted the offer for {job_title}.\n"
        + (f"Joining date: {joining_date}\n" if joining_date else "")
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_offer_declined(ctx: Dict[str, Any]) -> RenderedEmail:
    """Internal email to HR team when HR records a candidate decline."""
    candidate_name = ctx.get("candidate_name", "the candidate")
    job_title = ctx.get("job_title", "the role")
    reason = ctx.get("decline_reason") or "No reason recorded."
    subject = f"[PUG] Offer declined — {candidate_name} ({job_title})"
    body = (
        f"<p><strong>{_esc(candidate_name)}</strong> declined the offer for "
        f"<strong>{_esc(job_title)}</strong>.</p>"
        + _kv("Reason", str(reason))
        + "<p>Consider re-engaging the waiting list for this role.</p>"
        + "<p>— The PUG HR system</p>"
    )
    html = _wrap(
        title="Offer declined",
        body_html=body,
        **_ctx(TPL_OFFER_DECLINED, ctx),
    )
    text = (
        f"{candidate_name} declined the offer for {job_title}.\n"
        f"Reason: {reason}\n"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_offer_joined(ctx: Dict[str, Any]) -> RenderedEmail:
    """Internal email to HR team when HR marks the candidate as joined."""
    candidate_name = ctx.get("candidate_name", "the candidate")
    job_title = ctx.get("job_title", "the role")
    joined_at = ctx.get("joined_at")
    subject = f"[PUG] Candidate joined — {candidate_name} ({job_title})"
    body = (
        f"<p>🎉 <strong>{_esc(candidate_name)}</strong> joined as "
        f"<strong>{_esc(job_title)}</strong>"
        + (f" on <strong>{_esc(str(joined_at))}</strong>" if joined_at else "")
        + ".</p>"
        + "<p>Recruitment status has been updated to <code>joined</code>.</p>"
        + "<p>— The PUG HR system</p>"
    )
    html = _wrap(
        title="Candidate joined",
        body_html=body,
        **_ctx(TPL_OFFER_JOINED, ctx),
    )
    text = (
        f"{candidate_name} joined as {job_title}"
        + (f" on {joined_at}" if joined_at else "")
        + ".\n"
    )
    return RenderedEmail(subject=subject, html=html, text=text)


def _r_contact_reply(ctx: Dict[str, Any]) -> RenderedEmail:
    """Branded HTML email for an admin reply on a contact ticket.

    Context keys (all optional except marked):
      * customer_name *
      * ticket_number *
      * reply_body *           — admin-typed text, line breaks preserved
      * admin_name             — used to sign the reply
      * original_subject       — surfaced in the subject + header
      * original_message       — included as a small quoted preview
      * support_email          — "reply directly to" mailbox
      * website_url            — footer link
      * brand_logo_url
      * email_footer_text
    """
    customer_name = ctx.get("customer_name") or "there"
    ticket_number = ctx.get("ticket_number") or ""
    reply_body = (ctx.get("reply_body") or "").strip()
    admin_name = ctx.get("admin_name") or "Paris United Group support"
    original_subject = (ctx.get("original_subject") or "your enquiry").strip()
    original_message = (ctx.get("original_message") or "").strip()
    support_email = ctx.get("support_email") or ""
    website_url = ctx.get("website_url") or ""

    title = "Reply from Paris United Group"
    # Subject is built by the caller (it needs the ticket marker
    # appended consistently); we still echo it here so the renderer
    # can be used standalone in tests / previews.
    if ticket_number:
        subject = f"Re: {original_subject} [{ticket_number}]"
    else:
        subject = f"Re: {original_subject}"

    ticket_chip = (
        f'<span style="display:inline-block;background:#f6f3eb;'
        f"border:1px solid #e4e0d6;border-radius:999px;padding:4px 10px;"
        f'font-size:11px;letter-spacing:0.04em;color:#61736b;'
        f'font-family:Inter,Arial,sans-serif;">Ticket {_esc(ticket_number)}</span>'
        if ticket_number
        else ""
    )

    reply_html_block = (
        '<div style="background:#ffffff;border:1px solid #e4e0d6;'
        "border-radius:8px;padding:18px 20px;margin:16px 0;line-height:1.6;"
        'font-size:14px;color:#17382f;white-space:pre-wrap;">'
        f"{_esc(reply_body)}"
        "</div>"
    )

    signature_block = (
        f'<p style="margin:0;padding:8px 0 0 0;color:#61736b;font-size:13px;">'
        f"— {_esc(admin_name)}<br />"
        f'<span style="color:#9a8f6e;">Paris United Group Holding</span></p>'
    )

    original_block = ""
    if original_message:
        original_block = (
            '<details style="margin-top:24px;color:#61736b;font-size:12px;">'
            "<summary style=\"cursor:pointer;font-weight:600;\">"
            "Show your original message</summary>"
            "<blockquote style=\"margin:8px 0 0;padding:8px 12px;"
            "border-left:2px solid #e4e0d6;background:#fafaf6;white-space:pre-wrap;"
            "font-size:12px;color:#61736b;\">"
            f"{_esc(original_message)}"
            "</blockquote></details>"
        )

    cta_text = "You can reply directly to this email to continue the conversation."
    if support_email:
        cta_block = (
            f'<p style="margin:16px 0 0 0;font-size:13px;color:#61736b;">'
            f"{_esc(cta_text)} Your reply will land back with our team at "
            f'<a href="mailto:{_esc(support_email)}" '
            f'style="color:#17382f;">{_esc(support_email)}</a>.'
            f"</p>"
        )
    else:
        cta_block = (
            f'<p style="margin:16px 0 0 0;font-size:13px;color:#61736b;">'
            f"{_esc(cta_text)}</p>"
        )

    body_html = (
        f'<p style="margin:0 0 8px 0;font-size:15px;">Hi {_esc(customer_name)},</p>'
        f'<p style="margin:0 0 4px 0;color:#61736b;font-size:13px;">'
        f"Regarding: <strong style=\"color:#17382f;\">{_esc(original_subject)}</strong>"
        f"</p>"
        f"{ticket_chip}"
        f"{reply_html_block}"
        f"{signature_block}"
        f"{cta_block}"
        f"{original_block}"
    )

    footer = ctx.get("email_footer_text")
    if not footer:
        bits = ["© Paris United Group Holding."]
        if support_email:
            bits.append(f"Support: {support_email}.")
        if website_url:
            bits.append(website_url)
        footer = " ".join(bits)

    html = _wrap(
        title=title,
        body_html=body_html,
        brand_logo_url=ctx.get("brand_logo_url"),
        footer_text=footer,
    )

    # Plain-text fallback. Keep it short — the html copy is the
    # primary surface, this is just for screen readers + clients
    # that strip HTML.
    text_lines = [
        f"Hi {customer_name},",
        "",
        f"Regarding: {original_subject}",
    ]
    if ticket_number:
        text_lines.append(f"Ticket: {ticket_number}")
    text_lines.extend(["", reply_body, "", f"— {admin_name}", "Paris United Group Holding", ""])
    text_lines.append(cta_text)
    if support_email:
        text_lines.append(f"Reply directly to {support_email}.")
    if original_message:
        text_lines.append("")
        text_lines.append("--- Your original message ---")
        text_lines.append(original_message)
    text = "\n".join(text_lines)

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
    # Phase 11
    TPL_INTERVIEW_FEEDBACK_SUBMITTED: _r_interview_feedback_submitted,
    TPL_OFFER_APPROVAL_REQUESTED: _r_offer_approval_requested,
    TPL_OFFER_APPROVED: _r_offer_approved,
    TPL_OFFER_ISSUED: _r_offer_issued,
    TPL_OFFER_ACCEPTED: _r_offer_accepted,
    TPL_OFFER_DECLINED: _r_offer_declined,
    TPL_OFFER_JOINED: _r_offer_joined,
    # Contact ticket
    TPL_CONTACT_REPLY: _r_contact_reply,
}


def available_template_keys() -> tuple[str, ...]:
    return tuple(sorted(_RENDERERS.keys()))

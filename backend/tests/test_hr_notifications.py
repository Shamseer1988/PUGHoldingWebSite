"""Tests for the HR notifications service + branded email templates.

We monkey-patch :meth:`EmailService._send` so the SMTP call is replaced
with an in-memory capture. This means tests run without any network.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

import pytest
from sqlalchemy.orm import Session

from app.models.email_settings import EmailSetting
from app.models.hr_ats import (
    APPROVAL_STATUS_APPROVED,
    EMAIL_LOG_FAILED,
    EMAIL_LOG_PENDING,
    EMAIL_LOG_SENT,
    EmailLog,
    JobOpening,
    PUBLISH_STATUS_PUBLISHED,
)
from app.services import hr_notifications, email_templates
from app.services.email import EmailService


@pytest.fixture
def stub_smtp(monkeypatch):
    """Capture every _send call so we never open a real SMTP socket."""
    sent: List[dict] = []

    def fake_send(msg, config):
        sent.append(
            {
                "subject": msg["Subject"],
                "to": msg["To"],
                "from": msg["From"],
                "host": config.host,
            }
        )

    monkeypatch.setattr(EmailService, "_send", staticmethod(fake_send))
    return sent


@pytest.fixture
def enabled_email_settings(db_session: Session) -> EmailSetting:
    setting = EmailService.get_or_create_settings(db_session)
    setting.email_enabled = True
    setting.smtp_host = "smtp.example.com"
    setting.smtp_port = 587
    setting.email_from = "hr@pug.example.com"
    setting.email_from_name = "PUG HR"
    setting.hr_notification_emails = ["manager1@pug.example.com", "manager2@pug.example.com"]
    setting.job_approval_email_enabled = True
    setting.candidate_email_enabled = True
    setting.interview_email_enabled = True
    db_session.commit()
    return setting


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def test_every_template_key_renders():
    """All declared templates must render without raising."""
    for key in email_templates.available_template_keys():
        out = email_templates.render(
            key,
            {
                "job_title": "Senior Engineer",
                "job_department": "Engineering",
                "job_company": "PUG Holding",
                "candidate_name": "John Doe",
                "actor_email": "manager@pug.example.com",
                "reason": "Insufficient details",
                "scheduled_at": "2026-06-01T10:00:00Z",
                "duration_minutes": 60,
                "mode": "online",
                "meeting_link": "https://meet.google.com/abc",
                "round_name": "Technical Round",
                "interviewer_name": "Jane Smith",
                "email_note": "Please be on time.",
            },
        )
        assert out.subject
        assert "<html" not in out.html  # we render fragments, not full doc
        assert out.text


def test_template_escapes_html_dangerous_input():
    out = email_templates.render(
        email_templates.TPL_JOB_APPROVED,
        {"job_title": "<script>alert(1)</script>"},
    )
    assert "<script>" not in out.html
    assert "&lt;script&gt;" in out.html


# ---------------------------------------------------------------------------
# send_notification core
# ---------------------------------------------------------------------------


def test_send_notification_logs_sent_status(
    db_session: Session, stub_smtp, enabled_email_settings
):
    log = hr_notifications.send_notification(
        db_session,
        template_key=email_templates.TPL_JOB_APPROVED,
        to_emails=["hr-mgr@example.com"],
        context={"job_title": "Test Role"},
        related_type="job_opening",
        related_id="42",
    )
    db_session.commit()

    assert log.status == EMAIL_LOG_SENT
    assert log.sent_at is not None
    assert log.to_emails == ["hr-mgr@example.com"]
    assert log.template_key == email_templates.TPL_JOB_APPROVED
    assert log.related_type == "job_opening"
    assert log.related_id == "42"

    persisted = db_session.get(EmailLog, log.id)
    assert persisted is not None
    assert persisted.status == EMAIL_LOG_SENT

    # SMTP stub recorded the send.
    assert len(stub_smtp) == 1
    assert "Test Role" in stub_smtp[0]["subject"]


def test_send_notification_marks_failed_when_no_recipients(
    db_session: Session, enabled_email_settings
):
    log = hr_notifications.send_notification(
        db_session,
        template_key=email_templates.TPL_JOB_APPROVED,
        to_emails=[],
        context={"job_title": "Test"},
    )
    db_session.commit()
    assert log.status == EMAIL_LOG_FAILED
    assert "No recipients" in (log.error_message or "")


def test_send_notification_respects_feature_flag(
    db_session: Session, stub_smtp, enabled_email_settings
):
    enabled_email_settings.job_approval_email_enabled = False
    db_session.commit()

    log = hr_notifications.send_notification(
        db_session,
        template_key=email_templates.TPL_JOB_APPROVED,
        to_emails=["hr@example.com"],
        context={"job_title": "Test"},
        check_feature_flag="job_approval_email_enabled",
    )
    db_session.commit()
    assert log.status == EMAIL_LOG_FAILED
    assert "Disabled by" in (log.error_message or "")
    # No SMTP send.
    assert stub_smtp == []


def test_send_notification_marks_failed_when_smtp_disabled(
    db_session: Session, stub_smtp
):
    # No EmailSetting → defaults → email_enabled=False
    setting = EmailService.get_or_create_settings(db_session)
    setting.email_enabled = False
    db_session.commit()

    log = hr_notifications.send_notification(
        db_session,
        template_key=email_templates.TPL_JOB_APPROVED,
        to_emails=["x@example.com"],
        context={"job_title": "Test"},
    )
    db_session.commit()
    assert log.status == EMAIL_LOG_FAILED
    assert stub_smtp == []


# ---------------------------------------------------------------------------
# Idempotency — short-window dedup
# ---------------------------------------------------------------------------
#
# Originally reported as: "career emails frequently sending to candidates
# and admin teams at the time of every server restart when running
# `py run.py`". Root cause: uvicorn --reload kills the worker mid-request
# while ``notify_*()`` is still inside SMTP send → browser auto-retries
# the POST → second worker re-fires the same notification → two
# emails per real event. Same shape applies to double-clicked admin
# buttons and any HTTP client with implicit retry-on-connection-close.


def test_send_notification_dedupes_repeated_calls_within_window(
    db_session: Session, stub_smtp, enabled_email_settings
):
    """A second call with the same (template, related_type, related_id)
    inside the dedup window must NOT trigger SMTP and must NOT
    create a second EmailLog row."""
    first = hr_notifications.send_notification(
        db_session,
        template_key=email_templates.TPL_JOB_APPROVED,
        to_emails=["candidate@example.com"],
        context={"job_title": "Backend Engineer"},
        related_type="job_opening",
        related_id="42",
    )
    db_session.commit()
    assert first.status == EMAIL_LOG_SENT
    assert len(stub_smtp) == 1

    second = hr_notifications.send_notification(
        db_session,
        template_key=email_templates.TPL_JOB_APPROVED,
        to_emails=["candidate@example.com"],
        context={"job_title": "Backend Engineer"},
        related_type="job_opening",
        related_id="42",
    )
    db_session.commit()

    # No new SMTP traffic. Same EmailLog row returned. Only one row
    # exists for this (template, related) tuple.
    assert len(stub_smtp) == 1
    assert second.id == first.id
    total = (
        db_session.query(EmailLog)
        .filter(
            EmailLog.template_key == email_templates.TPL_JOB_APPROVED,
            EmailLog.related_type == "job_opening",
            EmailLog.related_id == "42",
        )
        .count()
    )
    assert total == 1


def test_send_notification_allows_resend_after_window_expires(
    db_session: Session, stub_smtp, enabled_email_settings
):
    """Outside the dedup window a legitimate re-send (e.g. status
    flipped back-and-forth days later) must still fire."""
    first = hr_notifications.send_notification(
        db_session,
        template_key=email_templates.TPL_JOB_APPROVED,
        to_emails=["candidate@example.com"],
        context={"job_title": "Backend Engineer"},
        related_type="job_opening",
        related_id="7",
    )
    db_session.commit()
    # Backdate so the dedup-window query excludes the first row.
    first.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    db_session.commit()

    second = hr_notifications.send_notification(
        db_session,
        template_key=email_templates.TPL_JOB_APPROVED,
        to_emails=["candidate@example.com"],
        context={"job_title": "Backend Engineer"},
        related_type="job_opening",
        related_id="7",
    )
    db_session.commit()
    assert len(stub_smtp) == 2
    assert second.id != first.id


def test_send_notification_dedupe_scope_is_per_template_and_related(
    db_session: Session, stub_smtp, enabled_email_settings
):
    """Different template OR different related_id must still send —
    the dedup is a *tuple* match, not blanket suppression."""
    hr_notifications.send_notification(
        db_session,
        template_key=email_templates.TPL_JOB_APPROVED,
        to_emails=["a@example.com"],
        context={"job_title": "A"},
        related_type="job_opening",
        related_id="1",
    )
    # Same template, different related_id → fires.
    hr_notifications.send_notification(
        db_session,
        template_key=email_templates.TPL_JOB_APPROVED,
        to_emails=["b@example.com"],
        context={"job_title": "B"},
        related_type="job_opening",
        related_id="2",
    )
    # Different template, same related_id → fires.
    hr_notifications.send_notification(
        db_session,
        template_key=email_templates.TPL_JOB_PUBLISHED,
        to_emails=["c@example.com"],
        context={"job_title": "C"},
        related_type="job_opening",
        related_id="1",
    )
    db_session.commit()
    assert len(stub_smtp) == 3


def test_send_notification_without_related_id_never_dedupes(
    db_session: Session, stub_smtp, enabled_email_settings
):
    """Ad-hoc sends (test email, manual send) don't carry a
    related_id — they must always go through."""
    for _ in range(3):
        hr_notifications.send_notification(
            db_session,
            template_key=email_templates.TPL_JOB_APPROVED,
            to_emails=["adhoc@example.com"],
            context={"job_title": "Adhoc"},
        )
    db_session.commit()
    assert len(stub_smtp) == 3


def test_send_notification_dedupe_can_be_disabled(
    db_session: Session, stub_smtp, enabled_email_settings
):
    """Operator opt-out: ``dedupe_within_seconds=0`` restores the
    pre-fix behaviour for one-off integrations that genuinely need
    to fire the same notification twice in a row."""
    for _ in range(2):
        hr_notifications.send_notification(
            db_session,
            template_key=email_templates.TPL_JOB_APPROVED,
            to_emails=["candidate@example.com"],
            context={"job_title": "Backend"},
            related_type="job_opening",
            related_id="42",
            dedupe_within_seconds=0,
        )
    db_session.commit()
    assert len(stub_smtp) == 2


def test_send_notification_dedupes_against_pending_in_flight(
    db_session: Session, stub_smtp, enabled_email_settings
):
    """First call is interrupted (think uvicorn --reload mid-send) so
    it stays in status=pending forever. A retry within the window
    must NOT fire a fresh SMTP call — pending counts as "send in
    progress" for dedup purposes."""
    # Build the "interrupted" row directly: same shape send_notification
    # would have written, but stuck at pending without a successful
    # SMTP follow-up. This is what a worker-killed-mid-send leaves
    # behind in the table.
    stranded = EmailLog(
        scope="hr",
        template_key=email_templates.TPL_JOB_APPROVED,
        to_emails=["c@example.com"],
        status=EMAIL_LOG_PENDING,
        related_type="job_opening",
        related_id="99",
    )
    db_session.add(stranded)
    db_session.commit()

    # Now the retry hits — SMTP is healthy and would happily send a
    # second copy if dedup didn't catch the stranded pending row.
    second = hr_notifications.send_notification(
        db_session,
        template_key=email_templates.TPL_JOB_APPROVED,
        to_emails=["c@example.com"],
        context={"job_title": "Title"},
        related_type="job_opening",
        related_id="99",
    )
    db_session.commit()
    assert second.id == stranded.id
    # No SMTP traffic — the retry was suppressed.
    assert stub_smtp == []

"""Tests for the HR notifications service + branded email templates.

We monkey-patch :meth:`EmailService._send` so the SMTP call is replaced
with an in-memory capture. This means tests run without any network.
"""
from __future__ import annotations

from typing import List

import pytest
from sqlalchemy.orm import Session

from app.models.email_settings import EmailSetting
from app.models.hr_ats import (
    APPROVAL_STATUS_APPROVED,
    EMAIL_LOG_FAILED,
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

"""Scheduled report digests (Feature F4)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.models.hr_ats import ScheduledReport
from app.services.scheduled_reports import (
    dispatch_scheduled_report,
    is_due,
    render_report_html,
    render_report_text,
)
from app.services.hr_reports import Report


HR_LOGIN = "/api/v1/hr/auth/login"
BASE = "/api/v1/hr/scheduled-reports"


def _login(client: TestClient, email: str, password: str) -> dict:
    r = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# is_due
# ---------------------------------------------------------------------------


class TestIsDue:
    def test_never_run_is_always_due(self):
        assert is_due("daily", None) is True
        assert is_due("weekly", None) is True
        assert is_due("monthly", None) is True

    def test_daily_due_when_last_run_was_yesterday(self):
        now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        last = now - timedelta(days=1, minutes=1)
        assert is_due("daily", last, now=now) is True

    def test_daily_not_due_when_already_ran_today(self):
        now = datetime(2026, 6, 1, 18, 0, tzinfo=timezone.utc)
        last = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        assert is_due("daily", last, now=now) is False

    def test_weekly_due_after_new_iso_week(self):
        # 2026-06-01 is a Monday — week 23. last_run on previous Sun is
        # in week 22 -> due.
        now = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        last = datetime(2026, 5, 31, 9, 0, tzinfo=timezone.utc)
        assert is_due("weekly", last, now=now) is True

    def test_weekly_not_due_within_same_week(self):
        now = datetime(2026, 6, 4, 9, 0, tzinfo=timezone.utc)  # Thu
        last = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)  # Mon, same wk
        assert is_due("weekly", last, now=now) is False

    def test_monthly_due_in_new_calendar_month(self):
        now = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)
        last = datetime(2026, 6, 30, 9, 0, tzinfo=timezone.utc)
        assert is_due("monthly", last, now=now) is True

    def test_monthly_not_due_same_month(self):
        now = datetime(2026, 6, 28, 9, 0, tzinfo=timezone.utc)
        last = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        assert is_due("monthly", last, now=now) is False


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _stub_report() -> Report:
    return Report(
        type="demo",
        title="Demo report",
        description="For unit tests",
        generated_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        columns=["Candidate", "Status"],
        rows=[
            ["Jane Doe", "shortlisted"],
            ["John Roe", "rejected"],
        ],
        summary={"Total": 2},
    )


class TestRendering:
    def test_html_contains_headers_and_rows(self):
        html = render_report_html(_stub_report())
        assert "Demo report" in html
        assert "Candidate" in html
        assert "Jane Doe" in html
        # Special chars are escaped — the dataset doesn't include any,
        # but we sanity-check the helper still works.
        assert "<script>" not in html

    def test_html_escapes_dangerous_values(self):
        report = _stub_report()
        report.rows = [["<script>alert(1)</script>", "ok"]]
        html = render_report_html(report)
        assert "<script>alert(1)" not in html
        assert "&lt;script&gt;" in html

    def test_text_contains_summary_block(self):
        text = render_report_text(_stub_report())
        assert "Demo report" in text
        assert "Summary:" in text
        assert "Total: 2" in text


# ---------------------------------------------------------------------------
# Endpoint CRUD
# ---------------------------------------------------------------------------


class TestEndpoints:
    def test_anon_is_401(self, client: TestClient):
        assert client.get(BASE).status_code == 401

    def test_interviewer_is_403(self, client: TestClient, seed_auth):
        headers = _login(
            client, "interviewer@pug.example.com", seed_auth["password"]
        )
        assert client.get(BASE, headers=headers).status_code == 403

    def test_create_list_update_delete(
        self, client: TestClient, seed_auth, db_session
    ):
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        body = {
            "name": "Daily shortlist digest",
            "report_type": "shortlist",
            "frequency": "daily",
            "recipients": ["ops@example.com", "lead@example.com"],
            "params": {"location": "Doha"},
            "is_active": True,
        }
        r = client.post(BASE, headers=headers, json=body)
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["frequency"] == "daily"
        assert len(created["recipients"]) == 2
        sid = created["id"]

        listing = client.get(BASE, headers=headers).json()
        assert any(x["id"] == sid for x in listing)

        r = client.patch(
            f"{BASE}/{sid}", headers=headers, json={"frequency": "weekly"}
        )
        assert r.status_code == 200
        assert r.json()["frequency"] == "weekly"

        r = client.delete(f"{BASE}/{sid}", headers=headers)
        assert r.status_code == 204
        r = client.patch(f"{BASE}/{sid}", headers=headers, json={})
        assert r.status_code == 404

    def test_rejects_unknown_report_type(
        self, client: TestClient, seed_auth
    ):
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        r = client.post(
            BASE,
            headers=headers,
            json={
                "name": "Bogus",
                "report_type": "not_a_real_report",
                "frequency": "daily",
                "recipients": ["ops@example.com"],
            },
        )
        assert r.status_code == 422
        assert "Unknown report_type" in r.json()["detail"]

    def test_rejects_bad_frequency(self, client: TestClient, seed_auth):
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        r = client.post(
            BASE,
            headers=headers,
            json={
                "name": "Bad freq",
                "report_type": "shortlist",
                "frequency": "every_minute",
                "recipients": ["ops@example.com"],
            },
        )
        # Pydantic catches this before the endpoint validator.
        assert r.status_code == 422

    def test_requires_at_least_one_recipient(
        self, client: TestClient, seed_auth
    ):
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        r = client.post(
            BASE,
            headers=headers,
            json={
                "name": "No one",
                "report_type": "shortlist",
                "frequency": "daily",
                "recipients": [],
            },
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Dispatch + run-now
# ---------------------------------------------------------------------------


class TestDispatch:
    def test_run_now_stamps_metadata_even_when_email_unconfigured(
        self, client: TestClient, seed_auth, db_session, monkeypatch
    ):
        """The test env has no SMTP. Dispatch should still stamp
        last_run_at + last_run_status (failed) and not raise."""
        headers = _login(client, "hr@pug.example.com", seed_auth["password"])
        created = client.post(
            BASE,
            headers=headers,
            json={
                "name": "Run-me",
                "report_type": "shortlist",
                "frequency": "daily",
                "recipients": ["ops@example.com"],
            },
        ).json()
        sid = created["id"]

        # Patch the email service so the dispatcher exercises the
        # success path without actually opening a socket.
        sent_to: list[str] = []

        class _StubResult:
            status = "sent"

        def _fake_send(db, *, to_email, subject, body_text, body_html=None, reply_to=None):
            sent_to.append(to_email)
            return _StubResult()

        from app.services import email as email_mod

        monkeypatch.setattr(
            email_mod.EmailService, "send_simple", classmethod(lambda cls, *a, **k: _fake_send(*a, **k))
        )

        r = client.post(f"{BASE}/{sid}/run", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["delivered_count"] == 1
        assert sent_to == ["ops@example.com"]

        # Reload from DB and check the bookkeeping columns.
        db_session.expire_all()
        row = db_session.get(ScheduledReport, sid)
        assert row.last_run_at is not None
        assert row.last_run_status == "success"

"""HR-side ``/api/v1/hr/assessments`` endpoint coverage (Phase 2).

Locks the contract for the assessment-template + invite surface:

  * **CRUD**: create / list / get / patch / delete templates
  * **Questions**: add / patch / delete questions, with the
    "can't replace choices once an answer exists" lock
  * **Invites**: send, re-send (token rotates), cancel, fetch
  * **RBAC**: only ``hr:assessments:manage`` can write; ``view``
    is enough to read
  * **Validation**: ≥2 choices, ≥1 correct, etc.

The public candidate-facing flow (token verify / fetch / submit) is
covered in ``test_public_assessments.py``.
"""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_assessment import (
    Assessment,
    AssessmentAnswer,
    AssessmentInvite,
    AssessmentQuestion,
    AssessmentSubmission,
)
from app.models.hr_ats import Candidate, JobOpening


HR_LOGIN = "/api/v1/hr/auth/login"
BASE = "/api/v1/hr/assessments"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    r = client.post(HR_LOGIN, json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _login_manager(client: TestClient, password: str) -> dict[str, str]:
    return _login(client, "hr@pug.example.com", password)  # HR Manager


def _login_exec(client: TestClient, password: str) -> dict[str, str]:
    return _login(client, "hrexec@pug.example.com", password)


def _login_dept_mgr(client: TestClient, password: str) -> dict[str, str]:
    return _login(client, "deptmgr@pug.example.com", password)


def _login_interviewer(client: TestClient, password: str) -> dict[str, str]:
    return _login(client, "interviewer@pug.example.com", password)


def _seed_job(db: Session, *, slug: str = "qa-eng") -> JobOpening:
    job = JobOpening(
        slug=slug,
        title=f"Job {slug}",
        department="Engineering",
        company="PUG",
        location="Doha",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _seed_candidate(
    db: Session,
    *,
    email: str = "asm-cand@test.example",
    mobile: str | None = "+97455551234",
    dob: date | None = date(1990, 5, 15),
) -> Candidate:
    cand = Candidate(
        full_name="Asm Cand",
        email=email,
        mobile=mobile,
        date_of_birth=dob,
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return cand


def _basic_create_payload(job_id: int) -> dict:
    """Minimal valid create payload — one question, two choices, one
    marked correct."""
    return {
        "job_opening_id": job_id,
        "title": "Sample MCQ",
        "instructions": "Pick the right answers.",
        "time_limit_minutes": 30,
        "passing_score": 1,
        "questions": [
            {
                "text": "Is 2 + 2 = 4?",
                "points": 1,
                "choices": [
                    {"text": "Yes", "order_index": 0, "is_correct": True},
                    {"text": "No", "order_index": 1, "is_correct": False},
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreate:
    def test_create_with_inline_questions(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session)
        headers = _login_manager(client, seed_auth["password"])
        r = client.post(BASE, headers=headers, json=_basic_create_payload(job.id))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["title"] == "Sample MCQ"
        assert body["job_opening_id"] == job.id
        assert len(body["questions"]) == 1
        assert body["total_points"] == 1
        assert body["invite_count"] == 0
        # Answer key visible on the HR side.
        assert any(c["is_correct"] for c in body["questions"][0]["choices"])

    def test_create_rejects_question_with_one_choice(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-bad")
        headers = _login_manager(client, seed_auth["password"])
        payload = _basic_create_payload(job.id)
        payload["questions"][0]["choices"] = [
            {"text": "Solo", "is_correct": True}
        ]
        r = client.post(BASE, headers=headers, json=payload)
        # Pydantic min_length on choices catches this first → 422.
        assert r.status_code == 422

    def test_create_rejects_question_without_correct_choice(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-allwrong")
        headers = _login_manager(client, seed_auth["password"])
        payload = _basic_create_payload(job.id)
        for c in payload["questions"][0]["choices"]:
            c["is_correct"] = False
        r = client.post(BASE, headers=headers, json=payload)
        assert r.status_code == 400
        assert "correct" in r.json()["detail"].lower()

    def test_create_rejects_unknown_job(
        self, client: TestClient, seed_auth
    ):
        headers = _login_manager(client, seed_auth["password"])
        payload = _basic_create_payload(999_999)
        r = client.post(BASE, headers=headers, json=payload)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


class TestRead:
    def test_list_filters_by_job(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        j1 = _seed_job(db_session, slug="qa-list-1")
        j2 = _seed_job(db_session, slug="qa-list-2")
        headers = _login_manager(client, seed_auth["password"])
        for j in (j1, j2):
            r = client.post(BASE, headers=headers, json=_basic_create_payload(j.id))
            assert r.status_code == 201

        r = client.get(f"{BASE}?job_opening_id={j1.id}", headers=headers)
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["job_opening_id"] == j1.id

    def test_get_by_id(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-get")
        headers = _login_manager(client, seed_auth["password"])
        created = client.post(
            BASE, headers=headers, json=_basic_create_payload(job.id)
        ).json()
        r = client.get(f"{BASE}/{created['id']}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    def test_get_404_on_missing(
        self, client: TestClient, seed_auth
    ):
        headers = _login_manager(client, seed_auth["password"])
        r = client.get(f"{BASE}/999999", headers=headers)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Update + delete
# ---------------------------------------------------------------------------


class TestUpdateDelete:
    def test_patch_title(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-patch")
        headers = _login_manager(client, seed_auth["password"])
        created = client.post(
            BASE, headers=headers, json=_basic_create_payload(job.id)
        ).json()
        r = client.patch(
            f"{BASE}/{created['id']}", headers=headers, json={"title": "Renamed"}
        )
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Renamed"

    def test_delete_when_no_submissions(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-del-clean")
        headers = _login_manager(client, seed_auth["password"])
        created = client.post(
            BASE, headers=headers, json=_basic_create_payload(job.id)
        ).json()
        r = client.delete(f"{BASE}/{created['id']}", headers=headers)
        assert r.status_code == 204

    def test_delete_locked_when_submission_exists(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-del-locked")
        headers = _login_manager(client, seed_auth["password"])
        created = client.post(
            BASE, headers=headers, json=_basic_create_payload(job.id)
        ).json()
        assessment_id = created["id"]

        # Stage a fake submission against the assessment.
        cand = _seed_candidate(db_session, email="del@x.test")
        invite = AssessmentInvite(
            assessment_id=assessment_id,
            candidate_id=cand.id,
            token="t-locked-1",
            status="submitted",
        )
        db_session.add(invite)
        db_session.commit()
        db_session.add(
            AssessmentSubmission(invite_id=invite.id, score=1, max_score=1)
        )
        db_session.commit()

        r = client.delete(f"{BASE}/{assessment_id}", headers=headers)
        assert r.status_code == 409
        assert "submitted" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Question helpers
# ---------------------------------------------------------------------------


class TestQuestions:
    def test_add_question_picks_next_order_index(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-addq")
        headers = _login_manager(client, seed_auth["password"])
        created = client.post(
            BASE, headers=headers, json=_basic_create_payload(job.id)
        ).json()
        aid = created["id"]

        body = {
            "text": "Second question",
            "points": 2,
            "choices": [
                {"text": "A", "is_correct": True},
                {"text": "B", "is_correct": False},
            ],
        }
        r = client.post(f"{BASE}/{aid}/questions", headers=headers, json=body)
        assert r.status_code == 201
        # First was order_index 0; the new one should land at 1.
        assert r.json()["order_index"] == 1

    def test_update_question_replaces_choices(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-qupdate")
        headers = _login_manager(client, seed_auth["password"])
        created = client.post(
            BASE, headers=headers, json=_basic_create_payload(job.id)
        ).json()
        aid = created["id"]
        qid = created["questions"][0]["id"]

        new_choices = [
            {"text": "Foo", "is_correct": True},
            {"text": "Bar", "is_correct": False},
            {"text": "Baz", "is_correct": False},
        ]
        r = client.patch(
            f"{BASE}/{aid}/questions/{qid}",
            headers=headers,
            json={"choices": new_choices},
        )
        assert r.status_code == 200, r.text
        choices = r.json()["choices"]
        assert {c["text"] for c in choices} == {"Foo", "Bar", "Baz"}

    def test_update_question_locked_once_answer_exists(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-qlocked")
        headers = _login_manager(client, seed_auth["password"])
        created = client.post(
            BASE, headers=headers, json=_basic_create_payload(job.id)
        ).json()
        aid = created["id"]
        qid = created["questions"][0]["id"]

        # Stage an invite + submission + answer for this question.
        cand = _seed_candidate(db_session, email="qlock@x.test")
        invite = AssessmentInvite(
            assessment_id=aid,
            candidate_id=cand.id,
            token="t-qlock-1",
            status="opened",
        )
        db_session.add(invite)
        db_session.commit()
        sub = AssessmentSubmission(invite_id=invite.id)
        db_session.add(sub)
        db_session.commit()
        db_session.add(
            AssessmentAnswer(
                submission_id=sub.id, question_id=qid, selected_choice_ids=[]
            )
        )
        db_session.commit()

        r = client.patch(
            f"{BASE}/{aid}/questions/{qid}",
            headers=headers,
            json={
                "choices": [
                    {"text": "X", "is_correct": True},
                    {"text": "Y", "is_correct": False},
                ]
            },
        )
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# Invites
# ---------------------------------------------------------------------------


class TestInvites:
    def test_send_then_resend_rotates_token(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-inv-send")
        headers = _login_manager(client, seed_auth["password"])
        created = client.post(
            BASE, headers=headers, json=_basic_create_payload(job.id)
        ).json()
        aid = created["id"]
        cand = _seed_candidate(db_session, email="send@x.test")

        r1 = client.post(
            f"{BASE}/{aid}/invites",
            headers=headers,
            json={"candidate_id": cand.id},
        )
        assert r1.status_code == 201, r1.text
        invite1 = r1.json()
        assert invite1["status"] == "sent"
        token1 = invite1["token"]

        # Re-send rotates the token (so the previous link dies) and
        # the existing row is reused (unique constraint on
        # (candidate_id, assessment_id)).
        r2 = client.post(
            f"{BASE}/{aid}/invites",
            headers=headers,
            json={"candidate_id": cand.id},
        )
        assert r2.status_code == 201
        invite2 = r2.json()
        assert invite2["id"] == invite1["id"]
        assert invite2["token"] != token1

    def test_cannot_send_inactive_assessment(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-inv-inactive")
        headers = _login_manager(client, seed_auth["password"])
        created = client.post(
            BASE, headers=headers, json=_basic_create_payload(job.id)
        ).json()
        aid = created["id"]
        # Deactivate the template.
        client.patch(f"{BASE}/{aid}", headers=headers, json={"is_active": False})

        cand = _seed_candidate(db_session, email="inactive@x.test")
        r = client.post(
            f"{BASE}/{aid}/invites",
            headers=headers,
            json={"candidate_id": cand.id},
        )
        assert r.status_code == 400
        assert "inactive" in r.json()["detail"].lower()

    def test_cancel_invite(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-inv-cancel")
        headers = _login_manager(client, seed_auth["password"])
        created = client.post(
            BASE, headers=headers, json=_basic_create_payload(job.id)
        ).json()
        aid = created["id"]
        cand = _seed_candidate(db_session, email="cancel@x.test")

        invite = client.post(
            f"{BASE}/{aid}/invites",
            headers=headers,
            json={"candidate_id": cand.id},
        ).json()

        r = client.post(
            f"{BASE}/invites/{invite['id']}/cancel", headers=headers
        )
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"

    def test_get_invite_404_on_missing(
        self, client: TestClient, seed_auth
    ):
        headers = _login_manager(client, seed_auth["password"])
        r = client.get(f"{BASE}/invites/999999", headers=headers)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


class TestRBAC:
    def test_executive_can_manage(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-rbac-exec")
        headers = _login_exec(client, seed_auth["password"])
        r = client.post(BASE, headers=headers, json=_basic_create_payload(job.id))
        assert r.status_code == 201

    def test_dept_mgr_can_read_but_not_write(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-rbac-dept")
        mgr_headers = _login_manager(client, seed_auth["password"])
        created = client.post(
            BASE, headers=mgr_headers, json=_basic_create_payload(job.id)
        ).json()

        dept_headers = _login_dept_mgr(client, seed_auth["password"])

        # Read: OK
        r = client.get(f"{BASE}/{created['id']}", headers=dept_headers)
        assert r.status_code == 200

        # Write: 403
        r = client.patch(
            f"{BASE}/{created['id']}",
            headers=dept_headers,
            json={"title": "Hax"},
        )
        assert r.status_code == 403

    def test_interviewer_cannot_read(
        self, client: TestClient, seed_auth, db_session: Session
    ):
        job = _seed_job(db_session, slug="qa-rbac-int")
        mgr_headers = _login_manager(client, seed_auth["password"])
        created = client.post(
            BASE, headers=mgr_headers, json=_basic_create_payload(job.id)
        ).json()

        int_headers = _login_interviewer(client, seed_auth["password"])
        r = client.get(f"{BASE}/{created['id']}", headers=int_headers)
        assert r.status_code == 403

    def test_unauthenticated_rejected(self, client: TestClient):
        r = client.get(BASE)
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Email template
# ---------------------------------------------------------------------------


class TestAssessmentInviteEmail:
    def test_renders_subject_link_and_clock(self):
        from app.services.email_templates import (
            render,
            TPL_ASSESSMENT_INVITE,
        )

        out = render(
            TPL_ASSESSMENT_INVITE,
            {
                "candidate_name": "Jane Doe",
                "job_title": "Senior Engineer",
                "assessment_title": "Coding MCQ",
                "assessment_url": "http://localhost:3000/assessment/tok-abc",
                "time_limit_minutes": 30,
            },
        )
        assert "Senior Engineer" in out.subject
        assert "Coding MCQ" in out.html
        assert "/assessment/tok-abc" in out.html
        assert "30 minutes" in out.html
        # Plain-text fallback carries the same essentials.
        assert "tok-abc" in out.text
        assert "Coding MCQ" in out.text

    def test_renders_without_optional_fields(self):
        from app.services.email_templates import (
            render,
            TPL_ASSESSMENT_INVITE,
        )

        # Bare minimum — clock + expiry omitted.
        out = render(
            TPL_ASSESSMENT_INVITE,
            {
                "candidate_name": "Anon",
                "assessment_url": "http://example/assessment/t",
            },
        )
        assert "Anon" in out.html
        assert "this role" in out.html  # fallback when job_title missing

"""Candidate-facing ``/api/v1/assessments`` endpoint coverage (Phase 2).

Locks the contract for the public token + form surface:

  * **verify**: identity check accepts any of DOB / email / mobile,
    case- and whitespace-insensitive on email/mobile, mints a
    session JWT, transitions the invite to ``opened``, creates the
    submission row.
  * **fetch (/me)**: returns the form bundle **without** the
    ``is_correct`` flag — the answer key never leaves the server.
  * **submit (/me/submit)**: persists answers, scores all-or-
    nothing, flips invite + submission to ``submitted``, returns the
    candidate-visible ack.
  * **Token rotation invalidates old session JWTs.**
  * **Cancelled / expired / already-submitted invites all 4xx.**
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr_assessment import (
    Assessment,
    AssessmentChoice,
    AssessmentInvite,
    AssessmentQuestion,
)
from app.models.hr_ats import Candidate, JobOpening


VERIFY = "/api/v1/assessments/{token}/verify"
FETCH = "/api/v1/assessments/me"
SUBMIT = "/api/v1/assessments/me/submit"


# ---------------------------------------------------------------------------
# Fixtures (built inline rather than in conftest — the assessment
# scaffolding is heavy and only this file uses it).
# ---------------------------------------------------------------------------


def _seed_template(
    db_session: Session,
    *,
    title: str = "Smoke",
    time_limit_minutes: int | None = None,
    passing_score: int | None = None,
) -> Assessment:
    job = JobOpening(
        slug=f"job-{title.lower().replace(' ', '-')}",
        title="Job",
        department="Eng",
        company="PUG",
        location="Doha",
    )
    db_session.add(job)
    db_session.flush()

    assessment = Assessment(
        job_opening_id=job.id,
        title=title,
        time_limit_minutes=time_limit_minutes,
        passing_score=passing_score,
        is_active=True,
    )
    db_session.add(assessment)
    db_session.flush()

    # Two questions, the first all-or-nothing, the second with two
    # correct choices to exercise the set-equality scoring.
    q1 = AssessmentQuestion(
        assessment_id=assessment.id,
        text="Q1?",
        order_index=0,
        points=1,
        is_required=False,
    )
    db_session.add(q1)
    db_session.flush()
    db_session.add_all(
        [
            AssessmentChoice(
                question_id=q1.id, text="right", order_index=0, is_correct=True
            ),
            AssessmentChoice(
                question_id=q1.id, text="wrong", order_index=1, is_correct=False
            ),
        ]
    )
    q2 = AssessmentQuestion(
        assessment_id=assessment.id,
        text="Q2?",
        order_index=1,
        points=2,
        is_required=False,
    )
    db_session.add(q2)
    db_session.flush()
    db_session.add_all(
        [
            AssessmentChoice(
                question_id=q2.id, text="a", order_index=0, is_correct=True
            ),
            AssessmentChoice(
                question_id=q2.id, text="b", order_index=1, is_correct=True
            ),
            AssessmentChoice(
                question_id=q2.id, text="c", order_index=2, is_correct=False
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(assessment)
    return assessment


def _seed_candidate(
    db_session: Session,
    *,
    email: str = "cand@test.example",
    mobile: str | None = "+97455551234",
    dob: date | None = date(1990, 5, 15),
    full_name: str = "Pub Cand",
) -> Candidate:
    cand = Candidate(
        full_name=full_name,
        email=email,
        mobile=mobile,
        date_of_birth=dob,
    )
    db_session.add(cand)
    db_session.commit()
    db_session.refresh(cand)
    return cand


def _seed_invite(
    db_session: Session,
    assessment: Assessment,
    candidate: Candidate,
    *,
    status: str = "sent",
    token: str = "tok-public-1",
    expires_at: datetime | None = None,
) -> AssessmentInvite:
    invite = AssessmentInvite(
        assessment_id=assessment.id,
        candidate_id=candidate.id,
        token=token,
        status=status,
        expires_at=expires_at,
    )
    db_session.add(invite)
    db_session.commit()
    db_session.refresh(invite)
    return invite


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


class TestVerify:
    def test_verify_with_email(
        self, client: TestClient, db_session: Session
    ):
        a = _seed_template(db_session, title="Email Verify")
        c = _seed_candidate(
            db_session, email="ev@test.example", mobile=None, dob=None
        )
        invite = _seed_invite(db_session, a, c, token="email-1")

        r = client.post(
            VERIFY.format(token=invite.token),
            json={"identity_value": "EV@Test.Example"},  # mixed case
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["matched_field"] == "email"
        assert body["session_token"]
        assert body["submit_deadline"] is None  # no time limit
        # Invite + submission state updated.
        db_session.refresh(invite)
        assert invite.status == "opened"
        assert invite.opened_at is not None
        assert invite.verified_identity_field == "email"

    def test_verify_with_mobile_normalised(
        self, client: TestClient, db_session: Session
    ):
        a = _seed_template(db_session, title="Mobile Verify")
        c = _seed_candidate(
            db_session,
            email="m1@test.example",
            mobile="+97455551234",
            dob=None,
        )
        invite = _seed_invite(db_session, a, c, token="mobile-1")

        # Candidate types with spaces and country code variations.
        r = client.post(
            VERIFY.format(token=invite.token),
            json={"identity_value": "+974 5555 1234"},
        )
        assert r.status_code == 200
        assert r.json()["matched_field"] == "mobile"

    def test_verify_with_dob(
        self, client: TestClient, db_session: Session
    ):
        a = _seed_template(db_session, title="DOB Verify")
        c = _seed_candidate(
            db_session, email="dob@test.example", mobile=None,
            dob=date(1990, 5, 15),
        )
        invite = _seed_invite(db_session, a, c, token="dob-1")

        for value in ("1990-05-15", "15/05/1990"):
            r = client.post(
                VERIFY.format(token=invite.token),
                json={"identity_value": value},
            )
            # The first hit opens the submission; subsequent verify
            # calls also succeed because open_submission is idempotent.
            assert r.status_code == 200, r.text
            assert r.json()["matched_field"] == "dob"

    def test_verify_wrong_value_rejected(
        self, client: TestClient, db_session: Session
    ):
        a = _seed_template(db_session, title="Wrong Verify")
        c = _seed_candidate(
            db_session, email="x@test.example", mobile=None, dob=None,
        )
        invite = _seed_invite(db_session, a, c, token="wrong-1")

        r = client.post(
            VERIFY.format(token=invite.token),
            json={"identity_value": "not-the-email@x.test"},
        )
        assert r.status_code == 401
        # Invite NOT transitioned by a failed verify.
        db_session.refresh(invite)
        assert invite.status == "sent"

    def test_verify_unknown_token_404(
        self, client: TestClient
    ):
        r = client.post(
            VERIFY.format(token="no-such-token"),
            json={"identity_value": "anything"},
        )
        assert r.status_code == 404

    def test_verify_cancelled_invite_410(
        self, client: TestClient, db_session: Session
    ):
        a = _seed_template(db_session, title="Cancel Verify")
        c = _seed_candidate(db_session, email="cx@test.example", mobile=None, dob=None)
        invite = _seed_invite(
            db_session, a, c, token="cancel-1", status="cancelled"
        )
        r = client.post(
            VERIFY.format(token=invite.token),
            json={"identity_value": "cx@test.example"},
        )
        assert r.status_code == 410

    def test_verify_expired_invite_410(
        self, client: TestClient, db_session: Session
    ):
        a = _seed_template(db_session, title="Expired Verify")
        c = _seed_candidate(db_session, email="ex@test.example", mobile=None, dob=None)
        invite = _seed_invite(
            db_session,
            a,
            c,
            token="exp-1",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        r = client.post(
            VERIFY.format(token=invite.token),
            json={"identity_value": "ex@test.example"},
        )
        assert r.status_code == 410


# ---------------------------------------------------------------------------
# fetch + answer-key omission
# ---------------------------------------------------------------------------


def _verified_session(
    client: TestClient, db_session: Session, *, title: str = "Fetch", **kw
) -> tuple[Assessment, AssessmentInvite, str, Candidate]:
    """Stand up a template + candidate + invite, verify, return the
    session token so the test only needs to call /me + /submit."""
    a = _seed_template(db_session, title=title, **kw)
    c = _seed_candidate(
        db_session, email=f"{title.lower()}@test.example", mobile=None, dob=None,
    )
    invite = _seed_invite(db_session, a, c, token=f"tok-{title.lower()}")
    r = client.post(
        VERIFY.format(token=invite.token),
        json={"identity_value": c.email},
    )
    assert r.status_code == 200, r.text
    return a, invite, r.json()["session_token"], c


class TestFetch:
    def test_fetch_omits_is_correct(
        self, client: TestClient, db_session: Session
    ):
        a, _i, session_token, _c = _verified_session(
            client, db_session, title="Hide Key"
        )
        r = client.get(
            FETCH, headers={"Authorization": f"Bearer {session_token}"}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["title"] == "Hide Key"
        assert len(body["questions"]) == 2
        # ``is_correct`` MUST NOT appear anywhere in the choice payload.
        for q in body["questions"]:
            for ch in q["choices"]:
                assert "is_correct" not in ch

    def test_fetch_without_session_token_401(
        self, client: TestClient
    ):
        r = client.get(FETCH)
        assert r.status_code == 401

    def test_fetch_with_garbage_token_401(self, client: TestClient):
        r = client.get(FETCH, headers={"Authorization": "Bearer abc.def.ghi"})
        assert r.status_code == 401

    def test_fetch_after_token_rotation_401(
        self, client: TestClient, db_session: Session
    ):
        a, invite, session_token, _c = _verified_session(
            client, db_session, title="Rotate Sess"
        )
        # Simulate HR re-issuing the invite — token changes,
        # stashed session JWT goes stale.
        invite.token = "rotated-token-1"
        db_session.commit()
        r = client.get(
            FETCH, headers={"Authorization": f"Bearer {session_token}"}
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# submit + scoring
# ---------------------------------------------------------------------------


def _correct_choice_ids(template: Assessment) -> dict[int, list[int]]:
    """Map question_id → list of correct choice IDs."""
    out: dict[int, list[int]] = {}
    for q in template.questions:
        out[q.id] = [c.id for c in q.choices if c.is_correct]
    return out


class TestSubmit:
    def test_submit_all_correct(
        self, client: TestClient, db_session: Session
    ):
        a, invite, session_token, _c = _verified_session(
            client, db_session, title="All Correct", passing_score=2
        )
        db_session.refresh(a)
        keys = _correct_choice_ids(a)
        answers = [
            {"question_id": qid, "selected_choice_ids": cids}
            for qid, cids in keys.items()
        ]
        r = client.post(
            SUBMIT,
            headers={"Authorization": f"Bearer {session_token}"},
            json={"answers": answers},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Q1=1pt + Q2=2pt = 3 max; both correct → 3
        assert body["score"] == 3
        assert body["max_score"] == 3
        assert body["passed"] is True

        db_session.refresh(invite)
        assert invite.status == "submitted"
        assert invite.submitted_at is not None

    def test_submit_partial_subset_is_wrong(
        self, client: TestClient, db_session: Session
    ):
        """Q2 has two correct choices ({a, b}); picking only ``a`` is
        wrong under all-or-nothing scoring."""
        a, _i, session_token, _c = _verified_session(
            client, db_session, title="Partial", passing_score=2
        )
        db_session.refresh(a)
        keys = _correct_choice_ids(a)
        q1, q2 = list(keys.keys())
        answers = [
            {"question_id": q1, "selected_choice_ids": keys[q1]},  # right
            {"question_id": q2, "selected_choice_ids": keys[q2][:1]},  # short
        ]
        r = client.post(
            SUBMIT,
            headers={"Authorization": f"Bearer {session_token}"},
            json={"answers": answers},
        )
        body = r.json()
        assert body["score"] == 1  # only Q1
        assert body["max_score"] == 3
        assert body["passed"] is False

    def test_submit_with_extra_choice_is_wrong(
        self, client: TestClient, db_session: Session
    ):
        """Picking the correct set PLUS a distractor still scores 0."""
        a, _i, session_token, _c = _verified_session(
            client, db_session, title="Extra", passing_score=2
        )
        db_session.refresh(a)
        keys = _correct_choice_ids(a)
        q1, q2 = list(keys.keys())
        # Find the wrong choice on q2.
        q2_obj = next(q for q in a.questions if q.id == q2)
        wrong_q2 = next(c.id for c in q2_obj.choices if not c.is_correct)
        answers = [
            {"question_id": q1, "selected_choice_ids": keys[q1]},
            {
                "question_id": q2,
                "selected_choice_ids": keys[q2] + [wrong_q2],
            },
        ]
        r = client.post(
            SUBMIT,
            headers={"Authorization": f"Bearer {session_token}"},
            json={"answers": answers},
        )
        body = r.json()
        assert body["score"] == 1  # Q1 right, Q2 over-picked → wrong
        assert body["passed"] is False

    def test_resubmit_after_finalised_409(
        self, client: TestClient, db_session: Session
    ):
        a, _i, session_token, _c = _verified_session(
            client, db_session, title="Resubmit"
        )
        r1 = client.post(
            SUBMIT,
            headers={"Authorization": f"Bearer {session_token}"},
            json={"answers": []},
        )
        assert r1.status_code == 200
        r2 = client.post(
            SUBMIT,
            headers={"Authorization": f"Bearer {session_token}"},
            json={"answers": []},
        )
        assert r2.status_code == 409

    def test_passing_score_none_leaves_passed_null(
        self, client: TestClient, db_session: Session
    ):
        a, _i, session_token, _c = _verified_session(
            client, db_session, title="No Pass Score"
        )
        # passing_score not set; passed should be None on the ack.
        r = client.post(
            SUBMIT,
            headers={"Authorization": f"Bearer {session_token}"},
            json={"answers": []},
        )
        assert r.status_code == 200
        assert r.json()["passed"] is None

"""Business logic for the HR Phase 2 assessment workflow.

Five concerns, all in one module because they share enough state
that splitting would mean threading the same Session through three
files for no benefit:

1. **Template CRUD** — :func:`create_assessment`,
   :func:`update_assessment`, :func:`delete_assessment`,
   :func:`list_assessments`, :func:`get_assessment`, plus the
   per-question helpers.
2. **Invite issuance** — :func:`create_or_refresh_invite` and
   :func:`mark_invite_sent` / :func:`cancel_invite`. Tokens are
   generated with ``secrets.token_urlsafe(32)`` (~43 chars of
   url-safe entropy) — long enough that brute force is not a
   meaningful threat.
3. **Token lookup + identity check** — :func:`lookup_invite_by_token`
   and :func:`verify_identity` for the public surface.
4. **Submission lifecycle** — :func:`open_submission`,
   :func:`record_answer`, :func:`finalise_submission`.
5. **Scoring** — :func:`score_submission` runs after submit and
   writes ``score`` / ``max_score`` / ``passed`` plus per-answer
   ``is_correct`` denormalisation.

Everything that mutates state takes the Session and *does not*
commit — callers (endpoints) own the transaction so an endpoint
that does multiple service calls can rollback cleanly. The one
exception is :func:`open_submission` which commits once the row
is built (otherwise the candidate's identity check + submission
creation would have to be in the same transaction across a token
boundary, which is awkward to thread through the endpoint layer).
"""
from __future__ import annotations

import secrets
from datetime import date, datetime, timezone
from typing import Iterable, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.hr_assessment import (
    CHOICE_QUESTION_TYPES,
    QUESTION_ATTACHMENT,
    QUESTION_CHECKBOX,
    QUESTION_DATE,
    QUESTION_LONG_TEXT,
    QUESTION_SHORT_TEXT,
    Assessment,
    AssessmentAnswer,
    AssessmentChoice,
    AssessmentInvite,
    AssessmentQuestion,
    AssessmentSubmission,
)
from app.models.hr_ats import Candidate, CandidateJobApplication, JobOpening
from app.schemas.hr_assessment import (
    AssessmentChoiceCreate,
    AssessmentCreate,
    AssessmentQuestionCreate,
    AssessmentQuestionUpdate,
    AssessmentUpdate,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class AssessmentError(Exception):
    """Base for any service-level error worth surfacing as a 4xx."""


class AssessmentValidationError(AssessmentError):
    """400 — caller supplied a bad payload (no correct choice, etc.)."""


class AssessmentNotFound(AssessmentError):
    """404 — referenced row doesn't exist."""


class AssessmentLocked(AssessmentError):
    """409 — the operation is refused because the candidate already
    submitted, or the template already has submissions tied to it
    that a destructive edit would orphan."""


class InviteAlreadyOpen(AssessmentError):
    """409 — verify called on an invite that's already past ``opened``."""


class InviteExpired(AssessmentError):
    """410 — expires_at has passed."""


# ---------------------------------------------------------------------------
# Helpers — validation
# ---------------------------------------------------------------------------


def _validate_choices(choices: Iterable[AssessmentChoiceCreate]) -> None:
    items = list(choices)
    if len(items) < 2:
        raise AssessmentValidationError(
            "Each question needs at least two choices."
        )
    if not any(c.is_correct for c in items):
        raise AssessmentValidationError(
            "Each question needs at least one correct choice."
        )


def _validate_question_payload(
    qtype: str, choices: Optional[Iterable[AssessmentChoiceCreate]]
) -> None:
    """Type-aware validation: single/multi-choice need a valid choice list;
    every other type must not carry choices."""
    items = list(choices or [])
    if qtype in CHOICE_QUESTION_TYPES:
        _validate_choices(items)
    elif items:
        raise AssessmentValidationError(
            f"'{qtype}' questions do not take choices."
        )


def _normalise_answer_value(qtype: str, value: Optional[dict]) -> dict:
    """Coerce a candidate's typed answer into the canonical value shape."""
    value = value or {}
    if qtype in (QUESTION_SHORT_TEXT, QUESTION_LONG_TEXT):
        return {"text": str(value.get("text", "")).strip()}
    if qtype == QUESTION_DATE:
        raw = value.get("date")
        return {"date": raw.strip() if isinstance(raw, str) else raw}
    if qtype == QUESTION_CHECKBOX:
        return {"checked": bool(value.get("checked"))}
    # attachment (reserved) / unknown — persist as-is.
    return dict(value)


def _answer_is_empty(qtype: str, answer: Optional["AssessmentAnswer"]) -> bool:
    """Whether a required question was left effectively blank."""
    if answer is None:
        return True
    if qtype in CHOICE_QUESTION_TYPES:
        return not (answer.selected_choice_ids or [])
    v = answer.value or {}
    if qtype in (QUESTION_SHORT_TEXT, QUESTION_LONG_TEXT):
        return not str(v.get("text", "")).strip()
    if qtype == QUESTION_DATE:
        return not v.get("date")
    if qtype == QUESTION_CHECKBOX:
        return not bool(v.get("checked"))
    if qtype == QUESTION_ATTACHMENT:
        return not v.get("attachment_id")
    return False


def _materialise_choices(
    question: AssessmentQuestion, choices: Iterable[AssessmentChoiceCreate]
) -> None:
    """Build child rows on a (possibly new) question, in order."""
    for idx, src in enumerate(choices):
        # Honour an explicit order_index if supplied; otherwise tie-break
        # by the order the caller listed them. Keeps the HR UI simple
        # — a drag-and-drop reorder maps cleanly to the list order.
        question.choices.append(
            AssessmentChoice(
                text=src.text,
                order_index=src.order_index if src.order_index else idx,
                is_correct=src.is_correct,
            )
        )


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------


def create_assessment(
    db: Session, *, payload: AssessmentCreate, actor_id: Optional[int]
) -> Assessment:
    """Create a new template (with optional inline questions)."""
    job = db.get(JobOpening, payload.job_opening_id)
    if job is None:
        raise AssessmentNotFound(
            f"Job opening {payload.job_opening_id} not found."
        )

    assessment = Assessment(
        job_opening_id=payload.job_opening_id,
        title=payload.title,
        instructions=payload.instructions,
        time_limit_minutes=payload.time_limit_minutes,
        passing_score=payload.passing_score,
        is_active=payload.is_active,
        created_by_id=actor_id,
    )

    if payload.questions:
        for q_idx, q_payload in enumerate(payload.questions):
            _validate_question_payload(q_payload.type, q_payload.choices)
            question = AssessmentQuestion(
                text=q_payload.text,
                type=q_payload.type,
                help_text=q_payload.help_text,
                is_required=q_payload.is_required,
                config=q_payload.config or {},
                order_index=q_payload.order_index or q_idx,
                points=q_payload.points,
            )
            if q_payload.type in CHOICE_QUESTION_TYPES and q_payload.choices:
                _materialise_choices(question, q_payload.choices)
            assessment.questions.append(question)

    db.add(assessment)
    db.flush()  # populate ids without committing
    return assessment


def update_assessment(
    db: Session, *, assessment_id: int, payload: AssessmentUpdate
) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise AssessmentNotFound(
            f"Assessment {assessment_id} not found."
        )
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(assessment, field, value)
    db.flush()
    return assessment


def delete_assessment(db: Session, *, assessment_id: int) -> None:
    """Hard delete a template *only if no submissions exist*.

    We don't soft-delete on cascade because the FK chain already
    handles it — invites + submissions + answers cascade from the
    template. But if HR ran any candidate through the form, we
    refuse so the submission history isn't lost; HR can flip
    ``is_active`` to ``False`` instead.
    """
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise AssessmentNotFound(
            f"Assessment {assessment_id} not found."
        )
    has_submissions = db.execute(
        select(func.count(AssessmentSubmission.id))
        .join(AssessmentInvite)
        .where(AssessmentInvite.assessment_id == assessment_id)
    ).scalar_one()
    if has_submissions:
        raise AssessmentLocked(
            "Cannot delete — candidates have already submitted. "
            "Set the template inactive instead."
        )
    db.delete(assessment)
    db.flush()


def list_assessments(
    db: Session,
    *,
    job_opening_id: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> list[Assessment]:
    stmt = select(Assessment).order_by(Assessment.created_at.desc())
    if job_opening_id is not None:
        stmt = stmt.where(Assessment.job_opening_id == job_opening_id)
    if is_active is not None:
        stmt = stmt.where(Assessment.is_active.is_(is_active))
    return list(db.execute(stmt).scalars().all())


def get_assessment(db: Session, assessment_id: int) -> Assessment:
    stmt = (
        select(Assessment)
        .where(Assessment.id == assessment_id)
        .options(selectinload(Assessment.questions).selectinload(AssessmentQuestion.choices))
    )
    assessment = db.execute(stmt).scalar_one_or_none()
    if assessment is None:
        raise AssessmentNotFound(f"Assessment {assessment_id} not found.")
    return assessment


# ---------------------------------------------------------------------------
# Question helpers
# ---------------------------------------------------------------------------


def add_question(
    db: Session,
    *,
    assessment_id: int,
    payload: AssessmentQuestionCreate,
) -> AssessmentQuestion:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise AssessmentNotFound(f"Assessment {assessment_id} not found.")
    _validate_question_payload(payload.type, payload.choices)
    # Default order_index to "next" if caller didn't pin one.
    next_order = db.execute(
        select(func.coalesce(func.max(AssessmentQuestion.order_index), -1) + 1)
        .where(AssessmentQuestion.assessment_id == assessment_id)
    ).scalar_one()
    question = AssessmentQuestion(
        assessment_id=assessment_id,
        text=payload.text,
        type=payload.type,
        help_text=payload.help_text,
        is_required=payload.is_required,
        config=payload.config or {},
        order_index=payload.order_index or next_order,
        points=payload.points,
    )
    if payload.type in CHOICE_QUESTION_TYPES and payload.choices:
        _materialise_choices(question, payload.choices)
    db.add(question)
    db.flush()
    return question


def update_question(
    db: Session,
    *,
    question_id: int,
    payload: AssessmentQuestionUpdate,
) -> AssessmentQuestion:
    question = db.get(AssessmentQuestion, question_id)
    if question is None:
        raise AssessmentNotFound(f"Question {question_id} not found.")

    # Effective type after this update (caller may be switching it).
    new_type = payload.type or question.type

    # If the template has submissions tied to it, lock destructive
    # edits — changing the answer key after the fact would silently
    # rescore past attempts on next view.
    if payload.choices is not None and _question_has_answers(db, question_id):
        raise AssessmentLocked(
            "Cannot replace choices — at least one candidate has "
            "already answered this question. Add a new question "
            "instead."
        )
    if payload.choices is not None:
        _validate_question_payload(new_type, payload.choices)

    data = payload.model_dump(exclude_unset=True, exclude={"choices"})
    # config is NOT NULL — an explicit null clears to {}.
    if "config" in data and data["config"] is None:
        data["config"] = {}
    for field, value in data.items():
        setattr(question, field, value)

    if payload.choices is not None:
        # Replace the whole set — cascade-delete handles the orphans.
        question.choices.clear()
        db.flush()
        if new_type in CHOICE_QUESTION_TYPES:
            _materialise_choices(question, payload.choices)
    elif payload.type is not None and new_type not in CHOICE_QUESTION_TYPES:
        # Switched to a non-choice type — drop any stale choices.
        if question.choices:
            question.choices.clear()

    db.flush()
    return question


def delete_question(db: Session, *, question_id: int) -> None:
    question = db.get(AssessmentQuestion, question_id)
    if question is None:
        raise AssessmentNotFound(f"Question {question_id} not found.")
    if _question_has_answers(db, question_id):
        raise AssessmentLocked(
            "Cannot delete — at least one candidate has already "
            "answered this question."
        )
    db.delete(question)
    db.flush()


def _question_has_answers(db: Session, question_id: int) -> bool:
    return bool(
        db.execute(
            select(AssessmentAnswer.id).where(
                AssessmentAnswer.question_id == question_id
            ).limit(1)
        ).first()
    )


# ---------------------------------------------------------------------------
# Counts (used to enrich AssessmentRead / AssessmentSummary)
# ---------------------------------------------------------------------------


def assessment_counts(
    db: Session, assessment_id: int
) -> Tuple[int, int, int, int]:
    """(question_count, total_points, invite_count, submission_count)."""
    q_row = db.execute(
        select(
            func.count(AssessmentQuestion.id),
            func.coalesce(func.sum(AssessmentQuestion.points), 0),
        ).where(AssessmentQuestion.assessment_id == assessment_id)
    ).one()
    invite_count = db.execute(
        select(func.count(AssessmentInvite.id)).where(
            AssessmentInvite.assessment_id == assessment_id
        )
    ).scalar_one()
    submission_count = db.execute(
        select(func.count(AssessmentSubmission.id))
        .join(AssessmentInvite)
        .where(AssessmentInvite.assessment_id == assessment_id)
    ).scalar_one()
    return q_row[0], int(q_row[1] or 0), invite_count, submission_count


# ---------------------------------------------------------------------------
# Invites
# ---------------------------------------------------------------------------


def create_or_refresh_invite(
    db: Session,
    *,
    assessment_id: int,
    candidate_id: int,
    application_id: Optional[int],
    sent_by_id: Optional[int],
    expires_at: Optional[datetime] = None,
) -> AssessmentInvite:
    """Create the invite, or refresh an existing one to a fresh token.

    Re-sends bump the existing row (per the unique constraint on
    ``candidate_id`` + ``assessment_id``). If the existing invite is
    already in a terminal state (submitted / cancelled), refuse —
    HR should cancel + manually re-issue rather than overwrite a
    finished attempt.
    """
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise AssessmentNotFound(f"Assessment {assessment_id} not found.")
    if not assessment.is_active:
        raise AssessmentValidationError(
            "Cannot send an inactive assessment template."
        )

    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise AssessmentNotFound(f"Candidate {candidate_id} not found.")

    existing = db.execute(
        select(AssessmentInvite).where(
            AssessmentInvite.candidate_id == candidate_id,
            AssessmentInvite.assessment_id == assessment_id,
        )
    ).scalar_one_or_none()

    if existing is not None and existing.status in ("submitted", "cancelled"):
        raise AssessmentLocked(
            f"Existing invite is {existing.status}; cancel + re-issue manually."
        )

    if existing is not None:
        existing.token = _new_token()
        existing.status = "pending"
        existing.sent_at = None
        existing.opened_at = None
        existing.submitted_at = None
        existing.verified_identity_field = None
        existing.expires_at = expires_at
        existing.sent_by_id = sent_by_id
        # Wipe the (incomplete) submission, if any.
        if existing.submission is not None:
            db.delete(existing.submission)
        db.flush()
        return existing

    invite = AssessmentInvite(
        assessment_id=assessment_id,
        candidate_id=candidate_id,
        application_id=application_id,
        token=_new_token(),
        status="pending",
        expires_at=expires_at,
        sent_by_id=sent_by_id,
    )
    db.add(invite)
    db.flush()
    return invite


def mark_invite_sent(db: Session, invite_id: int) -> AssessmentInvite:
    invite = db.get(AssessmentInvite, invite_id)
    if invite is None:
        raise AssessmentNotFound(f"Invite {invite_id} not found.")
    invite.status = "sent"
    invite.sent_at = datetime.now(timezone.utc)
    db.flush()
    return invite


def cancel_invite(db: Session, invite_id: int) -> AssessmentInvite:
    invite = db.get(AssessmentInvite, invite_id)
    if invite is None:
        raise AssessmentNotFound(f"Invite {invite_id} not found.")
    if invite.status == "submitted":
        raise AssessmentLocked(
            "Cannot cancel — candidate has already submitted."
        )
    invite.status = "cancelled"
    db.flush()
    return invite


def _new_token() -> str:
    """URL-safe token. ``token_urlsafe(32)`` yields ~43 chars."""
    return secrets.token_urlsafe(32)


def as_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Force a datetime to be tz-aware (assume UTC for naive).

    SQLite (test backend) drops tzinfo on round-trip, so an
    ``expires_at`` written as tz-aware comes back naive. Postgres
    keeps the tz. Coercing here means service-level comparisons
    work uniformly on both backends without each call site having
    to deal with it.
    """
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Token lookup + identity verification (public surface helpers)
# ---------------------------------------------------------------------------


def lookup_invite_by_token(
    db: Session, token: str
) -> Tuple[AssessmentInvite, Candidate, Assessment]:
    """Return (invite, candidate, assessment) or raise NotFound."""
    invite = db.execute(
        select(AssessmentInvite).where(AssessmentInvite.token == token)
    ).scalar_one_or_none()
    if invite is None:
        raise AssessmentNotFound("Invite not found for this link.")
    candidate = db.get(Candidate, invite.candidate_id)
    assessment = db.get(Assessment, invite.assessment_id)
    if candidate is None or assessment is None:
        # Either side gone → treat as a dead link rather than 500.
        raise AssessmentNotFound("Invite references a missing record.")
    return invite, candidate, assessment


def verify_identity(
    invite: AssessmentInvite, candidate: Candidate, value: str
) -> Optional[str]:
    """Return the matched field name (``dob`` / ``email`` / ``mobile``)
    or None if no match.

    Comparison is case- and whitespace-insensitive for email/mobile so
    a candidate typing in different casing or with a leading ``+`` on
    the country code isn't bounced. DOB is matched on the ISO date
    (``YYYY-MM-DD``) — same format as the public application form."""
    if not value:
        return None
    stripped = value.strip()

    if (
        candidate.email
        and stripped.lower() == candidate.email.lower()
    ):
        return "email"

    if candidate.mobile:
        if _normalise_mobile(stripped) == _normalise_mobile(candidate.mobile):
            return "mobile"

    if candidate.date_of_birth is not None:
        if _parse_dob(stripped) == candidate.date_of_birth:
            return "dob"

    return None


def _normalise_mobile(value: str) -> str:
    """Strip spaces / dashes / parentheses; keep leading ``+``."""
    keep = []
    for ch in value:
        if ch.isdigit() or ch == "+":
            keep.append(ch)
    return "".join(keep)


def _parse_dob(value: str) -> Optional[date]:
    """Tolerate the two formats the public form might emit
    (``YYYY-MM-DD`` and ``DD/MM/YYYY``)."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Submission lifecycle + scoring
# ---------------------------------------------------------------------------


def open_submission(
    db: Session,
    *,
    invite: AssessmentInvite,
    matched_field: str,
) -> AssessmentSubmission:
    """Flip the invite to ``opened`` and create the submission shell.

    Re-entry is allowed — if a submission already exists (candidate
    refreshed the page mid-test), return the existing one untouched
    so the clock isn't reset.
    """
    now = datetime.now(timezone.utc)
    expires = as_aware_utc(invite.expires_at)
    if expires is not None and now > expires:
        raise InviteExpired("This assessment link has expired.")
    if invite.status == "submitted":
        raise InviteAlreadyOpen("This assessment has already been submitted.")
    if invite.status == "cancelled":
        raise AssessmentLocked("This invite has been cancelled.")

    if invite.submission is not None:
        return invite.submission

    invite.status = "opened"
    invite.opened_at = now
    invite.verified_identity_field = matched_field

    submission = AssessmentSubmission(invite_id=invite.id, started_at=now)
    db.add(submission)
    db.flush()
    db.commit()
    return submission


def finalise_submission(
    db: Session,
    *,
    submission: AssessmentSubmission,
    answers: list,  # list[PublicAnswerSubmit] — typed loosely to avoid the import dependency
) -> AssessmentSubmission:
    """Upsert each (submission, question) answer, then score the
    whole submission and flip the invite to ``submitted``."""
    invite = submission.invite

    if invite.status == "submitted":
        raise AssessmentLocked("Already submitted.")
    expires = as_aware_utc(invite.expires_at)
    if expires is not None and datetime.now(timezone.utc) > expires:
        raise InviteExpired("Submission window has closed.")

    # Load the canonical question/choice graph once so we don't
    # round-trip for every answer.
    questions = (
        db.execute(
            select(AssessmentQuestion)
            .where(AssessmentQuestion.assessment_id == invite.assessment_id)
            .options(selectinload(AssessmentQuestion.choices))
        )
        .scalars()
        .all()
    )
    questions_by_id = {q.id: q for q in questions}

    # Drop any prior answer rows on the same submission — the public
    # endpoint POSTs the full answer set, not a diff.
    db.execute(
        AssessmentAnswer.__table__.delete().where(
            AssessmentAnswer.submission_id == submission.id
        )
    )

    new_answers: list[AssessmentAnswer] = []
    for payload in answers:
        question = questions_by_id.get(payload.question_id)
        if question is None:
            # Silently ignore unknown question IDs rather than 4xx —
            # a stale browser tab from before a question got removed
            # shouldn't lose the candidate's other answers.
            continue
        if question.type in CHOICE_QUESTION_TYPES:
            # Filter selected choices to ones that actually belong to this
            # question (defends against a client sending arbitrary IDs).
            valid_choice_ids = {c.id for c in question.choices}
            cleaned = [
                cid
                for cid in payload.selected_choice_ids
                if cid in valid_choice_ids
            ]
            answer = AssessmentAnswer(
                submission_id=submission.id,
                question_id=question.id,
                selected_choice_ids=cleaned,
            )
        else:
            answer = AssessmentAnswer(
                submission_id=submission.id,
                question_id=question.id,
                selected_choice_ids=[],
                value=_normalise_answer_value(question.type, payload.value),
            )
        new_answers.append(answer)
        db.add(answer)

    # Required-field validation. Raising here rolls the endpoint's
    # transaction back, so the answer-wipe above is undone and the
    # candidate's prior answers survive.
    answers_by_q = {a.question_id: a for a in new_answers}
    for q in questions:
        if q.is_required and _answer_is_empty(q.type, answers_by_q.get(q.id)):
            raise AssessmentValidationError(f"'{q.text[:60]}' is required.")

    db.flush()

    score_submission(db, submission=submission, questions=questions)

    now = datetime.now(timezone.utc)
    submission.submitted_at = now
    invite.status = "submitted"
    invite.submitted_at = now
    db.flush()
    return submission


def score_submission(
    db: Session,
    *,
    submission: AssessmentSubmission,
    questions: Optional[list] = None,
) -> None:
    """All-or-nothing MCQ-multi scoring.

    A question is "correct" iff the candidate's selected-choice set
    EXACTLY equals the set of choices marked ``is_correct``. Partial
    credit is out of scope for v1 (the requirements doc explicitly
    flags it as contentious)."""
    if questions is None:
        questions = (
            db.execute(
                select(AssessmentQuestion)
                .where(AssessmentQuestion.assessment_id == submission.invite.assessment_id)
                .options(selectinload(AssessmentQuestion.choices))
            )
            .scalars()
            .all()
        )

    # Only choice questions are auto-graded; text/date/checkbox/attachment
    # are manual-review (objective 0 until HR sets a score override) and
    # are excluded from the objective max so "score / max" reads as the
    # auto-gradable portion.
    choice_questions = [
        q for q in questions if q.type in CHOICE_QUESTION_TYPES
    ]
    correct_sets = {
        q.id: {c.id for c in q.choices if c.is_correct}
        for q in choice_questions
    }
    points_by_q = {q.id: q.points for q in choice_questions}

    answers = (
        db.execute(
            select(AssessmentAnswer).where(
                AssessmentAnswer.submission_id == submission.id
            )
        )
        .scalars()
        .all()
    )

    score = 0
    for ans in answers:
        if ans.question_id not in correct_sets:
            # Manual-review question — leave is_correct NULL.
            ans.is_correct = None
            continue
        expected = correct_sets[ans.question_id]
        chosen = set(ans.selected_choice_ids or [])
        is_correct = chosen == expected
        ans.is_correct = is_correct
        if is_correct:
            score += points_by_q.get(ans.question_id, 0)

    max_score = sum(points_by_q.values())
    submission.score = score
    submission.max_score = max_score

    template = db.get(Assessment, submission.invite.assessment_id)
    if template is not None and template.passing_score is not None:
        submission.passed = score >= template.passing_score
    else:
        submission.passed = None

    db.flush()


__all__ = [
    # Exceptions
    "AssessmentError",
    "AssessmentValidationError",
    "AssessmentNotFound",
    "AssessmentLocked",
    "InviteAlreadyOpen",
    "InviteExpired",
    # Template CRUD
    "create_assessment",
    "update_assessment",
    "delete_assessment",
    "list_assessments",
    "get_assessment",
    "assessment_counts",
    # Questions
    "add_question",
    "update_question",
    "delete_question",
    # Invites
    "create_or_refresh_invite",
    "mark_invite_sent",
    "cancel_invite",
    # Public helpers
    "lookup_invite_by_token",
    "verify_identity",
    # Submission lifecycle
    "open_submission",
    "finalise_submission",
    "score_submission",
]

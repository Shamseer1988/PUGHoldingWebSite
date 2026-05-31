"""HR Phase 2 — candidate assessment workflow models.

Six tables, all prefixed ``hr_assessment_``:

* ``Assessment`` — a reusable template attached to a :class:`JobOpening`.
  Holds the title, instructions, time-limit and passing score.
* ``AssessmentQuestion`` — an MCQ-multi question on the template.
  ``order_index`` controls render order; ``points`` is per-question
  weight (default 1).
* ``AssessmentChoice`` — a single answer choice. ``is_correct`` flags
  which subset of choices make up the "correct" answer for the
  question (we score MCQ-multi as all-or-nothing on day 1 — partial
  credit is contentious and out-of-scope).
* ``AssessmentInvite`` — issued once per :class:`CandidateJobApplication`.
  Carries the URL-safe token, the lifecycle status (pending → sent →
  opened → submitted | expired | cancelled), and the issue / expiry
  timestamps. The token is the only secret the candidate needs to
  reach their assessment; identity verification on first open uses
  any of DOB / email / mobile that match the candidate's row.
* ``AssessmentSubmission`` — one row per invite that progressed to a
  finished assessment. Records start time, submit time, raw and
  scaled scores so HR can sort by performance directly.
* ``AssessmentAnswer`` — the candidate's selected choice IDs for a
  single question (JSON array), plus a denormalised ``is_correct``
  flag set at scoring time so HR detail views don't have to re-run
  the scoring math on every page load.

Cascade rules:
  * Deleting a JobOpening cascades to its Assessment (templates die
    with the job — orphaned templates can't be reused without a job
    anyway).
  * Deleting an Assessment cascades to its questions, choices, and
    all invites/submissions/answers underneath.
  * Deleting a CandidateJobApplication sets ``application_id`` on
    invites to NULL so the audit trail survives (the candidate's
    submission still tells HR what happened, even if the parent
    application row was archived).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


# ---------------------------------------------------------------------------
# Status enums (kept as module-level tuples so the CHECK constraints + the
# Python code share one source of truth).
# ---------------------------------------------------------------------------

INVITE_STATUSES = (
    "pending",
    "sent",
    "opened",
    "submitted",
    "expired",
    "cancelled",
)


# Question types (multi-field assessment engine). ``multi_choice`` is the
# original MCQ-multi; every legacy question backfills to it. ``attachment``
# is reserved (the candidate file-upload UI ships in a follow-up) but kept
# in the enum so the type is already valid.
QUESTION_SHORT_TEXT = "short_text"
QUESTION_LONG_TEXT = "long_text"
QUESTION_DATE = "date"
QUESTION_CHECKBOX = "checkbox"
QUESTION_SINGLE_CHOICE = "single_choice"
QUESTION_MULTI_CHOICE = "multi_choice"
QUESTION_ATTACHMENT = "attachment"
QUESTION_TYPES = (
    QUESTION_SHORT_TEXT,
    QUESTION_LONG_TEXT,
    QUESTION_DATE,
    QUESTION_CHECKBOX,
    QUESTION_SINGLE_CHOICE,
    QUESTION_MULTI_CHOICE,
    QUESTION_ATTACHMENT,
)
# Types scored automatically (choice set-equality). Everything else is
# manual review — objective score 0 until HR sets an override.
CHOICE_QUESTION_TYPES = (QUESTION_SINGLE_CHOICE, QUESTION_MULTI_CHOICE)

# HR review lifecycle on a submission.
REVIEW_PENDING = "pending"
REVIEW_IN_REVIEW = "in_review"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"
REVIEW_REQUIRES_REVISION = "requires_revision"
REVIEW_STATUSES = (
    REVIEW_PENDING,
    REVIEW_IN_REVIEW,
    REVIEW_APPROVED,
    REVIEW_REJECTED,
    REVIEW_REQUIRES_REVISION,
)

# Audit actions written to ``hr_assessment_review_events``.
REVIEW_ACTION_DRAFT_SAVED = "draft_saved"
REVIEW_ACTION_APPROVED_ADVANCED = "approved_advanced"
REVIEW_ACTION_REJECTED = "rejected"
REVIEW_ACTION_CHANGES_REQUESTED = "changes_requested"
REVIEW_ACTION_SCORE_OVERRIDDEN = "score_overridden"
REVIEW_ACTIONS = (
    REVIEW_ACTION_DRAFT_SAVED,
    REVIEW_ACTION_APPROVED_ADVANCED,
    REVIEW_ACTION_REJECTED,
    REVIEW_ACTION_CHANGES_REQUESTED,
    REVIEW_ACTION_SCORE_OVERRIDDEN,
)


def _enum_in_clause(column: str, allowed: tuple[str, ...]) -> str:
    """Build a portable ``column IN (...)`` CHECK clause.

    Matches the helper hr_ats.py uses so the generated DDL looks
    identical to the rest of the schema.
    """
    quoted = ", ".join(f"'{v}'" for v in allowed)
    return f"{column} IN ({quoted})"


# ---------------------------------------------------------------------------
# Assessment template
# ---------------------------------------------------------------------------


class Assessment(Base, TimestampMixin):
    """A reusable MCQ-multi assessment template attached to a job."""

    __tablename__ = "hr_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_opening_id: Mapped[int] = mapped_column(
        ForeignKey("hr_job_openings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text)

    # When set, the candidate must submit within this many minutes of
    # the moment they first verify identity (i.e. when the invite
    # transitions to ``opened``). None = no clock.
    time_limit_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    # Candidates need >= this many points (sum of fully-correct
    # questions' points) to pass. None = pass/fail not tracked.
    passing_score: Mapped[Optional[int]] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    created_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    questions: Mapped[List["AssessmentQuestion"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="AssessmentQuestion.order_index",
        lazy="selectin",
    )
    invites: Mapped[List["AssessmentInvite"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
    )


class AssessmentQuestion(Base, TimestampMixin):
    """A single MCQ-multi question on a template."""

    __tablename__ = "hr_assessment_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("hr_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)
    # One of QUESTION_TYPES. Defaults to multi_choice so every legacy row
    # (and any insert that predates the builder's type selector) stays a
    # valid MCQ-multi.
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=QUESTION_MULTI_CHOICE,
        server_default=QUESTION_MULTI_CHOICE,
    )
    help_text: Mapped[Optional[str]] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # Type-specific options: min_length/max_length (text), min_date/max_date
    # (date), placeholder, accepted_mime_types/max_file_size_mb (attachment).
    # Choices live in their own table, not here.
    config: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    points: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    assessment: Mapped[Assessment] = relationship(back_populates="questions")
    choices: Mapped[List["AssessmentChoice"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="AssessmentChoice.order_index",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            _enum_in_clause("type", QUESTION_TYPES),
            name="ck_hr_assessment_questions_type",
        ),
    )


class AssessmentChoice(Base):
    """One choice on an MCQ-multi question.

    No TimestampMixin — choices are content of their parent question
    and don't have an independent edit history worth surfacing.
    """

    __tablename__ = "hr_assessment_choices"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("hr_assessment_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_correct: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    question: Mapped[AssessmentQuestion] = relationship(back_populates="choices")


# ---------------------------------------------------------------------------
# Per-candidate invite + submission
# ---------------------------------------------------------------------------


class AssessmentInvite(Base, TimestampMixin):
    """A tokenised invitation for one candidate to take one assessment.

    Lifecycle: pending → sent → opened → submitted.  ``expired`` and
    ``cancelled`` are terminal escape hatches. The candidate-facing
    URL is ``/assessment/{token}``; ``token`` is a 32-char URL-safe
    string generated via ``secrets.token_urlsafe`` at insert time.
    """

    __tablename__ = "hr_assessment_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("hr_assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("hr_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # ON DELETE SET NULL so an archived application leaves the
    # submission trail intact — HR can still answer "did this person
    # ever pass our screening" months after the application row is
    # tidied away.
    application_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("hr_candidate_job_applications.id", ondelete="SET NULL"),
        index=True,
    )

    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )

    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # The identity field the candidate verified with on open
    # (``dob`` | ``email`` | ``mobile``) — captured for audit so HR
    # can prove which credential the candidate produced.
    verified_identity_field: Mapped[Optional[str]] = mapped_column(String(16))

    # Who pushed Send / re-sent. SET NULL so an HR user leaving the
    # company doesn't break the invite row.
    sent_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    assessment: Mapped[Assessment] = relationship(back_populates="invites")
    submission: Mapped[Optional["AssessmentSubmission"]] = relationship(
        back_populates="invite",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        # At most one open invite per (candidate, assessment) — re-sends
        # bump the existing row rather than spawning duplicates. HR can
        # cancel and re-issue when they need a fresh attempt.
        UniqueConstraint(
            "candidate_id", "assessment_id",
            name="uq_hr_assessment_invites_candidate_assessment",
        ),
        CheckConstraint(
            _enum_in_clause("status", INVITE_STATUSES),
            name="ck_hr_assessment_invites_status",
        ),
    )


class AssessmentSubmission(Base, TimestampMixin):
    """A completed (or in-progress) submission for one invite."""

    __tablename__ = "hr_assessment_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    invite_id: Mapped[int] = mapped_column(
        ForeignKey("hr_assessment_invites.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Raw score = sum of points for fully-correct questions.
    # Max score = sum of points across all questions on the template
    # at submission time (snapshotted so later template edits don't
    # rewrite history).
    score: Mapped[Optional[int]] = mapped_column(Integer)
    max_score: Mapped[Optional[int]] = mapped_column(Integer)

    # Convenience denormalisation so HR list views can colour pass/
    # fail without a join. NULL until ``submitted_at`` is set.
    passed: Mapped[Optional[bool]] = mapped_column(Boolean)

    # HR review lifecycle (one of REVIEW_STATUSES). ``pending`` until an
    # executive opens the review screen.
    review_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=REVIEW_PENDING,
        server_default=REVIEW_PENDING,
        index=True,
    )
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    reviewer_overall_comment: Mapped[Optional[str]] = mapped_column(Text)
    # When set, overrides the objective auto-score as the final score.
    reviewer_score_override: Mapped[Optional[int]] = mapped_column(Integer)

    invite: Mapped[AssessmentInvite] = relationship(back_populates="submission")
    answers: Mapped[List["AssessmentAnswer"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    review_events: Mapped[List["AssessmentReviewEvent"]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="AssessmentReviewEvent.created_at",
        lazy="selectin",
    )


class AssessmentAnswer(Base):
    """The candidate's chosen choice-ids for a single question."""

    __tablename__ = "hr_assessment_answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("hr_assessment_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("hr_assessment_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # JSON array of choice IDs the candidate ticked. Empty list = the
    # candidate left the question blank. Stored as JSON (not a
    # join table) because the answer is opaque to anything except
    # the scoring routine — no need to query "which questions did
    # anyone pick choice X for" across submissions.
    selected_choice_ids: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )

    # Typed answer payload for non-MCQ questions. Exactly one of
    # selected_choice_ids (non-empty) or value (non-null) is populated,
    # enforced in the service layer. Shapes by question type:
    #   short_text/long_text -> {"text": "..."}
    #   date                 -> {"date": "2026-05-31"}
    #   checkbox             -> {"checked": true}
    #   single_choice        -> {"choice_id": 42}
    #   attachment           -> {"attachment_id": 17}  (reserved)
    value: Mapped[Optional[dict]] = mapped_column(JSON)

    # Set by the auto-scorer at submit time. NULL means "not scored
    # yet" — relevant during the brief window between insert and the
    # scoring pass running. Always NULL for manual-review (non-choice)
    # question types.
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Per-question HR review (set on the review screen). NULL until an
    # executive marks the answer pass/fail / leaves a note.
    reviewer_passed: Mapped[Optional[bool]] = mapped_column(Boolean)
    reviewer_note: Mapped[Optional[str]] = mapped_column(Text)

    submission: Mapped[AssessmentSubmission] = relationship(back_populates="answers")

    __table_args__ = (
        # One answer per (submission, question). The candidate can edit
        # their choice as they go through the form; the backend upserts
        # against this constraint at submit time.
        UniqueConstraint(
            "submission_id", "question_id",
            name="uq_hr_assessment_answers_submission_question",
        ),
    )


class AssessmentReviewEvent(Base):
    """Audit trail of HR review actions on a submission.

    One row per draft-save / approve+advance / reject / changes-requested
    / score-override, surfaced in both the submission's history panel and
    the candidate's unified Activity tab.
    """

    __tablename__ = "hr_assessment_review_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("hr_assessment_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    # Application status either side of an approve+advance / reject, for a
    # readable audit ("advanced from technical_interview to final_interview").
    from_status: Mapped[Optional[str]] = mapped_column(String(40))
    to_status: Mapped[Optional[str]] = mapped_column(String(40))
    note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    submission: Mapped[AssessmentSubmission] = relationship(
        back_populates="review_events"
    )

    __table_args__ = (
        CheckConstraint(
            _enum_in_clause("action", REVIEW_ACTIONS),
            name="ck_hr_assessment_review_events_action",
        ),
    )


__all__ = [
    "INVITE_STATUSES",
    "QUESTION_TYPES",
    "CHOICE_QUESTION_TYPES",
    "QUESTION_SHORT_TEXT",
    "QUESTION_LONG_TEXT",
    "QUESTION_DATE",
    "QUESTION_CHECKBOX",
    "QUESTION_SINGLE_CHOICE",
    "QUESTION_MULTI_CHOICE",
    "QUESTION_ATTACHMENT",
    "REVIEW_STATUSES",
    "REVIEW_PENDING",
    "REVIEW_IN_REVIEW",
    "REVIEW_APPROVED",
    "REVIEW_REJECTED",
    "REVIEW_REQUIRES_REVISION",
    "REVIEW_ACTIONS",
    "REVIEW_ACTION_DRAFT_SAVED",
    "REVIEW_ACTION_APPROVED_ADVANCED",
    "REVIEW_ACTION_REJECTED",
    "REVIEW_ACTION_CHANGES_REQUESTED",
    "REVIEW_ACTION_SCORE_OVERRIDDEN",
    "Assessment",
    "AssessmentQuestion",
    "AssessmentChoice",
    "AssessmentInvite",
    "AssessmentSubmission",
    "AssessmentAnswer",
    "AssessmentReviewEvent",
]

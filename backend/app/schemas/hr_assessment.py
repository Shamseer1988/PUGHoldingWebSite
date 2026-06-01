"""Pydantic schemas for the HR Phase 2 assessment workflow.

Three audiences eat from this module:

* **HR write**: ``AssessmentCreate`` / ``AssessmentUpdate``,
  ``AssessmentQuestionCreate`` / ``AssessmentQuestionUpdate``, etc.
  These accept the full template definition, including which
  choices are correct.
* **HR read**: ``AssessmentRead`` (nested questions + choices with
  the ``is_correct`` flag visible). ``AssessmentSubmissionRead``
  shows the candidate's answers next to the answer key.
* **Public read**: ``PublicAssessmentRead`` — the same shape **minus
  the ``is_correct`` flag on choices**. Renders the form to the
  candidate without leaking the answer key over the wire.

The MCQ-multi only restriction in Phase 2 means there's no question
``type`` field — every question is multi-select MCQ. If a future
phase introduces free-text / file upload, add a ``type`` discrim-
inator to ``AssessmentQuestionBase`` and dispatch in the scoring
service.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


INVITE_STATUS_PATTERN = r"^(pending|sent|opened|submitted|expired|cancelled)$"
IDENTITY_FIELD_PATTERN = r"^(dob|email|mobile)$"

QuestionType = Literal[
    "short_text",
    "long_text",
    "date",
    "checkbox",
    "single_choice",
    "multi_choice",
    "attachment",
]


# ---------------------------------------------------------------------------
# Write models — HR creates/edits templates
# ---------------------------------------------------------------------------


class AssessmentChoiceCreate(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    order_index: int = Field(default=0, ge=0, le=10_000)
    is_correct: bool = False


class AssessmentChoiceUpdate(BaseModel):
    text: Optional[str] = Field(default=None, max_length=2000)
    order_index: Optional[int] = Field(default=None, ge=0, le=10_000)
    is_correct: Optional[bool] = None


class AssessmentQuestionCreate(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    type: QuestionType = "multi_choice"
    help_text: Optional[str] = Field(default=None, max_length=2000)
    is_required: bool = True
    # Type-specific options (min_length/max_length, min_date/max_date,
    # placeholder, accepted_mime_types, max_file_size_mb).
    config: Dict[str, Any] = Field(default_factory=dict)
    order_index: int = Field(default=0, ge=0, le=10_000)
    points: int = Field(default=1, ge=1, le=100)
    # Required + non-empty (≥2, ≥1 correct) only for single_choice /
    # multi_choice — validated by type here (422) and defended in the
    # service layer.
    choices: Optional[List[AssessmentChoiceCreate]] = Field(
        default=None, max_length=20
    )

    @model_validator(mode="after")
    def _check_choices_by_type(self) -> "AssessmentQuestionCreate":
        # Shape check (422). The "≥1 correct" rule stays in the service
        # layer so it surfaces as a friendly 400 with a message.
        items = self.choices or []
        if self.type in ("single_choice", "multi_choice"):
            if len(items) < 2:
                raise ValueError("Choice questions need at least two choices.")
        elif items:
            raise ValueError(
                f"'{self.type}' questions do not take choices."
            )
        return self


class AssessmentQuestionUpdate(BaseModel):
    text: Optional[str] = Field(default=None, max_length=5000)
    type: Optional[QuestionType] = None
    help_text: Optional[str] = Field(default=None, max_length=2000)
    is_required: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    order_index: Optional[int] = Field(default=None, ge=0, le=10_000)
    points: Optional[int] = Field(default=None, ge=1, le=100)
    # If supplied, the choice list fully replaces what's stored —
    # simpler than a per-choice diff and matches how the HR UI edits
    # a question (whole form, then Save).
    choices: Optional[List[AssessmentChoiceCreate]] = Field(
        default=None, max_length=20
    )


class AssessmentCreate(BaseModel):
    job_opening_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    instructions: Optional[str] = Field(default=None, max_length=20_000)
    time_limit_minutes: Optional[int] = Field(default=None, ge=1, le=600)
    passing_score: Optional[int] = Field(default=None, ge=0)
    is_active: bool = True
    # Optional inline questions so a one-shot "create template +
    # questions" POST stays a single transaction.
    questions: Optional[List[AssessmentQuestionCreate]] = Field(default=None)


class AssessmentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    instructions: Optional[str] = Field(default=None, max_length=20_000)
    time_limit_minutes: Optional[int] = Field(default=None, ge=1, le=600)
    passing_score: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# HR read models — full answer-key visibility
# ---------------------------------------------------------------------------


class AssessmentChoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    order_index: int
    is_correct: bool


class AssessmentQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    type: str = "multi_choice"
    help_text: Optional[str] = None
    is_required: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)
    order_index: int
    points: int
    choices: List[AssessmentChoiceRead]


class AssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_opening_id: int
    title: str
    instructions: Optional[str]
    time_limit_minutes: Optional[int]
    passing_score: Optional[int]
    is_active: bool
    created_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    questions: List[AssessmentQuestionRead]
    total_points: int = 0  # populated by the service layer

    invite_count: int = 0  # populated by the service layer
    submission_count: int = 0  # populated by the service layer


class AssessmentSummary(BaseModel):
    """Lightweight list-view shape — no question nesting."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_opening_id: int
    title: str
    is_active: bool
    time_limit_minutes: Optional[int]
    passing_score: Optional[int]
    created_at: datetime
    updated_at: datetime
    question_count: int = 0
    invite_count: int = 0
    submission_count: int = 0


class AssessmentList(BaseModel):
    items: List[AssessmentSummary]
    total: int


# ---------------------------------------------------------------------------
# Invite + submission read models (HR side)
# ---------------------------------------------------------------------------


class AssessmentInviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assessment_id: int
    candidate_id: int
    application_id: Optional[int]
    token: str
    status: str
    sent_at: Optional[datetime]
    opened_at: Optional[datetime]
    submitted_at: Optional[datetime]
    expires_at: Optional[datetime]
    verified_identity_field: Optional[str]
    sent_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class AssessmentInviteSend(BaseModel):
    """HR ``POST /hr/assessments/{id}/invites`` body."""

    candidate_id: int = Field(ge=1)
    application_id: Optional[int] = Field(default=None, ge=1)
    expires_at: Optional[datetime] = None


class AssessmentAnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: int
    selected_choice_ids: List[int]
    value: Optional[Dict[str, Any]] = None
    is_correct: Optional[bool]
    reviewer_passed: Optional[bool] = None
    reviewer_note: Optional[str] = None


class AssessmentSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invite_id: int
    started_at: datetime
    submitted_at: Optional[datetime]
    score: Optional[int]
    max_score: Optional[int]
    passed: Optional[bool]
    review_status: str = "pending"
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    reviewer_overall_comment: Optional[str] = None
    reviewer_score_override: Optional[int] = None
    answers: List[AssessmentAnswerRead]


class AssessmentSubmissionListItem(BaseModel):
    """One row in the cross-template submissions list (criterion 6).

    Flattens invite + submission + candidate + assessment + job so the
    HR submissions index renders without N+1 round-trips.
    """

    invite_id: int
    submission_id: int
    candidate_id: int
    candidate_name: str
    candidate_email: Optional[str] = None
    application_id: Optional[int] = None
    assessment_id: int
    assessment_title: str
    job_opening_id: Optional[int] = None
    job_title: Optional[str] = None
    invite_status: str
    submitted_at: Optional[datetime] = None
    score: Optional[int] = None
    max_score: Optional[int] = None
    passed: Optional[bool] = None


class AssessmentSubmissionListResponse(BaseModel):
    items: List[AssessmentSubmissionListItem]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Public-facing models — answer key MUST NOT leak
# ---------------------------------------------------------------------------


class PublicChoiceRead(BaseModel):
    """Public version of a choice — note the absence of ``is_correct``.

    Pydantic doesn't auto-strip fields, so this is a separate model
    rather than ``AssessmentChoiceRead`` with an exclude. Keeping it
    explicit means we can't accidentally hand back the answer key in
    a future refactor.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    order_index: int


class PublicQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    type: str = "multi_choice"
    help_text: Optional[str] = None
    is_required: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)
    order_index: int
    points: int
    choices: List[PublicChoiceRead]


class PublicAssessmentRead(BaseModel):
    """The bundle a verified candidate fetches to render the form."""

    title: str
    instructions: Optional[str]
    time_limit_minutes: Optional[int]
    questions: List[PublicQuestionRead]
    candidate_name: str
    candidate_email: Optional[str]
    submit_deadline: Optional[datetime]  # opened_at + time_limit, if set


class IdentityVerifyRequest(BaseModel):
    """POST /assessments/{token}/verify."""

    identity_value: str = Field(min_length=1, max_length=255)


class IdentityVerifyResponse(BaseModel):
    """Returned on successful identity check.

    ``session_token`` is a short-lived JWT the frontend stashes and
    sends on subsequent fetch/submit calls so the candidate doesn't
    re-verify on every page nav.
    """

    session_token: str
    matched_field: str  # dob | email | mobile
    opened_at: datetime
    submit_deadline: Optional[datetime]


class PublicAnswerSubmit(BaseModel):
    question_id: int = Field(ge=1)
    selected_choice_ids: List[int] = Field(default_factory=list, max_length=20)
    # Typed answer for non-choice questions:
    #   {"text": "..."} | {"date": "2026-05-31"} | {"checked": true}
    #   | {"choice_id": 42}  (single_choice)
    value: Optional[Dict[str, Any]] = None


class PublicAssessmentSubmit(BaseModel):
    """POST /assessments/{token}/submit."""

    answers: List[PublicAnswerSubmit] = Field(default_factory=list)


class PublicSubmissionAck(BaseModel):
    """Returned to the candidate after submit — only the score and
    pass/fail signal, never per-question correctness."""

    score: int
    max_score: int
    passed: Optional[bool]
    submitted_at: datetime


# ---------------------------------------------------------------------------
# HR review-and-advance
# ---------------------------------------------------------------------------


class ReviewPerQuestion(BaseModel):
    question_id: int = Field(ge=1)
    passed: Optional[bool] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class AssessmentReviewCreate(BaseModel):
    """Payload for ``POST /hr/assessments/submissions/{id}/review``."""

    action: Literal[
        "draft_saved", "approved_advanced", "rejected", "changes_requested"
    ]
    per_question: List[ReviewPerQuestion] = Field(default_factory=list)
    overall_comment: Optional[str] = Field(default=None, max_length=5000)
    score_override: Optional[int] = Field(default=None, ge=0)
    # Required when action == approved_advanced — the next application
    # status (must be in ALLOWED_TRANSITIONS for the current status).
    advance_to_status: Optional[str] = None
    # Required when action in {rejected, changes_requested}.
    reason: Optional[str] = Field(default=None, max_length=2000)


class AssessmentReviewEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    submission_id: int
    actor_user_id: Optional[int] = None
    action: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime


__all__ = [
    "INVITE_STATUS_PATTERN",
    "IDENTITY_FIELD_PATTERN",
    # HR write
    "AssessmentChoiceCreate",
    "AssessmentChoiceUpdate",
    "AssessmentQuestionCreate",
    "AssessmentQuestionUpdate",
    "AssessmentCreate",
    "AssessmentUpdate",
    # HR read
    "AssessmentChoiceRead",
    "AssessmentQuestionRead",
    "AssessmentRead",
    "AssessmentSummary",
    "AssessmentList",
    "AssessmentInviteRead",
    "AssessmentInviteSend",
    "AssessmentAnswerRead",
    "AssessmentSubmissionRead",
    "AssessmentSubmissionListItem",
    "AssessmentSubmissionListResponse",
    # Review
    "ReviewPerQuestion",
    "AssessmentReviewCreate",
    "AssessmentReviewEventRead",
    # Public
    "PublicChoiceRead",
    "PublicQuestionRead",
    "PublicAssessmentRead",
    "IdentityVerifyRequest",
    "IdentityVerifyResponse",
    "PublicAnswerSubmit",
    "PublicAssessmentSubmit",
    "PublicSubmissionAck",
]

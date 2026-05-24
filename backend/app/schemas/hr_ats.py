"""Pydantic schemas for the HR ATS Job Opening surface (Phase 9)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


JOB_STATUS_PATTERN = r"^(open|on_hold|closed)$"
EMPLOYMENT_TYPE_PATTERN = r"^(full_time|part_time|contract)$"


class JobOpeningBase(BaseModel):
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=1, max_length=255)
    department: str = Field(min_length=1, max_length=120)
    division: Optional[str] = Field(default=None, max_length=120)
    company: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=255)
    employment_type: str = Field(default="full_time", pattern=EMPLOYMENT_TYPE_PATTERN)

    min_experience: int = Field(default=0, ge=0, le=60)
    max_experience: int = Field(default=0, ge=0, le=60)
    required_education: Optional[str] = Field(default=None, max_length=255)

    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_max: Optional[int] = Field(default=None, ge=0)
    visa_requirement: Optional[str] = Field(default=None, max_length=120)
    nationality_preference: Optional[str] = Field(default=None, max_length=255)
    language_requirement: Optional[str] = Field(default=None, max_length=255)
    notice_period_preference: Optional[str] = Field(default=None, max_length=120)

    description: Optional[str] = None
    responsibilities: Optional[str] = None  # newline-separated
    requirements: Optional[str] = None  # newline-separated
    required_skills: Optional[str] = None  # comma-separated
    preferred_skills: Optional[str] = None  # comma-separated

    status: str = Field(default="open", pattern=JOB_STATUS_PATTERN)


class JobOpeningCreate(JobOpeningBase):
    pass


class JobOpeningUpdate(BaseModel):
    slug: Optional[str] = Field(default=None, pattern=r"^[a-z0-9-]+$")
    title: Optional[str] = None
    department: Optional[str] = None
    division: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    employment_type: Optional[str] = Field(default=None, pattern=EMPLOYMENT_TYPE_PATTERN)

    min_experience: Optional[int] = Field(default=None, ge=0, le=60)
    max_experience: Optional[int] = Field(default=None, ge=0, le=60)
    required_education: Optional[str] = None

    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_max: Optional[int] = Field(default=None, ge=0)
    visa_requirement: Optional[str] = None
    nationality_preference: Optional[str] = None
    language_requirement: Optional[str] = None
    notice_period_preference: Optional[str] = None

    description: Optional[str] = None
    responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    required_skills: Optional[str] = None
    preferred_skills: Optional[str] = None

    status: Optional[str] = Field(default=None, pattern=JOB_STATUS_PATTERN)


class JobOpeningRead(JobOpeningBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    posted_at: datetime
    closed_at: Optional[datetime] = None
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class JobOpeningList(BaseModel):
    """Lightweight list payload — same fields, used as the response model
    of the list endpoint. Kept as a thin alias so we can later switch
    to a paginated wrapper without touching consumers."""

    items: List[JobOpeningRead]


# ---------------------------------------------------------------------------
# Candidates (Phase 10)
# ---------------------------------------------------------------------------


class CandidateDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_path: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    is_primary: bool
    uploaded_by_id: Optional[int] = None
    created_at: datetime


class CandidateApplicationSummary(BaseModel):
    """Application row shown alongside the candidate (e.g. in lists)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    job_opening_id: Optional[int] = None
    job_title: Optional[str] = None
    applied_at: datetime
    source: Optional[str] = None


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    nationality: Optional[str] = None
    current_location: Optional[str] = None
    current_designation: Optional[str] = None
    current_company: Optional[str] = None
    total_experience_years: Optional[float] = None
    gcc_experience_years: Optional[float] = None
    qatar_experience_years: Optional[float] = None
    expected_salary: Optional[int] = None
    notice_period: Optional[str] = None
    visa_status: Optional[str] = None
    availability: Optional[str] = None
    is_blacklisted: bool
    is_archived: bool
    source: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    documents: List[CandidateDocumentRead] = Field(default_factory=list)


class CandidateListItem(BaseModel):
    """Trimmed candidate row for the HR list view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    current_designation: Optional[str] = None
    total_experience_years: Optional[float] = None
    source: Optional[str] = None
    is_blacklisted: bool
    is_archived: bool
    created_at: datetime


class ApplicationSubmissionResponse(BaseModel):
    """Returned from POST /public/candidate-applications and the HR
    single-upload endpoint."""

    candidate_id: int
    application_id: int
    was_existing_candidate: bool
    job_title: Optional[str] = None
    job_slug: Optional[str] = None


class BulkUploadSkip(BaseModel):
    name: str
    reason: str


class BulkUploadResult(BaseModel):
    total_files: int
    created_candidates: int
    matched_existing_candidates: int
    duplicate_applications_skipped: int
    skipped_files: List[BulkUploadSkip] = Field(default_factory=list)
    candidate_ids: List[int] = Field(default_factory=list)

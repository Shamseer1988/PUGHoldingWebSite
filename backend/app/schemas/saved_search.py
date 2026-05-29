"""Pydantic schemas for saved candidate searches (Feature F1)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.hr_ats import SAVED_SEARCH_SCOPES


# The "filters" payload is whatever shape the candidate-list search
# accepts. We don't lock it to a Pydantic model here because the
# CandidateFilters surface evolves over time and we'd rather have
# saved rows survive new optional fields than start raising on
# unknown keys.
FiltersPayload = dict


class SavedSearchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2000)
    filters: FiltersPayload = Field(default_factory=dict)
    scope: str = Field(default="private")
    pinned: bool = False


class SavedSearchUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2000)
    filters: Optional[FiltersPayload] = None
    scope: Optional[str] = None
    pinned: Optional[bool] = None


class SavedSearchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: Optional[int]
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None
    name: str
    description: Optional[str]
    filters: FiltersPayload
    scope: str
    pinned: bool
    last_run_at: Optional[datetime]
    last_result_count: Optional[int]
    created_at: datetime
    updated_at: datetime
    is_owner: bool = False


class SavedSearchRunResult(BaseModel):
    saved_search_id: int
    name: str
    result_count: int
    candidate_ids: list[int]


VALID_SCOPES = set(SAVED_SEARCH_SCOPES)

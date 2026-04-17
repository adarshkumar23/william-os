"""
WILLIAM OS — Career Schemas
Pydantic v2 request/response models for the career module.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Problems ─────────────────────────────────────────────────────


class ProblemCreate(BaseModel):
    platform: str | None = None
    external_id: str | None = None
    title: str
    difficulty: str | None = None
    topics: list[str] = Field(default_factory=list)
    url: str | None = None
    solved_at: datetime | None = None
    time_spent_minutes: int | None = None
    notes: str | None = None


class ProblemUpdate(BaseModel):
    platform: str | None = None
    external_id: str | None = None
    title: str | None = None
    difficulty: str | None = None
    topics: list[str] | None = None
    url: str | None = None
    solved_at: datetime | None = None
    time_spent_minutes: int | None = None
    notes: str | None = None


class ProblemRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    platform: str | None
    external_id: str | None
    title: str
    difficulty: str | None
    topics: list[str]
    url: str | None
    solved_at: datetime | None
    time_spent_minutes: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Projects ─────────────────────────────────────────────────────


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    tech_stack: list[str] = Field(default_factory=list)
    status: str = "planning"
    live_url: str | None = None
    github_url: str | None = None
    on_resume: bool = False
    started_at: date | None = None
    shipped_at: date | None = None
    notes: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tech_stack: list[str] | None = None
    status: str | None = None
    live_url: str | None = None
    github_url: str | None = None
    on_resume: bool | None = None
    started_at: date | None = None
    shipped_at: date | None = None
    notes: str | None = None


class ProjectRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    tech_stack: list[str]
    status: str
    live_url: str | None
    github_url: str | None
    on_resume: bool
    started_at: date | None
    shipped_at: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Applications ─────────────────────────────────────────────────


class ApplicationCreate(BaseModel):
    company: str
    role: str
    platform: str | None = None
    stage: str = "researching"
    applied_at: date | None = None
    next_action: str | None = None
    next_action_due: date | None = None
    stipend_or_ctc: str | None = None
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    company: str | None = None
    role: str | None = None
    platform: str | None = None
    stage: str | None = None
    applied_at: date | None = None
    next_action: str | None = None
    next_action_due: date | None = None
    stipend_or_ctc: str | None = None
    notes: str | None = None
    archived: bool | None = None


class ApplicationStageUpdate(BaseModel):
    stage: str


class ApplicationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    company: str
    role: str
    platform: str | None
    stage: str
    stage_updated_at: datetime | None
    applied_at: date | None
    next_action: str | None
    next_action_due: date | None
    stipend_or_ctc: str | None
    notes: str | None
    archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Contacts ─────────────────────────────────────────────────────


class ContactCreate(BaseModel):
    name: str
    company: str | None = None
    role: str | None = None
    tags: list[str] = Field(default_factory=list)
    linkedin_url: str | None = None
    email: str | None = None
    temperature: str = "cold"
    last_contacted_at: date | None = None
    next_followup_at: date | None = None
    relationship_notes: str | None = None


class ContactUpdate(BaseModel):
    name: str | None = None
    company: str | None = None
    role: str | None = None
    tags: list[str] | None = None
    linkedin_url: str | None = None
    email: str | None = None
    temperature: str | None = None
    last_contacted_at: date | None = None
    next_followup_at: date | None = None
    relationship_notes: str | None = None


class ContactRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    company: str | None
    role: str | None
    tags: list[str]
    linkedin_url: str | None
    email: str | None
    temperature: str
    last_contacted_at: date | None
    next_followup_at: date | None
    relationship_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Opportunities ─────────────────────────────────────────────────


class OpportunityCreate(BaseModel):
    title: str
    source: str | None = None
    kind: str = "other"
    url: str | None = None
    description: str | None = None
    deadline: datetime | None = None
    stipend_info: str | None = None
    status: str = "inbox"


class OpportunityUpdate(BaseModel):
    title: str | None = None
    source: str | None = None
    kind: str | None = None
    url: str | None = None
    description: str | None = None
    deadline: datetime | None = None
    stipend_info: str | None = None
    status: str | None = None


class OpportunityConvert(BaseModel):
    role: str
    platform: str | None = None


class OpportunityRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    source: str | None
    kind: str
    url: str | None
    description: str | None
    deadline: datetime | None
    stipend_info: str | None
    status: str
    converted_to_application_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Score ─────────────────────────────────────────────────────────


class CareerScoreRead(BaseModel):
    overall: int
    components: dict[str, Any]
    snapshot_date: str


class CareerDashboardRead(BaseModel):
    score: CareerScoreRead
    score_history: list[dict[str, Any]]
    stats: dict[str, Any]
    pipeline_preview: dict[str, list[dict[str, Any]]]
    recent_opportunities: list[dict[str, Any]]
    warnings: list[str]


class CFRatingUpdate(BaseModel):
    rating: int = Field(ge=0, le=4000)

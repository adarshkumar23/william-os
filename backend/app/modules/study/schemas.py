"""
WILLIAM OS — Study Schemas
Pydantic models for Study Mentor API contracts.
"""

from __future__ import annotations

from datetime import date as DateType
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    syllabus_topics: list[str] = Field(default_factory=list)
    total_weight: float = Field(default=0.0, ge=0)
    color: str = Field(default="#3B82F6", min_length=7, max_length=7)


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    syllabus_topics: list[str] | None = None
    total_weight: float | None = Field(default=None, ge=0)
    color: str | None = Field(default=None, min_length=7, max_length=7)


class SubjectResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    syllabus_topics: list[str]
    total_weight: float
    color: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StudySessionCreate(BaseModel):
    subject_id: UUID
    duration_minutes: int = Field(ge=1, le=1440)
    topics_covered: list[str] = Field(default_factory=list)
    comprehension_score: float = Field(ge=1, le=10)
    notes: str | None = None
    session_date: DateType = Field(default_factory=DateType.today)


class StudySessionUpdate(BaseModel):
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    topics_covered: list[str] | None = None
    comprehension_score: float | None = Field(default=None, ge=1, le=10)
    notes: str | None = None
    session_date: DateType | None = None


class StudySessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    subject_id: UUID
    duration_minutes: int
    topics_covered: list[str]
    comprehension_score: float
    notes: str | None
    session_date: DateType
    created_at: datetime

    model_config = {"from_attributes": True}


class RevisionCardCreate(BaseModel):
    subject_id: UUID
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    next_review_date: DateType = Field(default_factory=DateType.today)


class RevisionCardUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1)
    answer: str | None = Field(default=None, min_length=1)
    next_review_date: DateType | None = None


class RevisionCardResponse(BaseModel):
    id: UUID
    user_id: UUID
    subject_id: UUID
    question: str
    answer: str
    next_review_date: DateType
    interval_days: int
    ease_factor: float
    repetitions: int
    last_reviewed: DateType | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewResult(BaseModel):
    quality: int = Field(ge=0, le=5)


class MockTestCreate(BaseModel):
    subject_id: UUID | None = None
    test_name: str = Field(min_length=1, max_length=200)
    score: int = Field(ge=0)
    total: int = Field(ge=1)
    date: DateType = Field(default_factory=DateType.today)
    analysis: dict | None = None

    @model_validator(mode="after")
    def validate_score(self) -> MockTestCreate:
        if self.score > self.total:
            raise ValueError("score cannot exceed total")
        return self


class MockTestUpdate(BaseModel):
    test_name: str | None = Field(default=None, min_length=1, max_length=200)
    score: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=1)
    date: DateType | None = None
    analysis: dict | None = None


class MockTestResponse(BaseModel):
    id: UUID
    user_id: UUID
    subject_id: UUID | None
    test_name: str
    score: int
    total: int
    percentage: float
    date: DateType
    analysis: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class StudyProgress(BaseModel):
    subject: str
    hours_studied: float
    avg_comprehension: float
    cards_due: int
    mock_avg: float


class StudyPlanRequest(BaseModel):
    target_date: DateType
    daily_hours: int = Field(ge=1, le=16)

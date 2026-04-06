"""
WILLIAM OS — Decisions Schemas
Request and response models for decision assistant APIs.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class DecisionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    decision_type: str = Field(min_length=1, max_length=50)
    deadline: date | None = None
    options: list[dict] = Field(default_factory=list)
    criteria: list[dict] = Field(default_factory=list)


class DecisionResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: str
    status: str
    decision_type: str
    deadline: date | None
    options: list[dict]
    criteria: list[dict]
    ai_analysis: str | None
    ai_scores: dict | None
    chosen_option: str | None
    chosen_at: datetime | None
    outcome: str | None
    outcome_rating: int | None
    reviewed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DecisionAnalysis(BaseModel):
    scores: dict
    recommendation: str
    reasoning: str
    confidence: float
    risk_factors: list[str]


class DecisionChoose(BaseModel):
    chosen_option: str = Field(min_length=1, max_length=200)
    reasoning: str | None = None


class DecisionOutcome(BaseModel):
    outcome: str = Field(min_length=1)
    outcome_rating: int = Field(ge=1, le=5)


class DecisionStats(BaseModel):
    total: int
    avg_time_to_decide: float
    ai_agreement_rate: float
    avg_outcome_rating: float
    by_type: dict

"""
WILLIAM OS — Sleep Schemas
Request and response models for sleep optimizer.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


class SleepRecordCreate(BaseModel):
    sleep_date: date
    bedtime: datetime
    wake_time: datetime
    time_to_fall_asleep_minutes: int | None = Field(default=None, ge=0, le=240)
    interruptions: int = Field(default=0, ge=0, le=100)
    sleep_quality: float = Field(ge=1, le=10)
    deep_sleep_minutes: int | None = Field(default=None, ge=0)
    light_sleep_minutes: int | None = Field(default=None, ge=0)
    rem_sleep_minutes: int | None = Field(default=None, ge=0)
    notes: str | None = None
    source: str = Field(default="manual", min_length=1, max_length=20)


class SleepRecordResponse(BaseModel):
    id: UUID
    user_id: UUID
    sleep_date: date
    bedtime: datetime
    wake_time: datetime
    sleep_duration_minutes: int
    time_to_fall_asleep_minutes: int | None
    interruptions: int
    sleep_quality: float
    deep_sleep_minutes: int | None
    light_sleep_minutes: int | None
    rem_sleep_minutes: int | None
    notes: str | None
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SleepRecommendationResponse(BaseModel):
    id: UUID
    user_id: UUID
    recommendation_date: date
    recommended_bedtime: str
    recommended_wake_time: str
    recommended_duration_minutes: int
    reasoning: str
    factors: dict
    confidence: float
    followed: bool | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SleepDebtResponse(BaseModel):
    id: UUID
    user_id: UUID
    calculated_date: date
    optimal_hours: float
    actual_hours_7d_avg: float
    debt_hours: float
    trend: str
    days_to_recover: int
    created_at: datetime


class SleepStats(BaseModel):
    avg_quality_30d: float
    avg_duration: float
    avg_bedtime: str
    consistency_score: float


class SleepAnalysis(BaseModel):
    patterns: list[str]
    recommendations: list[str]
    optimal_window: dict
    ai_insights: str

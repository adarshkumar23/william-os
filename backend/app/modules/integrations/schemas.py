"""WILLIAM OS - Integrations request schemas."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Literal
from typing import Any
from uuid import UUID

from app.modules.journal.models import JournalMood
from pydantic import BaseModel, Field


class IntegrationSleepIn(BaseModel):
    sleep_date: date
    bedtime: datetime
    wake_time: datetime
    sleep_quality: float = Field(ge=1, le=10)
    source_device: str | None = None


class IntegrationWorkoutIn(BaseModel):
    workout_date: date = Field(default_factory=date.today)
    workout_type: str = Field(min_length=1, max_length=50)
    duration_minutes: int = Field(ge=1, le=1440)
    calories: float | None = None
    notes: str | None = None
    source_device: str | None = None


class IntegrationHabitCheckInIn(BaseModel):
    habit_id: UUID | None = None
    habit_name: str | None = None
    completed: bool = True
    check_date: date | None = None
    note: str | None = None


class IntegrationJournalEntryIn(BaseModel):
    content: str = Field(min_length=1)
    mood: JournalMood | None = None
    tags: list[str] = Field(default_factory=list)


class IntegrationTradeIn(BaseModel):
    symbol: str
    action: str
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    trade_date: date | None = None
    exchange: str = "NSE"


class IntegrationMedicineLogIn(BaseModel):
    medicine_id: UUID | None = None
    medicine_name: str | None = None
    taken: bool
    taken_at: datetime | None = None
    note: str | None = None


class IntegrationMoodIn(BaseModel):
    mood: JournalMood
    note: str | None = None
    logged_at: datetime | None = None


class IntegrationStudySessionIn(BaseModel):
    subject_id: UUID | None = None
    subject_name: str | None = None
    duration_minutes: int = Field(ge=1, le=600)
    comprehension_score: float = Field(ge=0, le=10)
    topics_covered: list[str] = Field(default_factory=list)


class IntegrationScheduleGenerateIn(BaseModel):
    target_date: date = Field(default_factory=date.today)
    force_regenerate: bool = False
    extra_context: dict[str, Any] = Field(default_factory=dict)


class IntegrationScheduleBlockIn(BaseModel):
    plan_date: date = Field(default_factory=date.today)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category: Literal[
        "work",
        "study",
        "fitness",
        "meal",
        "sleep",
        "personal",
        "social",
        "health",
        "commute",
        "break",
        "routine",
        "buffer",
    ] = "work"
    start_time: time
    end_time: time
    priority: int = Field(default=5, ge=1, le=10)
    is_fixed: bool = False
    tags: list[str] = Field(default_factory=list)


class IntegrationDecisionCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    decision_type: str = Field(min_length=1, max_length=50)
    deadline: date | None = None
    options: list[dict[str, Any]] = Field(default_factory=list)
    criteria: list[dict[str, Any]] = Field(default_factory=list)


class IntegrationDecisionChooseIn(BaseModel):
    decision_id: UUID
    chosen_option: str = Field(min_length=1, max_length=200)
    reasoning: str | None = None


class IntegrationDecisionOutcomeIn(BaseModel):
    decision_id: UUID
    outcome: str = Field(min_length=1)
    outcome_rating: int = Field(ge=1, le=5)


class IntegrationApiKeyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class IntegrationApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime
    api_key: str | None = None


class IntegrationTelegramDailyIn(BaseModel):
    action: Literal[
        "today_schedule",
        "daily_summary",
        "habit_checkin",
        "quick_journal",
        "study_log",
    ]
    habit_name: str | None = None
    journal_content: str | None = None
    journal_passphrase: str | None = None
    study_subject_name: str | None = None
    study_duration_minutes: int | None = Field(default=None, ge=1, le=600)
    study_comprehension_score: float | None = Field(default=None, ge=0, le=10)
    study_topics: list[str] = Field(default_factory=list)


class IntegrationTriggerIn(BaseModel):
    event_name: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class IntegrationSessionContext(BaseModel):
    user_id: UUID
    source: str
    token_type: str


class IntegrationDailySummary(BaseModel):
    sleep: dict[str, Any]
    habits: dict[str, Any]
    fitness: dict[str, Any]
    study: dict[str, Any]
    medicine: dict[str, Any]
    life_score: dict[str, Any]
    warnings: dict[str, Any]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC).replace(tzinfo=None))


class IntegrationAuthMeta(BaseModel):
    user_id: UUID
    source: str
    token_type: str

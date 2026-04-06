"""
WILLIAM OS — Habits Schemas
Request/response models for habits and check-ins.
"""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from app.modules.habits.models import HabitFrequency
from pydantic import BaseModel, Field, field_validator, model_validator


class HabitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    category: str = Field(default="general", max_length=50)
    icon: str = Field(default="✅", max_length=10)

    frequency: HabitFrequency = HabitFrequency.DAILY
    days_of_week: list[int] = []
    preferred_time: time | None = None
    duration_minutes: int = Field(default=0, ge=0)

    auto_schedule: bool = True
    schedule_category: str = Field(default="routine", max_length=20)
    sort_order: int = 0
    is_active: bool = True

    @field_validator("days_of_week")
    @classmethod
    def validate_days_of_week(cls, value: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("days_of_week must contain integers from 0 (Mon) to 6 (Sun)")
        return sorted(list(set(value)))

    @model_validator(mode="after")
    def validate_frequency(self) -> HabitCreate:
        if self.frequency == HabitFrequency.CUSTOM and not self.days_of_week:
            raise ValueError("Custom frequency requires at least one day in days_of_week")
        return self


class HabitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    category: str | None = Field(default=None, max_length=50)
    icon: str | None = Field(default=None, max_length=10)

    frequency: HabitFrequency | None = None
    days_of_week: list[int] | None = None
    preferred_time: time | None = None
    duration_minutes: int | None = Field(default=None, ge=0)

    auto_schedule: bool | None = None
    schedule_category: str | None = Field(default=None, max_length=20)
    sort_order: int | None = None
    is_active: bool | None = None

    @field_validator("days_of_week")
    @classmethod
    def validate_days_of_week(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return value
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("days_of_week must contain integers from 0 (Mon) to 6 (Sun)")
        return sorted(list(set(value)))


class HabitResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str | None
    category: str
    icon: str

    frequency: HabitFrequency
    days_of_week: list[int]
    preferred_time: time | None
    duration_minutes: int

    current_streak: int
    best_streak: int
    total_completions: int

    is_active: bool
    sort_order: int
    auto_schedule: bool
    schedule_category: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HabitCheckInCreate(BaseModel):
    check_date: date = Field(default_factory=date.today)
    completed: bool = True
    skipped: bool = False
    notes: str | None = None
    quality_score: float | None = Field(default=None, ge=1, le=5)
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_check_in_state(self) -> HabitCheckInCreate:
        if self.completed and self.skipped:
            raise ValueError("A check-in cannot be both completed and skipped")
        return self


class HabitCheckInResponse(BaseModel):
    id: UUID
    habit_id: UUID
    check_date: date
    completed: bool
    completed_at: datetime | None
    skipped: bool
    notes: str | None
    quality_score: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProcrastinationDetectRequest(BaseModel):
    target_date: date = Field(default_factory=date.today)
    threshold_minutes: int = Field(default=90, ge=1, le=720)
    missed_habit_threshold: int = Field(default=2, ge=1, le=20)


class ProcrastinationSignalResponse(BaseModel):
    id: UUID
    user_id: UUID
    signal_date: date
    missed_habits: list[str]
    missed_blocks: list[str]
    severity: str
    notification_sent: bool
    acknowledged: bool
    created_at: datetime

    model_config = {"from_attributes": True}

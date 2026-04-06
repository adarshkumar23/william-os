"""
WILLIAM OS — Fitness Schemas
Request/response models for fitness intelligence APIs.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FitnessDeviceCreate(BaseModel):
    device_type: str = Field(min_length=2, max_length=30)
    device_name: str = Field(min_length=1, max_length=100)
    device_id: str | None = Field(default=None, max_length=100)


class FitnessDeviceResponse(BaseModel):
    id: UUID
    user_id: UUID
    device_type: str
    device_name: str
    device_id: str | None
    last_sync_at: datetime | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthMetricCreate(BaseModel):
    metric_type: str = Field(min_length=1, max_length=30)
    value: float
    unit: str = Field(min_length=1, max_length=20)
    recorded_at: datetime
    source_device_id: UUID | None = None


class HealthMetricResponse(BaseModel):
    id: UUID
    user_id: UUID
    metric_type: str
    value: float
    unit: str
    recorded_at: datetime
    source_device_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthMetricBatch(BaseModel):
    metrics: list[HealthMetricCreate]


class WorkoutLogCreate(BaseModel):
    workout_type: str = Field(min_length=1, max_length=50)
    duration_minutes: int = Field(ge=1, le=1440)
    calories_burned: float | None = None
    heart_rate_avg: float | None = None
    heart_rate_max: float | None = None
    distance_km: float | None = None
    notes: str | None = None
    workout_date: date = Field(default_factory=date.today)


class WorkoutLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    workout_type: str
    duration_minutes: int
    calories_burned: float | None
    heart_rate_avg: float | None
    heart_rate_max: float | None
    distance_km: float | None
    notes: str | None
    workout_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class DailyHealthSummary(BaseModel):
    steps: float
    avg_heart_rate: float
    calories: float
    sleep_hours: float
    spo2: float
    stress: float
    workout_count: int
    workout_minutes: int


class EnergyForecastResponse(BaseModel):
    id: UUID
    forecast_date: date
    hourly_scores: dict
    peak_hours: list[str]
    low_hours: list[str]
    suggestions: list[str]
    generated_by: str

    model_config = {"from_attributes": True}
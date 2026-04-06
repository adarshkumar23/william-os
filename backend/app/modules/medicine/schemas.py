"""
WILLIAM OS — Medicine Reminder Schemas
Request/response models for medicine plans, logs, and analytics.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from app.modules.medicine.models import MedicineType
from pydantic import BaseModel, Field, model_validator


class MedicineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dosage: str = Field(min_length=1, max_length=50)
    medicine_type: MedicineType = MedicineType.SUPPLEMENT
    instructions: str | None = None

    times_per_day: int = Field(default=1, ge=1, le=24)
    reminder_times: list[str] = []
    with_food: bool = False

    start_date: date | None = None
    end_date: date | None = None
    refill_reminder_days: int = Field(default=7, ge=1, le=365)
    remaining_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_date_window(self) -> MedicineCreate:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        return self


class MedicineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    dosage: str | None = Field(default=None, min_length=1, max_length=50)
    medicine_type: MedicineType | None = None
    instructions: str | None = None

    times_per_day: int | None = Field(default=None, ge=1, le=24)
    reminder_times: list[str] | None = None
    with_food: bool | None = None

    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None
    refill_reminder_days: int | None = Field(default=None, ge=1, le=365)
    remaining_count: int | None = Field(default=None, ge=0)


class MedicineResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    dosage: str
    medicine_type: MedicineType
    instructions: str | None
    times_per_day: int
    reminder_times: list[str]
    with_food: bool
    start_date: date | None
    end_date: date | None
    is_active: bool
    refill_reminder_days: int
    remaining_count: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MedicineLogCreate(BaseModel):
    taken: bool
    skipped: bool
    skip_reason: str | None = None

    @model_validator(mode="after")
    def validate_state(self) -> MedicineLogCreate:
        if self.taken and self.skipped:
            raise ValueError("A dose cannot be marked as both taken and skipped")
        if not self.taken and not self.skipped:
            raise ValueError("A dose must be marked as either taken or skipped")
        if self.skipped and not self.skip_reason:
            raise ValueError("skip_reason is required when skipped=true")
        return self


class MedicineLogResponse(BaseModel):
    id: UUID
    medicine_id: UUID
    log_date: date
    scheduled_time: str
    taken: bool
    taken_at: str | None
    skipped: bool
    skip_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UpcomingReminder(BaseModel):
    medicine_name: str
    dosage: str
    scheduled_time: str
    with_food: bool
    instructions: str | None


class AdherenceStats(BaseModel):
    total_scheduled: int
    total_taken: int
    total_skipped: int
    adherence_rate: float

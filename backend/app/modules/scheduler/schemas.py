"""
WILLIAM OS — Scheduler Schemas
Request/response models for schedule endpoints.
"""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.scheduler.models import BlockCategory, BlockStatus, PlanStatus


class BlockCreate(BaseModel):
    title: str = Field(max_length=200)
    description: str | None = None
    category: BlockCategory
    start_time: time
    end_time: time
    priority: int = Field(default=5, ge=1, le=10)
    is_fixed: bool = False
    tags: list[str] = []
    linked_module: str | None = None


class BlockUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    category: BlockCategory | None = None
    start_time: time | None = None
    end_time: time | None = None
    status: BlockStatus | None = None
    priority: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = None


class BlockResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    category: BlockCategory
    start_time: time
    end_time: time
    duration_minutes: int
    status: BlockStatus
    priority: int
    is_fixed: bool
    is_ai_generated: bool
    actual_start: datetime | None
    actual_end: datetime | None
    notes: str | None
    tags: list[str]
    linked_module: str | None

    model_config = {"from_attributes": True}


class DailyPlanResponse(BaseModel):
    id: UUID
    plan_date: date
    status: PlanStatus
    generation_model: str
    completion_score: float | None
    energy_score: float | None
    blocks: list[BlockResponse]
    created_at: datetime

    model_config = {"from_attributes": True}


class RescheduleRequest(BaseModel):
    reason: str = Field(max_length=500)
    trigger: str = "manual"  # voice, manual, auto
    affected_block_ids: list[UUID] = []
    new_constraints: dict = {}  # e.g. {"free_until": "14:00", "cancel": ["gym"]}


class ScheduleGenerateRequest(BaseModel):
    target_date: date
    force_regenerate: bool = False
    extra_context: dict = {}  # user can inject priorities, events, etc.


class DayScoreUpdate(BaseModel):
    completion_score: float = Field(ge=0, le=10)
    energy_score: float = Field(ge=0, le=10)

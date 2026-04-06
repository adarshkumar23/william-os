"""
WILLIAM OS — Scheduler Models
Daily plans generated at midnight, individual schedule blocks, and reschedule history.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from enum import Enum

from app.core.database import Base
from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class PlanStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class BlockCategory(str, Enum):
    WORK = "work"
    STUDY = "study"
    FITNESS = "fitness"
    MEAL = "meal"
    SLEEP = "sleep"
    PERSONAL = "personal"
    SOCIAL = "social"
    HEALTH = "health"
    COMMUTE = "commute"
    BREAK = "break"
    ROUTINE = "routine"  # morning/evening routines
    BUFFER = "buffer"  # flex time


class BlockStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    RESCHEDULED = "rescheduled"


class DailyPlan(Base):
    """One plan per user per day. Regenerated at midnight via Gemini."""

    __tablename__ = "daily_plans"
    __table_args__ = (
        Index(
            "ix_daily_plans_user_date_status",
            "user_id",
            "plan_date",
            "status",
        ),
        {"schema": "scheduler"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[PlanStatus] = mapped_column(
        SAEnum(PlanStatus, schema="scheduler"),
        default=PlanStatus.DRAFT,
    )

    # AI generation metadata
    generation_model: Mapped[str] = mapped_column(String(50), default="gemini-2.0-flash")
    generation_prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generation_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Context fed to AI for generation
    context_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Day scoring
    completion_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    energy_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    blocks: Mapped[list[ScheduleBlock]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="ScheduleBlock.start_time",
        lazy="selectin",
    )
    reschedule_log: Mapped[list[RescheduleEvent]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ScheduleBlock(Base):
    """Individual time block within a daily plan."""

    __tablename__ = "schedule_blocks"
    __table_args__ = {"schema": "scheduler"}

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduler.daily_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[BlockCategory] = mapped_column(
        SAEnum(BlockCategory, schema="scheduler"),
        nullable=False,
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[BlockStatus] = mapped_column(
        SAEnum(BlockStatus, schema="scheduler"),
        default=BlockStatus.PENDING,
    )
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1=highest, 10=lowest
    is_fixed: Mapped[bool] = mapped_column(Boolean, default=False)  # immovable blocks
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=True)

    # Completion tracking
    actual_start: Mapped[datetime | None] = mapped_column(nullable=True)
    actual_end: Mapped[datetime | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    linked_module: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linked_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    plan: Mapped[DailyPlan] = relationship(back_populates="blocks")


class RescheduleEvent(Base):
    """Tracks every reschedule for audit trail + AI learning."""

    __tablename__ = "reschedule_events"
    __table_args__ = {"schema": "scheduler"}

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduler.daily_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    block_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False)  # voice, manual, auto
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    old_schedule: Mapped[dict] = mapped_column(JSONB, default=dict)
    new_schedule: Mapped[dict] = mapped_column(JSONB, default=dict)
    ai_model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)

    plan: Mapped[DailyPlan] = relationship(back_populates="reschedule_log")

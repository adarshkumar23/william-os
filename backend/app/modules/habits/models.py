"""
WILLIAM OS — Habits Models
Habit definitions, daily check-ins, streaks, and procrastination signals.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from enum import Enum

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class HabitFrequency(str, Enum):
    DAILY = "daily"
    WEEKDAYS = "weekdays"
    WEEKENDS = "weekends"
    CUSTOM = "custom"  # specific days via days_of_week


class Habit(Base):
    __tablename__ = "habits"
    __table_args__ = {"schema": "habits"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="general")
    icon: Mapped[str] = mapped_column(String(10), default="✅")

    frequency: Mapped[HabitFrequency] = mapped_column(
        SAEnum(HabitFrequency, schema="habits"),
        default=HabitFrequency.DAILY,
    )
    days_of_week: Mapped[list[int]] = mapped_column(JSONB, default=list)  # 0=Mon..6=Sun
    preferred_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)

    # Streak tracking
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    total_completions: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    # Link to scheduler for auto-scheduling
    auto_schedule: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule_category: Mapped[str] = mapped_column(String(20), default="routine")

    check_ins: Mapped[list[HabitCheckIn]] = relationship(
        back_populates="habit",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class HabitCheckIn(Base):
    __tablename__ = "habit_check_ins"
    __table_args__ = (
        UniqueConstraint(
            "habit_id",
            "check_date",
            name="uq_habit_check_ins_habit_date",
        ),
        {
            "schema": "habits",
            "info": {"constraint_name": "uq_habit_check_ins_habit_date"},
        },
    )

    habit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("habits.habits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    check_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 1-5

    habit: Mapped[Habit] = relationship(back_populates="check_ins")


class ProcrastinationSignal(Base):
    """Detected when expected check-ins are missed beyond a threshold."""

    __tablename__ = "procrastination_signals"
    __table_args__ = {"schema": "habits"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_date: Mapped[date] = mapped_column(Date, nullable=False)
    missed_habits: Mapped[list[str]] = mapped_column(JSONB, default=list)
    missed_blocks: Mapped[list[str]] = mapped_column(JSONB, default=list)
    severity: Mapped[str] = mapped_column(String(10), default="low")  # low, medium, high
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)

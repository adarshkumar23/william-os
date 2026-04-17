"""
WILLIAM OS — Sleep Models
Sleep tracking, recommendations, and debt calculations.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

import structlog
from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

logger = structlog.get_logger(__name__)


class SleepRecord(Base):
    __tablename__ = "sleep_records"
    __table_args__ = {"schema": "sleep"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sleep_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    bedtime: Mapped[datetime] = mapped_column(nullable=False)
    wake_time: Mapped[datetime] = mapped_column(nullable=False)
    sleep_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    time_to_fall_asleep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interruptions: Mapped[int] = mapped_column(Integer, default=0)
    sleep_quality: Mapped[float] = mapped_column(Float, nullable=False)
    deep_sleep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    light_sleep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rem_sleep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")


class SleepRecommendation(Base):
    __tablename__ = "sleep_recommendations"
    __table_args__ = {"schema": "sleep"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recommendation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    recommended_bedtime: Mapped[str] = mapped_column(String(5), nullable=False)
    recommended_wake_time: Mapped[str] = mapped_column(String(5), nullable=False)
    recommended_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    factors: Mapped[dict] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    followed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class SleepDebt(Base):
    __tablename__ = "sleep_debts"
    __table_args__ = {"schema": "sleep"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    calculated_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    optimal_hours: Mapped[float] = mapped_column(Float, default=7.5)
    actual_hours_7d_avg: Mapped[float] = mapped_column(Float, nullable=False)
    debt_hours: Mapped[float] = mapped_column(Float, nullable=False)
    trend: Mapped[str] = mapped_column(String(20), nullable=False)

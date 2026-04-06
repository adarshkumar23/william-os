"""
WILLIAM OS — Fitness Models
Device sync, health metrics, workouts, and daily energy forecasting.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from app.core.database import Base
from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class FitnessDevice(Base):
    __tablename__ = "fitness_devices"
    __table_args__ = {"schema": "fitness"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_type: Mapped[str] = mapped_column(String(30), nullable=False)
    device_name: Mapped[str] = mapped_column(String(100), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class HealthMetric(Base):
    __tablename__ = "health_metrics"
    __table_args__ = {"schema": "fitness"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    source_device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fitness.fitness_devices.id", ondelete="SET NULL"),
        nullable=True,
    )


class WorkoutLog(Base):
    __tablename__ = "workout_logs"
    __table_args__ = {"schema": "fitness"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workout_type: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    calories_burned: Mapped[float | None] = mapped_column(Float, nullable=True)
    heart_rate_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    heart_rate_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    workout_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)


class EnergyForecast(Base):
    __tablename__ = "energy_forecasts"
    __table_args__ = {"schema": "fitness"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    hourly_scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    peak_hours: Mapped[list[str]] = mapped_column(JSONB, default=list)
    low_hours: Mapped[list[str]] = mapped_column(JSONB, default=list)
    factors: Mapped[dict] = mapped_column(JSONB, default=dict)
    generated_by: Mapped[str] = mapped_column(String(100), nullable=False)
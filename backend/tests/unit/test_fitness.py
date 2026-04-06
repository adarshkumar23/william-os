"""
WILLIAM OS — Fitness Service Tests
Unit tests for metrics ingestion, summaries, forecast generation, and workout logs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from app.modules.fitness.schemas import HealthMetricCreate, WorkoutLogCreate
from app.modules.fitness.service import FitnessService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_log_metrics_and_daily_summary(db_session: AsyncSession, test_user):
    service = FitnessService(db_session)

    await service.log_metrics(
        user_id=test_user.id,
        metrics=[
            HealthMetricCreate(
                metric_type="steps",
                value=8500,
                unit="count",
                recorded_at=datetime.now(UTC),
            ),
            HealthMetricCreate(
                metric_type="heart_rate",
                value=72,
                unit="bpm",
                recorded_at=datetime.now(UTC),
            ),
            HealthMetricCreate(
                metric_type="sleep_hours",
                value=7.5,
                unit="hours",
                recorded_at=datetime.now(UTC),
            ),
        ],
    )

    summary = await service.get_daily_summary(user_id=test_user.id, target_date=date.today())

    assert summary.steps == 8500
    assert summary.avg_heart_rate == 72
    assert summary.sleep_hours == 7.5


@pytest.mark.asyncio
async def test_workout_logging(db_session: AsyncSession, test_user):
    service = FitnessService(db_session)

    workout = await service.log_workout(
        user_id=test_user.id,
        data=WorkoutLogCreate(
            workout_type="running",
            duration_minutes=45,
            calories_burned=420,
            distance_km=6.2,
            workout_date=date.today(),
        ),
    )

    workouts = await service.list_workouts(user_id=test_user.id, days=7)

    assert workout.workout_type == "running"
    assert len(workouts) == 1
    assert workouts[0].duration_minutes == 45


@pytest.mark.asyncio
async def test_energy_forecast_generation(db_session: AsyncSession, test_user, monkeypatch):
    service = FitnessService(db_session)

    async def _fake_ai(_factors: dict):
        return {
            "hourly_scores": {"08": 8.2, "09": 8.6, "14": 5.4},
            "peak_hours": ["09", "08"],
            "low_hours": ["14"],
            "generated_by": "test-ai",
        }

    monkeypatch.setattr(service, "_generate_ai_forecast", _fake_ai)

    forecast = await service.generate_energy_forecast(
        user_id=test_user.id,
        forecast_date=date.today(),
    )

    assert forecast.generated_by == "test-ai"
    assert "09" in forecast.peak_hours
    assert isinstance(forecast.suggestions, list)


@pytest.mark.asyncio
async def test_metric_history_query(db_session: AsyncSession, test_user):
    service = FitnessService(db_session)

    await service.log_metrics(
        user_id=test_user.id,
        metrics=[
            HealthMetricCreate(
                metric_type="spo2",
                value=98,
                unit="percent",
                recorded_at=datetime.now(UTC),
            )
        ],
    )

    history = await service.get_metric_history(
        user_id=test_user.id,
        metric_type="spo2",
        days=30,
    )

    assert len(history) == 1
    assert history[0].metric_type == "spo2"

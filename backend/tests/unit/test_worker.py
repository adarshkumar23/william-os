"""
WILLIAM OS — Worker Schedule Tests
Regression checks for Celery beat wiring.
"""

from __future__ import annotations

from app.worker import celery_app


def test_energy_forecast_beat_task_registered() -> None:
    schedule = celery_app.conf.beat_schedule
    assert "daily-energy-forecast-generation" in schedule

    entry = schedule["daily-energy-forecast-generation"]
    assert entry["task"] == "app.worker.generate_daily_energy_forecasts"

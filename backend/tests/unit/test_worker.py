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


def test_sprint4_beat_tasks_registered() -> None:
    schedule = celery_app.conf.beat_schedule

    assert "trading-price-alert-check" in schedule
    assert schedule["trading-price-alert-check"]["task"] == "app.worker.check_trading_price_alerts"

    assert "daily-portfolio-snapshot" in schedule
    assert (
        schedule["daily-portfolio-snapshot"]["task"]
        == "app.worker.create_daily_portfolio_snapshots"
    )

    assert "daily-sleep-recommendation" in schedule
    assert (
        schedule["daily-sleep-recommendation"]["task"]
        == "app.worker.generate_daily_sleep_recommendations"
    )

    assert "weekly-decision-review" in schedule
    assert schedule["weekly-decision-review"]["task"] == "app.worker.send_weekly_decision_review"

"""
WILLIAM OS — Sleep Service Tests
Unit tests for sleep logging, debt, stats, and recommendations.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.modules.sleep.schemas import SleepRecordCreate
from app.modules.sleep.service import SleepService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_log_sleep_calculates_duration(db_session: AsyncSession, test_user):
    service = SleepService(db_session)

    bedtime = datetime.now(UTC).replace(hour=22, minute=30, second=0, microsecond=0) - timedelta(
        days=1
    )
    wake_time = bedtime + timedelta(hours=7, minutes=15)

    record = await service.log_sleep(
        user_id=test_user.id,
        data=SleepRecordCreate(
            sleep_date=date.today(),
            bedtime=bedtime,
            wake_time=wake_time,
            sleep_quality=8.0,
            source="manual",
        ),
    )

    assert record.sleep_duration_minutes == 435


@pytest.mark.asyncio
async def test_sleep_debt_calculation(db_session: AsyncSession, test_user):
    service = SleepService(db_session)

    for i in range(7):
        sleep_date = date.today() - timedelta(days=i)
        bedtime = datetime.now(UTC).replace(hour=23, minute=0, second=0, microsecond=0) - timedelta(
            days=i + 1
        )
        wake_time = bedtime + timedelta(hours=6)
        await service.log_sleep(
            user_id=test_user.id,
            data=SleepRecordCreate(
                sleep_date=sleep_date,
                bedtime=bedtime,
                wake_time=wake_time,
                sleep_quality=7.0,
            ),
        )

    debt = await service.calculate_sleep_debt(user_id=test_user.id)

    assert debt.actual_hours_7d_avg == pytest.approx(6.0)
    assert debt.debt_hours == pytest.approx(1.5)
    assert debt.days_to_recover >= 1


@pytest.mark.asyncio
async def test_sleep_stats(db_session: AsyncSession, test_user):
    service = SleepService(db_session)

    bedtime = datetime.now(UTC).replace(hour=22, minute=0, second=0, microsecond=0) - timedelta(
        days=1
    )
    wake_time = bedtime + timedelta(hours=8)

    await service.log_sleep(
        user_id=test_user.id,
        data=SleepRecordCreate(
            sleep_date=date.today(),
            bedtime=bedtime,
            wake_time=wake_time,
            sleep_quality=9.0,
        ),
    )

    stats = await service.get_sleep_stats(user_id=test_user.id)

    assert stats.avg_quality_30d == 9.0
    assert stats.avg_duration == 480.0
    assert stats.consistency_score >= 0


@pytest.mark.asyncio
async def test_generate_recommendation_with_mock(db_session: AsyncSession, test_user, monkeypatch):
    service = SleepService(db_session)

    async def _fake_ai(*args, **kwargs) -> dict:
        _ = (args, kwargs)
        return {
            "recommended_bedtime": "22:00",
            "recommended_wake_time": "06:00",
            "recommended_duration_minutes": 480,
            "reasoning": "Sleep debt recovery window.",
            "confidence": 0.88,
        }

    monkeypatch.setattr(service, "_generate_ai_recommendation", _fake_ai)

    recommendation = await service.generate_recommendation(
        user_id=test_user.id,
        for_date=date.today(),
    )

    assert recommendation.recommended_bedtime == "22:00"
    assert recommendation.recommended_duration_minutes == 480
    assert recommendation.confidence == pytest.approx(0.88)

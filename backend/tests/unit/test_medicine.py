"""
WILLIAM OS — Medicine Reminder Service Tests
Unit tests for medicine CRUD, logging, upcoming reminders, and adherence metrics.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from app.modules.medicine.models import MedicineType
from app.modules.medicine.schemas import MedicineCreate
from app.modules.medicine.service import MedicineService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_medicine_and_list_active(db_session: AsyncSession, test_user):
    service = MedicineService(db_session)

    created = await service.create_medicine(
        user_id=test_user.id,
        data=MedicineCreate(
            name="Omega 3",
            dosage="1000mg",
            medicine_type=MedicineType.SUPPLEMENT,
            times_per_day=1,
            reminder_times=["08:00"],
            with_food=True,
            remaining_count=30,
        ),
    )

    active = await service.list_active(user_id=test_user.id)

    assert created.name == "Omega 3"
    assert len(active) == 1
    assert active[0].id == created.id


@pytest.mark.asyncio
async def test_log_taken_decrements_remaining_count(db_session: AsyncSession, test_user):
    service = MedicineService(db_session)

    medicine = await service.create_medicine(
        user_id=test_user.id,
        data=MedicineCreate(
            name="Vitamin D",
            dosage="2000 IU",
            medicine_type=MedicineType.VITAMIN,
            times_per_day=1,
            reminder_times=["09:00"],
            remaining_count=10,
        ),
    )

    logged = await service.log_dose(
        user_id=test_user.id,
        medicine_id=medicine.id,
        log_date=date.today(),
        scheduled_time=datetime.strptime("09:00", "%H:%M").time(),
        taken=True,
        skipped=False,
        skip_reason=None,
    )

    refreshed = await service.get_medicine(user_id=test_user.id, medicine_id=medicine.id)

    assert logged.taken is True
    assert logged.skipped is False
    assert refreshed.remaining_count == 9


@pytest.mark.asyncio
async def test_log_skipped_stores_reason(db_session: AsyncSession, test_user):
    service = MedicineService(db_session)

    medicine = await service.create_medicine(
        user_id=test_user.id,
        data=MedicineCreate(
            name="Magnesium",
            dosage="500mg",
            medicine_type=MedicineType.SUPPLEMENT,
            times_per_day=1,
            reminder_times=["21:00"],
            remaining_count=20,
        ),
    )

    logged = await service.log_dose(
        user_id=test_user.id,
        medicine_id=medicine.id,
        log_date=date.today(),
        scheduled_time=datetime.strptime("21:00", "%H:%M").time(),
        taken=False,
        skipped=True,
        skip_reason="Forgot while traveling",
    )

    assert logged.taken is False
    assert logged.skipped is True
    assert logged.skip_reason == "Forgot while traveling"


@pytest.mark.asyncio
async def test_upcoming_query_returns_due_items(db_session: AsyncSession, test_user):
    service = MedicineService(db_session)

    upcoming_time = (
        (datetime.now(UTC) + timedelta(minutes=5)).time().replace(second=0, microsecond=0)
    )
    reminder_slot = upcoming_time.strftime("%H:%M")

    await service.create_medicine(
        user_id=test_user.id,
        data=MedicineCreate(
            name="Iron",
            dosage="65mg",
            medicine_type=MedicineType.SUPPLEMENT,
            times_per_day=1,
            reminder_times=[reminder_slot],
            with_food=False,
        ),
    )

    reminders = await service.get_upcoming(user_id=test_user.id, within_minutes=10)

    assert len(reminders) == 1
    assert reminders[0].medicine_name == "Iron"


@pytest.mark.asyncio
async def test_adherence_stats_calculation(db_session: AsyncSession, test_user):
    service = MedicineService(db_session)

    medicine = await service.create_medicine(
        user_id=test_user.id,
        data=MedicineCreate(
            name="B12",
            dosage="1500mcg",
            medicine_type=MedicineType.VITAMIN,
            times_per_day=1,
            reminder_times=["07:00", "19:00"],
            remaining_count=40,
        ),
    )

    morning = datetime.strptime("07:00", "%H:%M").time()
    evening = datetime.strptime("19:00", "%H:%M").time()

    await service.log_dose(
        user_id=test_user.id,
        medicine_id=medicine.id,
        log_date=date.today(),
        scheduled_time=morning,
        taken=True,
        skipped=False,
        skip_reason=None,
    )
    await service.log_dose(
        user_id=test_user.id,
        medicine_id=medicine.id,
        log_date=date.today(),
        scheduled_time=evening,
        taken=False,
        skipped=True,
        skip_reason="Missed reminder",
    )

    stats = await service.get_adherence_stats(user_id=test_user.id, days=30)

    assert stats.total_scheduled == 2
    assert stats.total_taken == 1
    assert stats.total_skipped == 1
    assert stats.adherence_rate == 50.0

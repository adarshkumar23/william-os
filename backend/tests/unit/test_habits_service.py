"""
WILLIAM OS — Habits Service Tests
Unit tests for habit CRUD, check-ins, streaks, and procrastination detection.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from app.modules.habits.models import Habit, HabitCheckIn, ProcrastinationSignal
from app.modules.habits.schemas import HabitCheckInCreate, HabitCreate, HabitUpdate
from app.modules.habits.service import HabitsService
from app.shared.types import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_habit(db_session: AsyncSession, test_user):
    service = HabitsService(db_session)

    habit = await service.create_habit(test_user.id, HabitCreate(name="Morning Walk"))

    assert habit.name == "Morning Walk"
    assert habit.user_id == test_user.id
    assert habit.current_streak == 0


@pytest.mark.asyncio
async def test_list_habits_active_only(db_session: AsyncSession, test_user):
    service = HabitsService(db_session)

    await service.create_habit(test_user.id, HabitCreate(name="Active Habit", is_active=True))
    await service.create_habit(test_user.id, HabitCreate(name="Inactive Habit", is_active=False))

    active = await service.list_habits(test_user.id, active_only=True)
    all_habits = await service.list_habits(test_user.id, active_only=False)

    assert len(active) == 1
    assert active[0].name == "Active Habit"
    assert len(all_habits) == 2


@pytest.mark.asyncio
async def test_get_habit_returns_item(db_session: AsyncSession, test_user):
    service = HabitsService(db_session)
    created = await service.create_habit(test_user.id, HabitCreate(name="Read"))

    fetched = await service.get_habit(test_user.id, created.id)

    assert fetched.id == created.id
    assert fetched.name == "Read"


@pytest.mark.asyncio
async def test_update_habit_changes_fields(db_session: AsyncSession, test_user):
    service = HabitsService(db_session)
    created = await service.create_habit(test_user.id, HabitCreate(name="Meditate"))

    updated = await service.update_habit(
        test_user.id,
        created.id,
        HabitUpdate(name="Meditation", duration_minutes=20),
    )

    assert updated.name == "Meditation"
    assert updated.duration_minutes == 20


@pytest.mark.asyncio
async def test_delete_habit_removes_record(db_session: AsyncSession, test_user):
    service = HabitsService(db_session)
    created = await service.create_habit(test_user.id, HabitCreate(name="Delete Me"))

    await service.delete_habit(test_user.id, created.id)

    with pytest.raises(NotFoundError):
        await service.get_habit(test_user.id, created.id)


@pytest.mark.asyncio
async def test_check_in_habit_updates_streak_for_consecutive_days(
    db_session: AsyncSession,
    test_user,
):
    service = HabitsService(db_session)
    habit = await service.create_habit(test_user.id, HabitCreate(name="Workout"))

    yesterday = date.today() - timedelta(days=1)

    await service.check_in_habit(
        test_user.id,
        habit.id,
        HabitCheckInCreate(
            check_date=yesterday,
            completed=True,
            completed_at=datetime.now(UTC) - timedelta(days=1),
        ),
    )
    await service.check_in_habit(
        test_user.id,
        habit.id,
        HabitCheckInCreate(check_date=date.today(), completed=True),
    )

    refreshed = await service.get_habit(test_user.id, habit.id)
    assert refreshed.current_streak == 2
    assert refreshed.best_streak >= 2
    assert refreshed.total_completions == 2


@pytest.mark.asyncio
async def test_check_in_habit_reset_streak_on_skip(db_session: AsyncSession, test_user):
    service = HabitsService(db_session)
    habit = await service.create_habit(test_user.id, HabitCreate(name="Journal"))

    yesterday = date.today() - timedelta(days=1)
    await service.check_in_habit(
        test_user.id,
        habit.id,
        HabitCheckInCreate(
            check_date=yesterday,
            completed=True,
            completed_at=datetime.now(UTC) - timedelta(days=1),
        ),
    )

    await service.check_in_habit(
        test_user.id,
        habit.id,
        HabitCheckInCreate(check_date=date.today(), completed=False, skipped=True),
    )

    refreshed = await service.get_habit(test_user.id, habit.id)
    assert refreshed.current_streak == 0
    assert refreshed.total_completions == 1


@pytest.mark.asyncio
async def test_get_daily_check_ins_returns_users_entries_only(db_session: AsyncSession, test_user):
    service = HabitsService(db_session)

    habit = await service.create_habit(test_user.id, HabitCreate(name="Hydrate"))
    await service.check_in_habit(
        test_user.id,
        habit.id,
        HabitCheckInCreate(check_date=date.today(), completed=True),
    )

    # Different user + habit should not appear.
    other_user = uuid.uuid4()
    other_habit = Habit(
        user_id=other_user,
        name="Other",
        category="general",
        icon="✅",
    )
    db_session.add(other_habit)
    await db_session.flush()
    db_session.add(HabitCheckIn(habit_id=other_habit.id, check_date=date.today(), completed=True))
    await db_session.flush()

    check_ins = await service.get_daily_check_ins(test_user.id, date.today())

    assert len(check_ins) == 1
    assert check_ins[0].habit_id == habit.id


@pytest.mark.asyncio
async def test_detect_procrastination_creates_signal_when_threshold_exceeded(
    db_session: AsyncSession, test_user
):
    service = HabitsService(db_session)

    await service.create_habit(
        test_user.id,
        HabitCreate(name="Morning Reading", preferred_time=time(7, 0)),
    )
    await service.create_habit(
        test_user.id,
        HabitCreate(name="Meditation", preferred_time=time(7, 30)),
    )

    signal = await service.detect_procrastination(
        user_id=test_user.id,
        target_date=date.today(),
        threshold_minutes=90,
        missed_habit_threshold=2,
    )

    assert signal is not None
    assert signal.signal_date == date.today()
    assert len(signal.missed_habits) == 2
    assert signal.severity in {"medium", "high"}


@pytest.mark.asyncio
async def test_detect_procrastination_returns_none_below_threshold(
    db_session: AsyncSession,
    test_user,
):
    service = HabitsService(db_session)

    await service.create_habit(
        test_user.id,
        HabitCreate(name="Single Habit", preferred_time=time(8, 0)),
    )

    signal = await service.detect_procrastination(
        user_id=test_user.id,
        target_date=date.today(),
        threshold_minutes=90,
        missed_habit_threshold=2,
    )

    assert signal is None

    result = await db_session.execute(select(ProcrastinationSignal))
    assert result.scalars().all() == []

"""
WILLIAM OS — Habits Service
Habit CRUD, daily check-ins, streaks, and procrastination detection.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

import structlog
from app.core.events import Event, EventType, event_bus
from app.modules.habits.models import (
    Habit,
    HabitCheckIn,
    HabitFrequency,
    ProcrastinationSignal,
)
from app.modules.habits.schemas import (
    HabitCheckInCreate,
    HabitCheckInResponse,
    HabitCreate,
    HabitResponse,
    HabitUpdate,
    ProcrastinationSignalResponse,
)
from app.shared.types import NotFoundError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class HabitsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_habit(self, user_id: uuid.UUID, data: HabitCreate) -> HabitResponse:
        habit = Habit(user_id=user_id, **data.model_dump())
        self.db.add(habit)
        await self.db.flush()
        await self.db.refresh(habit)

        logger.info("habit_created", user_id=str(user_id), habit_id=str(habit.id))
        return HabitResponse.model_validate(habit)

    async def list_habits(
        self,
        user_id: uuid.UUID,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[HabitResponse]:
        query = select(Habit).where(Habit.user_id == user_id)
        if active_only:
            query = query.where(Habit.is_active.is_(True))

        query = query.order_by(Habit.sort_order.asc(), Habit.name.asc())
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        habits = result.scalars().all()
        return [HabitResponse.model_validate(habit) for habit in habits]

    async def get_habit(self, user_id: uuid.UUID, habit_id: uuid.UUID) -> HabitResponse:
        habit = await self._get_habit_for_user(user_id, habit_id)
        return HabitResponse.model_validate(habit)

    async def update_habit(
        self,
        user_id: uuid.UUID,
        habit_id: uuid.UUID,
        data: HabitUpdate,
    ) -> HabitResponse:
        habit = await self._get_habit_for_user(user_id, habit_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(habit, field, value)

        await self.db.flush()
        await self.db.refresh(habit)
        logger.info("habit_updated", user_id=str(user_id), habit_id=str(habit.id))
        return HabitResponse.model_validate(habit)

    async def delete_habit(self, user_id: uuid.UUID, habit_id: uuid.UUID) -> None:
        habit = await self._get_habit_for_user(user_id, habit_id)
        await self.db.delete(habit)
        await self.db.flush()
        logger.info("habit_deleted", user_id=str(user_id), habit_id=str(habit_id))

    async def check_in_habit(
        self,
        user_id: uuid.UUID,
        habit_id: uuid.UUID,
        data: HabitCheckInCreate,
    ) -> HabitCheckInResponse:
        habit = await self._get_habit_for_user(user_id, habit_id)

        existing_result = await self.db.execute(
            select(HabitCheckIn).where(
                and_(
                    HabitCheckIn.habit_id == habit.id,
                    HabitCheckIn.check_date == data.check_date,
                )
            )
        )
        check_in = existing_result.scalar_one_or_none()

        payload = data.model_dump()
        if payload["completed"] and not payload["skipped"] and payload["completed_at"] is None:
            payload["completed_at"] = datetime.now(UTC)
        if not payload["completed"] or payload["skipped"]:
            payload["completed_at"] = None

        if check_in:
            for field, value in payload.items():
                setattr(check_in, field, value)
        else:
            check_in = HabitCheckIn(habit_id=habit.id, **payload)
            self.db.add(check_in)

        await self._recalculate_habit_stats(
            habit,
            force_current_streak_reset=(not check_in.completed or check_in.skipped),
        )
        await self.db.flush()

        if check_in.completed and not check_in.skipped:
            await event_bus.publish(
                Event(
                    type=EventType.HABIT_CHECKED_IN,
                    data={
                        "habit_id": str(habit.id),
                        "habit_name": habit.name,
                        "date": str(check_in.check_date),
                    },
                    user_id=user_id,
                )
            )
        else:
            await event_bus.publish(
                Event(
                    type=EventType.HABIT_MISSED,
                    data={
                        "habit_id": str(habit.id),
                        "habit_name": habit.name,
                        "date": str(check_in.check_date),
                    },
                    user_id=user_id,
                )
            )

        logger.info(
            "habit_check_in_recorded",
            user_id=str(user_id),
            habit_id=str(habit.id),
            check_date=str(check_in.check_date),
            completed=check_in.completed,
            skipped=check_in.skipped,
        )

        return HabitCheckInResponse.model_validate(check_in)

    async def get_daily_check_ins(
        self,
        user_id: uuid.UUID,
        target_date: date,
    ) -> list[HabitCheckInResponse]:
        result = await self.db.execute(
            select(HabitCheckIn)
            .join(Habit, Habit.id == HabitCheckIn.habit_id)
            .where(
                and_(
                    Habit.user_id == user_id,
                    HabitCheckIn.check_date == target_date,
                )
            )
            .order_by(HabitCheckIn.created_at.asc())
        )
        check_ins = result.scalars().all()
        return [HabitCheckInResponse.model_validate(check_in) for check_in in check_ins]

    async def detect_procrastination(
        self,
        user_id: uuid.UUID,
        target_date: date | None = None,
        threshold_minutes: int = 90,
        missed_habit_threshold: int = 2,
    ) -> ProcrastinationSignalResponse | None:
        signal_date = target_date or date.today()

        habits_result = await self.db.execute(
            select(Habit).where(and_(Habit.user_id == user_id, Habit.is_active.is_(True)))
        )
        habits = habits_result.scalars().all()
        if not habits:
            return None

        habit_ids = [habit.id for habit in habits]
        check_ins_result = await self.db.execute(
            select(HabitCheckIn).where(
                and_(
                    HabitCheckIn.habit_id.in_(habit_ids),
                    HabitCheckIn.check_date == signal_date,
                )
            )
        )
        check_ins = check_ins_result.scalars().all()
        check_in_by_habit_id = {check_in.habit_id: check_in for check_in in check_ins}

        missed_habits: list[str] = []

        for habit in habits:
            if not self._is_habit_due_on(habit, signal_date):
                continue

            if habit.preferred_time is None:
                continue

            check_in = check_in_by_habit_id.get(habit.id)
            if not check_in or check_in.skipped or not check_in.completed:
                missed_habits.append(habit.name)
                habit.current_streak = 0
                continue

            if check_in.completed_at is None:
                missed_habits.append(habit.name)
                habit.current_streak = 0
                continue

            minutes_late = self._minutes_late(habit.preferred_time, check_in.completed_at)
            if minutes_late > threshold_minutes:
                missed_habits.append(habit.name)
                habit.current_streak = 0

        if len(missed_habits) < missed_habit_threshold:
            await self.db.flush()
            return None

        severity = self._severity_for_count(len(missed_habits))

        existing_result = await self.db.execute(
            select(ProcrastinationSignal).where(
                and_(
                    ProcrastinationSignal.user_id == user_id,
                    ProcrastinationSignal.signal_date == signal_date,
                )
            )
        )
        signal = existing_result.scalar_one_or_none()

        if signal:
            signal.missed_habits = missed_habits
            signal.severity = severity
        else:
            signal = ProcrastinationSignal(
                user_id=user_id,
                signal_date=signal_date,
                missed_habits=missed_habits,
                missed_blocks=[],
                severity=severity,
            )
            self.db.add(signal)

        await self.db.flush()

        await event_bus.publish(
            Event(
                type=EventType.PROCRASTINATION_DETECTED,
                data={
                    "date": str(signal_date),
                    "missed_habits": missed_habits,
                    "severity": severity,
                },
                user_id=user_id,
            )
        )

        for habit_name in missed_habits:
            await event_bus.publish(
                Event(
                    type=EventType.HABIT_MISSED,
                    data={"habit_name": habit_name, "date": str(signal_date)},
                    user_id=user_id,
                )
            )

        logger.info(
            "procrastination_detected",
            user_id=str(user_id),
            signal_date=str(signal_date),
            missed_count=len(missed_habits),
            severity=severity,
        )

        return ProcrastinationSignalResponse.model_validate(signal)

    async def _get_habit_for_user(self, user_id: uuid.UUID, habit_id: uuid.UUID) -> Habit:
        result = await self.db.execute(
            select(Habit).where(and_(Habit.id == habit_id, Habit.user_id == user_id))
        )
        habit = result.scalar_one_or_none()
        if not habit:
            raise NotFoundError("Habit", str(habit_id))
        return habit

    async def _recalculate_habit_stats(
        self,
        habit: Habit,
        force_current_streak_reset: bool = False,
    ) -> None:
        result = await self.db.execute(
            select(HabitCheckIn)
            .where(and_(HabitCheckIn.habit_id == habit.id, HabitCheckIn.completed.is_(True)))
            .order_by(HabitCheckIn.check_date.asc())
        )
        completed_check_ins = result.scalars().all()

        if not completed_check_ins:
            habit.current_streak = 0
            habit.best_streak = 0
            habit.total_completions = 0
            return

        dates = [item.check_date for item in completed_check_ins]
        habit.total_completions = len(dates)

        best_streak = 1
        running = 1
        for i in range(1, len(dates)):
            if dates[i] == dates[i - 1] + timedelta(days=1):
                running += 1
            else:
                running = 1
            best_streak = max(best_streak, running)

        trailing = 1
        for i in range(len(dates) - 1, 0, -1):
            if dates[i] == dates[i - 1] + timedelta(days=1):
                trailing += 1
            else:
                break

        current_streak = trailing
        if HabitsService._is_streak_broken(habit, dates[-1]):
            current_streak = 0

        if force_current_streak_reset:
            current_streak = 0

        habit.current_streak = current_streak
        habit.best_streak = max(best_streak, habit.best_streak)

    @staticmethod
    def _is_habit_due_on(habit: Habit, target_date: date) -> bool:
        weekday = target_date.weekday()  # 0=Mon..6=Sun
        if habit.frequency == HabitFrequency.DAILY:
            return True
        if habit.frequency == HabitFrequency.WEEKDAYS:
            return weekday <= 4
        if habit.frequency == HabitFrequency.WEEKENDS:
            return weekday >= 5
        if habit.frequency == HabitFrequency.CUSTOM:
            return weekday in (habit.days_of_week or [])
        return False

    @staticmethod
    def _is_streak_broken(habit: Habit, last_check_date: date) -> bool:
        """
        Returns True only if a day on which the habit was due was skipped
        between last_check_date and today. Correctly handles non-daily habits.
        """
        today = date.today()
        check = last_check_date + timedelta(days=1)
        while check < today:
            if HabitsService._is_habit_due_on(habit, check):
                return True
            check += timedelta(days=1)
        return False

    @staticmethod
    def _minutes_late(preferred_time: time, completed_at: datetime) -> int:
        scheduled = datetime.combine(completed_at.date(), preferred_time)
        actual = completed_at.replace(tzinfo=None)
        delay = actual - scheduled
        return max(0, int(delay.total_seconds() // 60))

    @staticmethod
    def _severity_for_count(missed_count: int) -> str:
        if missed_count <= 1:
            return "low"
        if missed_count <= 3:
            return "medium"
        return "high"

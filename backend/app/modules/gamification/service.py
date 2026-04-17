"""
WILLIAM OS — Gamification Service
XP awarding, record tracking, weekly momentum, and event subscriptions.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.events import Event, EventType, event_bus
from app.modules.gamification.models import PersonalRecord, UserXP, WeeklyMomentum, XPEvent
from app.modules.gamification.schemas import (
    GamificationProfileResponse,
    LevelProgress,
    PersonalRecordResponse,
    WeeklyMomentumResponse,
    XPEventResponse,
)
from app.modules.sleep.models import SleepRecord
from app.modules.study.models import StudySession

logger = structlog.get_logger(__name__)
_HANDLERS_REGISTERED = False


class GamificationService:
    EXPECTED_WEEKLY_XP = 620.0
    TRACKED_MODULES = (
        "habits",
        "journal",
        "medicine",
        "study",
        "sleep",
        "fitness",
        "decisions",
    )

    STREAK_MILESTONES = {
        7: 50,
        30: 150,
        90: 500,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def award_xp(
        self,
        user_id: uuid.UUID,
        source_module: str,
        action: str,
        metadata: dict | None = None,
    ) -> XPEventResponse | None:
        details = metadata or {}
        base_xp = self._xp_for_action(action=action, metadata=details)
        if base_xp <= 0:
            return None

        profile = await self._get_or_create_user_xp(user_id=user_id)
        primary_event = await self._append_xp_event(
            profile=profile,
            user_id=user_id,
            source_module=source_module,
            action=action,
            xp=base_xp,
        )

        if action == "habit_checkin":
            current_streak = int(details.get("current_streak") or 0)
            milestone_xp = self.STREAK_MILESTONES.get(current_streak)
            if milestone_xp:
                await self._append_xp_event(
                    profile=profile,
                    user_id=user_id,
                    source_module=source_module,
                    action=f"habit_streak_milestone_{current_streak}",
                    xp=milestone_xp,
                )

        await self._update_personal_records_if_applicable(
            user_id=user_id,
            source_module=source_module,
            action=action,
        )

        await self.db.flush()
        await self.db.refresh(primary_event)
        return XPEventResponse.model_validate(primary_event)

    async def compute_weekly_momentum(self, user_id: uuid.UUID) -> WeeklyMomentumResponse:
        week_start = self._week_start(date.today())
        week_end = week_start + timedelta(days=7)

        result = await self.db.execute(
            select(XPEvent)
            .where(XPEvent.user_id == user_id)
            .where(XPEvent.earned_at >= datetime.combine(week_start, datetime.min.time()))
            .where(XPEvent.earned_at < datetime.combine(week_end, datetime.min.time()))
            .order_by(XPEvent.earned_at.asc())
        )
        events = result.scalars().all()

        per_module_days: dict[str, set[str]] = defaultdict(set)
        total_xp = 0
        for event in events:
            total_xp += int(event.xp_earned)
            per_module_days[event.source_module].add(event.earned_at.date().isoformat())

        consistency_components: list[float] = []
        for module in self.TRACKED_MODULES:
            active_days = len(per_module_days.get(module, set()))
            consistency_components.append(min(7, active_days) / 7.0)

        consistency = sum(consistency_components) / max(1, len(consistency_components))
        expected_to_date = self._expected_xp_to_date(week_start=week_start)
        volume_factor = min(1.0, total_xp / expected_to_date) if expected_to_date > 0 else 0.0
        momentum_score = round((consistency * 0.7 + volume_factor * 0.3) * 100.0, 2)

        discipline_debt = await self.compute_discipline_debt(user_id=user_id)

        row = await self._get_or_create_weekly_row(user_id=user_id, week_start=week_start)
        row.momentum_score = momentum_score
        row.discipline_debt = discipline_debt
        await self.db.flush()

        rank_query = await self.db.execute(
            select(func.count(WeeklyMomentum.id))
            .where(WeeklyMomentum.week_start == week_start)
            .where(WeeklyMomentum.momentum_score > row.momentum_score)
        )
        higher_count = int(rank_query.scalar() or 0)
        row.focus_rank = higher_count + 1

        await self.db.flush()
        await self.db.refresh(row)
        return WeeklyMomentumResponse.model_validate(row)

    async def compute_discipline_debt(self, user_id: uuid.UUID) -> float:
        week_start = self._week_start(date.today())
        week_end = week_start + timedelta(days=7)

        expected_to_date = self._expected_xp_to_date(week_start=week_start)
        xp_query = await self.db.execute(
            select(func.coalesce(func.sum(XPEvent.xp_earned), 0))
            .where(XPEvent.user_id == user_id)
            .where(XPEvent.earned_at >= datetime.combine(week_start, datetime.min.time()))
            .where(XPEvent.earned_at < datetime.combine(week_end, datetime.min.time()))
        )
        earned = float(xp_query.scalar() or 0.0)
        return round(max(0.0, expected_to_date - earned), 2)

    async def get_profile(self, user_id: uuid.UUID) -> GamificationProfileResponse:
        profile = await self._get_or_create_user_xp(user_id=user_id)
        momentum = await self.compute_weekly_momentum(user_id=user_id)
        records = await self.list_records(user_id=user_id, limit=10, offset=0)
        history = await self.list_xp_history(user_id=user_id, limit=20, offset=0)

        level_progress = self._build_level_progress(
            level=profile.level,
            total_xp=profile.total_xp,
        )

        return GamificationProfileResponse(
            level_progress=level_progress,
            weekly_momentum=momentum,
            records=records,
            recent_xp_events=history,
        )

    async def list_xp_history(
        self,
        user_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[XPEventResponse]:
        result = await self.db.execute(
            select(XPEvent)
            .where(XPEvent.user_id == user_id)
            .order_by(desc(XPEvent.earned_at), desc(XPEvent.created_at))
            .limit(limit)
            .offset(offset)
        )
        rows = result.scalars().all()
        return [XPEventResponse.model_validate(item) for item in rows]

    async def list_records(
        self,
        user_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[PersonalRecordResponse]:
        result = await self.db.execute(
            select(PersonalRecord)
            .where(PersonalRecord.user_id == user_id)
            .order_by(desc(PersonalRecord.achieved_at), desc(PersonalRecord.created_at))
            .limit(limit)
            .offset(offset)
        )
        rows = result.scalars().all()
        return [PersonalRecordResponse.model_validate(item) for item in rows]

    async def _append_xp_event(
        self,
        profile: UserXP,
        user_id: uuid.UUID,
        source_module: str,
        action: str,
        xp: int,
    ) -> XPEvent:
        profile.total_xp += int(xp)
        profile.level = self._level_from_total_xp(profile.total_xp)
        profile.last_updated = datetime.now(UTC).replace(tzinfo=None)

        event = XPEvent(
            user_id=user_id,
            source_module=source_module,
            action=action,
            xp_earned=int(xp),
            earned_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def _get_or_create_user_xp(self, user_id: uuid.UUID) -> UserXP:
        result = await self.db.execute(select(UserXP).where(UserXP.user_id == user_id))
        row = result.scalar_one_or_none()
        if row:
            return row

        row = UserXP(
            user_id=user_id,
            total_xp=0,
            level=1,
            last_updated=datetime.now(UTC).replace(tzinfo=None),
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def _get_or_create_weekly_row(
        self,
        user_id: uuid.UUID,
        week_start: date,
    ) -> WeeklyMomentum:
        result = await self.db.execute(
            select(WeeklyMomentum)
            .where(WeeklyMomentum.user_id == user_id)
            .where(WeeklyMomentum.week_start == week_start)
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row:
            return row

        row = WeeklyMomentum(
            user_id=user_id,
            week_start=week_start,
            momentum_score=0.0,
            discipline_debt=0.0,
            focus_rank=0,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def _update_personal_records_if_applicable(
        self,
        user_id: uuid.UUID,
        source_module: str,
        action: str,
    ) -> None:
        if source_module == "habits" and action == "habit_checkin":
            await self._refresh_record_most_habits_completed(user_id)
        elif source_module == "study" and action == "study_session_completed":
            await self._refresh_record_longest_study_streak(user_id)
        elif source_module == "sleep" and action == "sleep_goal_met":
            await self._refresh_record_best_sleep_week(user_id)

    async def _refresh_record_most_habits_completed(self, user_id: uuid.UUID) -> None:
        week_start = self._week_start(date.today())
        week_end = week_start + timedelta(days=7)

        result = await self.db.execute(
            select(func.count(XPEvent.id))
            .where(XPEvent.user_id == user_id)
            .where(XPEvent.source_module == "habits")
            .where(XPEvent.action == "habit_checkin")
            .where(XPEvent.earned_at >= datetime.combine(week_start, datetime.min.time()))
            .where(XPEvent.earned_at < datetime.combine(week_end, datetime.min.time()))
        )
        completed = float(result.scalar() or 0.0)
        await self._upsert_record_if_higher(
            user_id=user_id,
            record_type="most_habits_completed",
            value=completed,
        )

    async def _refresh_record_longest_study_streak(self, user_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(StudySession.session_date)
            .where(StudySession.user_id == user_id)
            .order_by(StudySession.session_date.asc())
        )
        dates = [item for item in result.scalars().all()]
        if not dates:
            return

        unique_dates = sorted(set(dates))
        longest = 1
        running = 1
        for idx in range(1, len(unique_dates)):
            if unique_dates[idx] == unique_dates[idx - 1] + timedelta(days=1):
                running += 1
            else:
                running = 1
            longest = max(longest, running)

        await self._upsert_record_if_higher(
            user_id=user_id,
            record_type="longest_study_streak",
            value=float(longest),
        )

    async def _refresh_record_best_sleep_week(self, user_id: uuid.UUID) -> None:
        today = date.today()
        cutoff = today - timedelta(days=6)

        result = await self.db.execute(
            select(func.avg(SleepRecord.sleep_quality))
            .where(SleepRecord.user_id == user_id)
            .where(SleepRecord.sleep_date >= cutoff)
            .where(SleepRecord.sleep_date <= today)
        )
        avg_quality = result.scalar()
        if avg_quality is None:
            return

        await self._upsert_record_if_higher(
            user_id=user_id,
            record_type="best_sleep_week",
            value=round(float(avg_quality), 2),
        )

    async def _upsert_record_if_higher(
        self,
        user_id: uuid.UUID,
        record_type: str,
        value: float,
    ) -> None:
        result = await self.db.execute(
            select(PersonalRecord)
            .where(PersonalRecord.user_id == user_id)
            .where(PersonalRecord.record_type == record_type)
            .limit(1)
        )
        row = result.scalar_one_or_none()
        now = datetime.now(UTC).replace(tzinfo=None)

        if row is None:
            row = PersonalRecord(
                user_id=user_id,
                record_type=record_type,
                value=value,
                achieved_at=now,
            )
            self.db.add(row)
            await self.db.flush()
            return

        if value > float(row.value):
            row.value = value
            row.achieved_at = now
            await self.db.flush()

    @classmethod
    def _xp_for_action(cls, action: str, metadata: dict) -> int:
        if action == "habit_checkin":
            return 10
        if action == "journal_entry_created":
            return 15
        if action == "medicine_taken_on_time":
            return 5
        if action == "study_session_completed":
            duration = int(metadata.get("duration_minutes") or 0)
            return max(0, int(round((duration / 60.0) * 20)))
        if action == "sleep_goal_met":
            return 25
        if action == "workout_logged":
            return 20
        if action == "decision_completed_with_outcome":
            return 30
        if action == "bonus_xp_rule":
            return max(0, int(metadata.get("xp") or 0))
        return 0

    @staticmethod
    def _week_start(target_date: date) -> date:
        return target_date - timedelta(days=target_date.weekday())

    @classmethod
    def _expected_xp_to_date(cls, week_start: date) -> float:
        elapsed_days = min(7, max(1, (date.today() - week_start).days + 1))
        return round((cls.EXPECTED_WEEKLY_XP / 7.0) * elapsed_days, 2)

    @staticmethod
    def _xp_needed_for_level(level: int) -> int:
        prev = max(level - 1, 0)
        return int((100 * prev * level) / 2)

    @classmethod
    def _level_from_total_xp(cls, total_xp: int) -> int:
        level = 1
        while total_xp >= cls._xp_needed_for_level(level + 1):
            level += 1
        return level

    @classmethod
    def _build_level_progress(cls, level: int, total_xp: int) -> LevelProgress:
        floor = cls._xp_needed_for_level(level)
        next_target = cls._xp_needed_for_level(level + 1)
        span = max(1, next_target - floor)
        in_level = max(0, total_xp - floor)
        progress = round((in_level / span) * 100.0, 2)

        return LevelProgress(
            level=level,
            total_xp=total_xp,
            current_level_xp_floor=floor,
            next_level_xp_target=next_target,
            xp_to_next_level=max(0, next_target - total_xp),
            progress_pct=progress,
        )


async def _handle_habit_checkin(event: Event) -> None:
    if event.user_id is None:
        return
    async with async_session_factory() as db:
        service = GamificationService(db)
        await service.award_xp(
            user_id=event.user_id,
            source_module="habits",
            action="habit_checkin",
            metadata=event.data,
        )
        await db.commit()


async def _handle_journal_created(event: Event) -> None:
    if event.user_id is None:
        return
    async with async_session_factory() as db:
        service = GamificationService(db)
        await service.award_xp(
            user_id=event.user_id,
            source_module="journal",
            action="journal_entry_created",
            metadata=event.data,
        )
        await db.commit()


async def _handle_medicine_taken(event: Event) -> None:
    if event.user_id is None:
        return
    if not bool(event.data.get("is_on_time", False)):
        return

    async with async_session_factory() as db:
        service = GamificationService(db)
        await service.award_xp(
            user_id=event.user_id,
            source_module="medicine",
            action="medicine_taken_on_time",
            metadata=event.data,
        )
        await db.commit()


async def _handle_study_session_completed(event: Event) -> None:
    if event.user_id is None:
        return
    async with async_session_factory() as db:
        service = GamificationService(db)
        await service.award_xp(
            user_id=event.user_id,
            source_module="study",
            action="study_session_completed",
            metadata=event.data,
        )
        await db.commit()


async def _handle_sleep_logged(event: Event) -> None:
    if event.user_id is None:
        return

    duration_minutes = int(event.data.get("duration_minutes") or 0)
    sleep_quality = float(event.data.get("sleep_quality") or 0.0)
    if duration_minutes < 420 or sleep_quality < 7.0:
        return

    async with async_session_factory() as db:
        service = GamificationService(db)
        await service.award_xp(
            user_id=event.user_id,
            source_module="sleep",
            action="sleep_goal_met",
            metadata=event.data,
        )
        await db.commit()


async def _handle_workout_logged(event: Event) -> None:
    if event.user_id is None:
        return
    async with async_session_factory() as db:
        service = GamificationService(db)
        await service.award_xp(
            user_id=event.user_id,
            source_module="fitness",
            action="workout_logged",
            metadata=event.data,
        )
        await db.commit()


async def _handle_decision_completed(event: Event) -> None:
    if event.user_id is None:
        return
    async with async_session_factory() as db:
        service = GamificationService(db)
        await service.award_xp(
            user_id=event.user_id,
            source_module="decisions",
            action="decision_completed_with_outcome",
            metadata=event.data,
        )
        await db.commit()


def register_gamification_handlers() -> None:
    global _HANDLERS_REGISTERED
    if _HANDLERS_REGISTERED:
        return

    event_bus.subscribe(EventType.HABIT_CHECKED_IN, _handle_habit_checkin)
    event_bus.subscribe(EventType.JOURNAL_ENTRY_CREATED, _handle_journal_created)
    event_bus.subscribe(EventType.MEDICINE_TAKEN, _handle_medicine_taken)
    event_bus.subscribe(EventType.STUDY_SESSION_COMPLETED, _handle_study_session_completed)
    event_bus.subscribe(EventType.SLEEP_DATA_RECORDED, _handle_sleep_logged)
    event_bus.subscribe(EventType.WORKOUT_LOGGED, _handle_workout_logged)
    event_bus.subscribe(EventType.DECISION_COMPLETED_WITH_OUTCOME, _handle_decision_completed)
    _HANDLERS_REGISTERED = True
    logger.info("gamification_handlers_registered")

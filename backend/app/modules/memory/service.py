"""WILLIAM OS - Personal memory graph service."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from statistics import mean
from time import perf_counter
from typing import TYPE_CHECKING

import httpx
import structlog
from app.core.config import get_settings
from app.core.metrics import observe_ai_call
from app.modules.auth.models import User
from app.modules.fitness.models import WorkoutLog
from app.modules.habits.models import Habit, HabitCheckIn, ProcrastinationSignal
from app.modules.intelligence.models import LifeScore, ModuleSignal
from app.modules.journal.models import JournalEntry, JournalMood
from app.modules.memory.models import MemoryInsight, MemoryType, UserMemory
from app.modules.memory.schemas import (
    MemoryInsightResponse,
    MemoryProfileResponse,
    UserMemoryResponse,
)
from app.modules.sleep.models import SleepRecord
from app.modules.study.models import StudySession
from sqlalchemy import desc, select

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_MOOD_SCORE = {
    JournalMood.GREAT: 90.0,
    JournalMood.GOOD: 75.0,
    JournalMood.OKAY: 55.0,
    JournalMood.LOW: 35.0,
    JournalMood.BAD: 20.0,
}


class MemoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def update_memory(self, user_id: uuid.UUID) -> list[UserMemoryResponse]:
        cutoff = date.today() - timedelta(days=30)

        memories: list[tuple[MemoryType, str, dict, float, list[str]]] = []
        memories.append(await self._preferred_sleep_memory(user_id, cutoff))
        memories.append(await self._focus_hours_memory(user_id, cutoff))
        memories.append(await self._procrastination_windows_memory(user_id, cutoff))
        memories.append(await self._mood_before_after_events_memory(user_id, cutoff))
        memories.append(await self._energy_after_workout_memory(user_id, cutoff))
        memories.append(await self._sleep_performance_memory(user_id, cutoff))
        memories.append(await self._habits_good_days_memory(user_id, cutoff))

        saved: list[UserMemoryResponse] = []
        for memory_type, key, value, confidence, source_modules in memories:
            row = await self._upsert_memory(
                user_id=user_id,
                memory_type=memory_type,
                key=key,
                value=value,
                confidence=confidence,
                source_modules=source_modules,
            )
            saved.append(UserMemoryResponse.model_validate(row))

        return saved

    async def generate_insights(self, user_id: uuid.UUID) -> list[MemoryInsightResponse]:
        memories = await self.list_memories(user_id)
        if not memories:
            await self.update_memory(user_id)
            memories = await self.list_memories(user_id)

        summary = [
            {
                "key": m.key,
                "type": m.memory_type.value,
                "value": m.value,
                "confidence": m.confidence,
            }
            for m in memories
        ]
        insights = await self._generate_ai_insights(summary)

        result = await self.db.execute(
            select(MemoryInsight)
            .where(MemoryInsight.user_id == user_id)
            .where(MemoryInsight.is_active.is_(True))
        )
        for row in result.scalars().all():
            row.is_active = False

        created: list[MemoryInsightResponse] = []
        for insight_text in insights[:5]:
            row = MemoryInsight(
                user_id=user_id,
                insight=insight_text,
                supporting_evidence={"memory_keys": [m.key for m in memories[:6]]},
                generated_at=datetime.now(UTC).replace(tzinfo=None),
                is_active=True,
            )
            self.db.add(row)
            await self.db.flush()
            await self.db.refresh(row)
            created.append(MemoryInsightResponse.model_validate(row))

        return created

    async def get_memory_profile(self, user_id: uuid.UUID) -> MemoryProfileResponse:
        memories = await self.list_memories(user_id)
        insights = await self.list_insights(user_id)
        if not memories:
            await self.update_memory(user_id)
            memories = await self.list_memories(user_id)
        if not insights:
            insights = await self.generate_insights(user_id)

        return MemoryProfileResponse(
            memories=[UserMemoryResponse.model_validate(item) for item in memories],
            insights=[MemoryInsightResponse.model_validate(item) for item in insights],
        )

    async def list_memories(self, user_id: uuid.UUID) -> list[UserMemory]:
        result = await self.db.execute(
            select(UserMemory)
            .where(UserMemory.user_id == user_id)
            .order_by(
                desc(UserMemory.confidence),
                desc(UserMemory.last_updated),
                desc(UserMemory.created_at),
            )
        )
        return list(result.scalars().all())

    async def list_insights(self, user_id: uuid.UUID) -> list[MemoryInsight]:
        result = await self.db.execute(
            select(MemoryInsight)
            .where(MemoryInsight.user_id == user_id)
            .where(MemoryInsight.is_active.is_(True))
            .order_by(desc(MemoryInsight.generated_at), desc(MemoryInsight.created_at))
        )
        return list(result.scalars().all())

    async def delete_memory(self, user_id: uuid.UUID, key: str) -> bool:
        result = await self.db.execute(
            select(UserMemory)
            .where(UserMemory.user_id == user_id)
            .where(UserMemory.key == key)
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self.db.delete(row)
        await self.db.flush()
        return True

    async def get_relevant_memory_context(
        self,
        user_id: uuid.UUID,
        modules: list[str] | None = None,
        limit: int = 6,
    ) -> str:
        memories = await self.list_memories(user_id)
        if not memories:
            return "No stable memory signals yet."

        selected = []
        module_set = set(modules or [])
        for memory in memories:
            if not module_set:
                selected.append(memory)
                continue
            if module_set.intersection(set(memory.source_modules or [])):
                selected.append(memory)

        if not selected:
            selected = memories

        lines = []
        for row in selected[:limit]:
            lines.append(
                f"- {row.key}: {json.dumps(row.value, default=str)} "
                f"(confidence {row.confidence:.2f})"
            )
        return "\n".join(lines)

    async def _upsert_memory(
        self,
        user_id: uuid.UUID,
        memory_type: MemoryType,
        key: str,
        value: dict,
        confidence: float,
        source_modules: list[str],
    ) -> UserMemory:
        result = await self.db.execute(
            select(UserMemory)
            .where(UserMemory.user_id == user_id)
            .where(UserMemory.key == key)
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = UserMemory(
                user_id=user_id,
                memory_type=memory_type,
                key=key,
                value=value,
                confidence=confidence,
                source_modules=source_modules,
                last_updated=datetime.now(UTC).replace(tzinfo=None),
            )
            self.db.add(row)
        else:
            row.memory_type = memory_type
            row.value = value
            row.confidence = confidence
            row.source_modules = source_modules
            row.last_updated = datetime.now(UTC).replace(tzinfo=None)

        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def _preferred_sleep_memory(
        self,
        user_id: uuid.UUID,
        cutoff: date,
    ) -> tuple[MemoryType, str, dict, float, list[str]]:
        result = await self.db.execute(
            select(SleepRecord.bedtime, SleepRecord.wake_time)
            .where(SleepRecord.user_id == user_id)
            .where(SleepRecord.sleep_date >= cutoff)
            .order_by(SleepRecord.sleep_date.desc())
        )
        rows = result.all()

        if not rows:
            user = await self.db.get(User, user_id)
            wake = user.wake_time if user else "06:00"
            sleep = user.sleep_time if user else "22:30"
            return (
                MemoryType.PREFERENCE,
                "preferred_wake_sleep_time",
                {"wake_time": wake, "sleep_time": sleep, "source": "profile_default"},
                0.35,
                ["auth", "sleep"],
            )

        bed_minutes = [item.bedtime.hour * 60 + item.bedtime.minute for item in rows]
        wake_minutes = [item.wake_time.hour * 60 + item.wake_time.minute for item in rows]
        avg_bed = int(mean(bed_minutes))
        avg_wake = int(mean(wake_minutes))

        return (
            MemoryType.PREFERENCE,
            "preferred_wake_sleep_time",
            {
                "wake_time": f"{avg_wake // 60:02d}:{avg_wake % 60:02d}",
                "sleep_time": f"{avg_bed // 60:02d}:{avg_bed % 60:02d}",
                "samples": len(rows),
            },
            min(0.95, 0.45 + len(rows) / 60.0),
            ["sleep", "auth"],
        )

    async def _focus_hours_memory(
        self,
        user_id: uuid.UUID,
        cutoff: date,
    ) -> tuple[MemoryType, str, dict, float, list[str]]:
        result = await self.db.execute(
            select(StudySession.created_at, StudySession.comprehension_score)
            .where(StudySession.user_id == user_id)
            .where(StudySession.session_date >= cutoff)
        )
        hour_scores: dict[int, list[float]] = defaultdict(list)
        for created_at, comprehension in result.all():
            hour_scores[created_at.hour].append(float(comprehension))

        ranked = sorted(
            ((hour, mean(scores)) for hour, scores in hour_scores.items()),
            key=lambda item: item[1],
            reverse=True,
        )
        best_hours = [f"{hour:02d}:00" for hour, _ in ranked[:3]]

        return (
            MemoryType.PATTERN,
            "best_focus_hours",
            {
                "best_hours": best_hours,
                "hour_scores": {f"{hour:02d}:00": round(score, 2) for hour, score in ranked[:8]},
            },
            0.4 if not ranked else min(0.9, 0.5 + len(ranked) / 20.0),
            ["study"],
        )

    async def _procrastination_windows_memory(
        self,
        user_id: uuid.UUID,
        cutoff: date,
    ) -> tuple[MemoryType, str, dict, float, list[str]]:
        result = await self.db.execute(
            select(ProcrastinationSignal.signal_date, ProcrastinationSignal.created_at)
            .where(ProcrastinationSignal.user_id == user_id)
            .where(ProcrastinationSignal.signal_date >= cutoff)
        )
        day_counts: dict[str, int] = defaultdict(int)
        hour_counts: dict[str, int] = defaultdict(int)
        for signal_date, created_at in result.all():
            day_counts[signal_date.strftime("%A")] += 1
            hour_counts[f"{created_at.hour:02d}:00"] += 1

        top_days = sorted(day_counts.items(), key=lambda item: item[1], reverse=True)[:3]
        top_hours = sorted(hour_counts.items(), key=lambda item: item[1], reverse=True)[:3]

        return (
            MemoryType.PATTERN,
            "procrastination_windows",
            {
                "days": [day for day, _ in top_days],
                "hours": [hour for hour, _ in top_hours],
                "frequency": {**day_counts, **hour_counts},
            },
            0.35 if not top_days else min(0.9, 0.45 + sum(day_counts.values()) / 40.0),
            ["habits", "scheduler"],
        )

    async def _mood_before_after_events_memory(
        self,
        user_id: uuid.UUID,
        cutoff: date,
    ) -> tuple[MemoryType, str, dict, float, list[str]]:
        journal_rows = await self.db.execute(
            select(JournalEntry.entry_date, JournalEntry.mood)
            .where(JournalEntry.user_id == user_id)
            .where(JournalEntry.entry_date >= cutoff)
            .where(JournalEntry.mood.is_not(None))
        )
        mood_by_date: dict[date, float] = {}
        for entry_date, mood in journal_rows.all():
            mood_by_date[entry_date] = _MOOD_SCORE.get(mood, 55.0)

        workout_days_result = await self.db.execute(
            select(WorkoutLog.workout_date)
            .where(WorkoutLog.user_id == user_id)
            .where(WorkoutLog.workout_date >= cutoff)
        )
        workout_days = {item for item in workout_days_result.scalars().all()}

        with_event = [score for d, score in mood_by_date.items() if d in workout_days]
        without_event = [score for d, score in mood_by_date.items() if d not in workout_days]

        avg_with = round(mean(with_event), 2) if with_event else 0.0
        avg_without = round(mean(without_event), 2) if without_event else 0.0

        return (
            MemoryType.CORRELATION,
            "mood_before_after_key_events",
            {
                "avg_mood_on_workout_days": avg_with,
                "avg_mood_on_non_workout_days": avg_without,
                "delta": round(avg_with - avg_without, 2),
            },
            0.4 if not with_event else min(0.9, 0.5 + len(with_event) / 35.0),
            ["journal", "fitness"],
        )

    async def _energy_after_workout_memory(
        self,
        user_id: uuid.UUID,
        cutoff: date,
    ) -> tuple[MemoryType, str, dict, float, list[str]]:
        workout_days_result = await self.db.execute(
            select(WorkoutLog.workout_date)
            .where(WorkoutLog.user_id == user_id)
            .where(WorkoutLog.workout_date >= cutoff)
        )
        workout_days = sorted(set(workout_days_result.scalars().all()))

        signal_rows = await self.db.execute(
            select(ModuleSignal.recorded_at, ModuleSignal.value)
            .where(ModuleSignal.user_id == user_id)
            .where(ModuleSignal.source_module == "fitness")
            .where(ModuleSignal.signal_type == "energy")
            .where(
                ModuleSignal.recorded_at
                >= datetime.combine(cutoff, datetime.min.time(), tzinfo=UTC)
            )
        )

        by_day = defaultdict(list)
        for recorded_at, value in signal_rows.all():
            by_day[recorded_at.date()].append(float(value))

        next_day_energy = []
        for day in workout_days:
            target = day + timedelta(days=1)
            if target in by_day:
                next_day_energy.append(mean(by_day[target]))

        avg_energy = round(mean(next_day_energy), 2) if next_day_energy else 0.0
        return (
            MemoryType.CORRELATION,
            "energy_after_workouts",
            {
                "avg_next_day_energy": avg_energy,
                "workout_days_analyzed": len(workout_days),
            },
            0.4 if not next_day_energy else min(0.92, 0.5 + len(next_day_energy) / 30.0),
            ["fitness", "intelligence"],
        )

    async def _sleep_performance_memory(
        self,
        user_id: uuid.UUID,
        cutoff: date,
    ) -> tuple[MemoryType, str, dict, float, list[str]]:
        sleep_rows = await self.db.execute(
            select(SleepRecord.sleep_date, SleepRecord.sleep_duration_minutes)
            .where(SleepRecord.user_id == user_id)
            .where(SleepRecord.sleep_date >= cutoff)
        )
        sleep_map = {d: float(minutes) / 60.0 for d, minutes in sleep_rows.all()}

        study_rows = await self.db.execute(
            select(StudySession.session_date, StudySession.comprehension_score)
            .where(StudySession.user_id == user_id)
            .where(StudySession.session_date >= cutoff)
        )

        good_hours = []
        bad_hours = []
        for session_date, comprehension in study_rows.all():
            hours = sleep_map.get(session_date)
            if hours is None:
                continue
            if float(comprehension) >= 7.0:
                good_hours.append(hours)
            else:
                bad_hours.append(hours)

        return (
            MemoryType.CORRELATION,
            "sleep_hours_predicting_performance",
            {
                "avg_sleep_hours_good_performance": (
                    round(mean(good_hours), 2) if good_hours else 0.0
                ),
                "avg_sleep_hours_low_performance": round(mean(bad_hours), 2) if bad_hours else 0.0,
                "recommended_min_sleep_hours": round(mean(good_hours), 2) if good_hours else 7.0,
            },
            0.42 if not good_hours else min(0.9, 0.55 + len(good_hours) / 30.0),
            ["sleep", "study"],
        )

    async def _habits_good_days_memory(
        self,
        user_id: uuid.UUID,
        cutoff: date,
    ) -> tuple[MemoryType, str, dict, float, list[str]]:
        habit_rows = await self.db.execute(
            select(Habit.name, HabitCheckIn.check_date)
            .join(HabitCheckIn, HabitCheckIn.habit_id == Habit.id)
            .where(Habit.user_id == user_id)
            .where(HabitCheckIn.check_date >= cutoff)
            .where(HabitCheckIn.completed.is_(True))
            .where(HabitCheckIn.skipped.is_(False))
        )

        habits_by_day: dict[date, list[str]] = defaultdict(list)
        for habit_name, check_date in habit_rows.all():
            habits_by_day[check_date].append(habit_name)

        score_rows = await self.db.execute(
            select(LifeScore.computed_at, LifeScore.score)
            .where(LifeScore.user_id == user_id)
            .where(
                LifeScore.computed_at
                >= datetime.combine(cutoff, datetime.min.time(), tzinfo=UTC)
            )
        )
        scores_by_day: dict[date, list[float]] = defaultdict(list)
        for computed_at, score in score_rows.all():
            scores_by_day[computed_at.date()].append(float(score))

        habit_good_counts: dict[str, int] = defaultdict(int)
        for day, habit_names in habits_by_day.items():
            day_scores = scores_by_day.get(day, [])
            if not day_scores or mean(day_scores) < 70.0:
                continue
            for name in set(habit_names):
                habit_good_counts[name] += 1

        ranked = sorted(habit_good_counts.items(), key=lambda item: item[1], reverse=True)[:5]

        return (
            MemoryType.CORRELATION,
            "habits_correlated_with_good_days",
            {
                "top_habits": [name for name, _ in ranked],
                "co_occurrence_counts": {name: count for name, count in ranked},
            },
            0.4 if not ranked else min(0.92, 0.52 + sum(habit_good_counts.values()) / 60.0),
            ["habits", "intelligence"],
        )

    async def _generate_ai_insights(self, summary: list[dict]) -> list[str]:
        api_key = self.settings.gemini_api_key.get_secret_value()
        if not api_key:
            return self._fallback_insights(summary)

        prompt = (
            "Generate 3-5 concise personal behavior insights from this memory summary. "
            "Return only a JSON array of strings. Avoid medical diagnosis. "
            f"Memory summary: {json.dumps(summary, default=str)}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 280},
        }

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}

        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                raw = response.json()

            observe_ai_call(provider="gemini", duration_seconds=perf_counter() - started)

            text = raw["candidates"][0]["content"]["parts"][0]["text"]
            cleaned = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                out = [str(item).strip() for item in parsed if str(item).strip()]
                if out:
                    return out[:5]
        except Exception as exc:
            observe_ai_call(provider="gemini", duration_seconds=perf_counter() - started)
            logger.warning("memory_insights_ai_failed", error=str(exc))

        return self._fallback_insights(summary)

    @staticmethod
    def _fallback_insights(summary: list[dict]) -> list[str]:
        by_key = {item.get("key"): item.get("value", {}) for item in summary}

        insights: list[str] = []
        sleep = by_key.get("sleep_hours_predicting_performance", {})
        recommended_sleep = sleep.get("recommended_min_sleep_hours")
        if isinstance(recommended_sleep, (float, int)) and recommended_sleep > 0:
            insights.append(
                "Your best study performance tends to happen after around "
                f"{recommended_sleep:.1f} hours of sleep."
            )

        procrastination = by_key.get("procrastination_windows", {})
        top_days = procrastination.get("days") or []
        top_hours = procrastination.get("hours") or []
        if top_days and top_hours:
            insights.append(
                f"You procrastinate most on {top_days[0]} around {top_hours[0]}."
            )

        focus = by_key.get("best_focus_hours", {})
        best_hours = focus.get("best_hours") or []
        if best_hours:
            insights.append(f"Your strongest focus window is around {best_hours[0]}.")

        habits = by_key.get("habits_correlated_with_good_days", {})
        top_habits = habits.get("top_habits") or []
        if top_habits:
            insights.append(
                f"Days including {top_habits[0]} are more often associated with higher life scores."
            )

        if not insights:
            insights.append(
                "Keep logging your habits, sleep, and study sessions "
                "to unlock deeper personal insights."
            )

        return insights[:5]

"""
WILLIAM OS — Intelligence Service
Cross-module signal collection and adjustment evaluation.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from math import isfinite
from time import perf_counter
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from app.core.config import get_settings
from app.core.events import Event, EventType, event_bus
from app.core.metrics import observe_ai_call, set_life_score
from app.modules.auth.models import User
from app.modules.decisions.models import Decision
from app.modules.decisions.service import DecisionService
from app.modules.fitness.models import WorkoutLog
from app.modules.fitness.service import FitnessService
from app.modules.habits.models import Habit, HabitCheckIn
from app.modules.habits.service import HabitsService
from app.modules.intelligence.models import CrossModuleRule, LifeScore, ModuleSignal
from app.modules.intelligence.schemas import (
    AdjustmentItem,
    AdjustmentsResponse,
    CrossModuleRuleCreate,
    CrossModuleRuleResponse,
    LifeScoreHistoryPoint,
    LifeScoreResponse,
    ModuleSignalResponse,
    TimelineEvent,
)
from app.modules.journal.models import JournalEntry
from app.modules.journal.service import JournalService
from app.modules.medicine.service import MedicineService
from app.modules.sleep.models import SleepRecord
from app.modules.sleep.service import SleepService
from app.modules.study.models import StudySession
from app.modules.study.service import StudyService
from app.modules.trading.models import TradeLog
from app.modules.trading.service import TradingService
from sqlalchemy import select

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


logger = structlog.get_logger(__name__)


MOOD_SCORE = {
    "great": 90.0,
    "good": 75.0,
    "okay": 55.0,
    "low": 35.0,
    "bad": 20.0,
}

LIFE_SCORE_WEIGHTS = {
    "sleep": 0.20,
    "habits": 0.20,
    "fitness": 0.15,
    "study": 0.15,
    "medicine": 0.10,
    "journal": 0.10,
    "decisions": 0.10,
}


class IntelligenceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def collect_signals(self, user_id: uuid.UUID) -> list[ModuleSignalResponse]:
        now = datetime.now(UTC)
        collected: list[ModuleSignalResponse] = []

        for source_module, signal_type, value in await self._gather_signal_triplets(user_id):
            signal = ModuleSignal(
                user_id=user_id,
                source_module=source_module,
                signal_type=signal_type,
                value=self._normalize_value(value),
                recorded_at=now,
            )
            self.db.add(signal)
            await self.db.flush()
            await self.db.refresh(signal)
            collected.append(ModuleSignalResponse.model_validate(signal))

        await event_bus.publish(
            Event(
                type=EventType.INTELLIGENCE_SIGNALS_COLLECTED,
                data={"count": len(collected)},
                user_id=user_id,
            )
        )

        return collected

    async def list_signals(
        self,
        user_id: uuid.UUID,
        source_module: str | None = None,
        signal_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ModuleSignalResponse]:
        query = select(ModuleSignal).where(ModuleSignal.user_id == user_id)
        if source_module:
            query = query.where(ModuleSignal.source_module == source_module)
        if signal_type:
            query = query.where(ModuleSignal.signal_type == signal_type)

        query = query.order_by(ModuleSignal.recorded_at.desc(), ModuleSignal.created_at.desc())
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return [ModuleSignalResponse.model_validate(item) for item in result.scalars().all()]

    async def create_rule(self, data: CrossModuleRuleCreate) -> CrossModuleRuleResponse:
        rule = CrossModuleRule(**data.model_dump())
        self.db.add(rule)
        await self.db.flush()
        await self.db.refresh(rule)
        return CrossModuleRuleResponse.model_validate(rule)

    async def apply_cross_rules(self, user_id: uuid.UUID) -> list[AdjustmentItem]:
        latest = await self._latest_signal_lookup(user_id)
        adjustments: list[AdjustmentItem] = []

        sleep_quality = self._signal_value(latest, "sleep", "energy", fallback=100.0)
        if sleep_quality < 60.0:
            adjustments.append(
                AdjustmentItem(
                    rule_name="sleep_quality_reduces_study_workload",
                    affected_module="study",
                    field="workload_recommendation",
                    operation="multiply",
                    value=0.7,
                )
            )

        medicine_missed_today = self._signal_value(latest, "medicine", "risk", fallback=0.0) >= 50.0
        if medicine_missed_today:
            adjustments.append(
                AdjustmentItem(
                    rule_name="medicine_missed_reduces_energy",
                    affected_module="energy",
                    field="score_prediction",
                    operation="decrement",
                    value=10.0,
                )
            )

        trading_stress = self._signal_value(latest, "trading", "stress", fallback=0.0)
        if trading_stress > 70.0:
            adjustments.append(
                AdjustmentItem(
                    rule_name="trading_stress_lowers_fitness_intensity",
                    affected_module="fitness",
                    field="suggested_intensity",
                    operation="set",
                    value=1.0,
                    target_label="light",
                )
            )

        habits_streak_drop = self._signal_value(latest, "habits", "risk", fallback=0.0) >= 50.0
        if habits_streak_drop:
            adjustments.append(
                AdjustmentItem(
                    rule_name="habit_streak_drop_increases_scheduler_risk",
                    affected_module="scheduler",
                    field="procrastination_risk",
                    operation="increment",
                    value=15.0,
                )
            )

        journal_mood = self._signal_value(latest, "journal", "mood", fallback=100.0)
        if journal_mood < 40.0:
            adjustments.append(
                AdjustmentItem(
                    rule_name="low_mood_reduces_decision_confidence",
                    affected_module="decisions",
                    field="confidence_modifier",
                    operation="decrement",
                    value=0.2,
                )
            )

        sleep_debt_hours = self._signal_value(latest, "sleep", "risk", fallback=0.0)
        if sleep_debt_hours > 2.0:
            adjustments.append(
                AdjustmentItem(
                    rule_name="sleep_debt_reduces_study_focus",
                    affected_module="study",
                    field="focus_score",
                    operation="multiply",
                    value=0.75,
                )
            )

        custom_rules = await self._list_active_rules()
        for rule in custom_rules:
            if self._rule_matches(rule, latest):
                adjustments.append(
                    AdjustmentItem(
                        rule_name=f"custom_rule_{rule.id}",
                        affected_module=rule.affected_module,
                        field=str(rule.trigger_condition.get("target_field", "custom_adjustment")),
                        operation=rule.adjustment_type,
                        value=rule.adjustment_value,
                    )
                )

        if adjustments:
            await event_bus.publish(
                Event(
                    type=EventType.INTELLIGENCE_RULES_APPLIED,
                    data={"count": len(adjustments)},
                    user_id=user_id,
                )
            )

        return adjustments

    async def get_active_adjustments(self, user_id: uuid.UUID) -> AdjustmentsResponse:
        adjustments = await self.apply_cross_rules(user_id)
        grouped: dict[str, list[AdjustmentItem]] = defaultdict(list)
        for item in adjustments:
            grouped[item.affected_module].append(item)

        return AdjustmentsResponse(
            generated_at=datetime.now(UTC),
            count=len(adjustments),
            adjustments=dict(grouped),
        )

    async def get_timeline(
        self,
        user_id: uuid.UUID,
        days: int = 90,
    ) -> list[TimelineEvent]:
        window_days = max(1, days)
        start_date = date.today() - timedelta(days=window_days - 1)
        start_dt = datetime.combine(start_date, datetime.min.time())

        timeline: list[TimelineEvent] = []

        sleep_rows = await self.db.execute(
            select(SleepRecord)
            .where(SleepRecord.user_id == user_id)
            .where(SleepRecord.sleep_date >= start_date)
            .order_by(SleepRecord.sleep_date.desc())
        )
        for row in sleep_rows.scalars().all():
            duration_hours = round(float(row.sleep_duration_minutes) / 60.0, 2)
            timeline.append(
                TimelineEvent(
                    date=row.sleep_date,
                    type="sleep",
                    value=duration_hours,
                    label=f"Slept {duration_hours:.1f}h",
                    metadata={"quality": float(row.sleep_quality)},
                )
            )

        habit_count_result = await self.db.execute(
            select(Habit.id).where(Habit.user_id == user_id).where(Habit.is_active.is_(True))
        )
        total_habits = len(habit_count_result.scalars().all())
        checkin_rows = await self.db.execute(
            select(HabitCheckIn)
            .join(Habit, Habit.id == HabitCheckIn.habit_id)
            .where(Habit.user_id == user_id)
            .where(HabitCheckIn.check_date >= start_date)
            .order_by(HabitCheckIn.check_date.asc())
        )
        by_day: dict[date, int] = defaultdict(int)
        for row in checkin_rows.scalars().all():
            if row.completed and not row.skipped:
                by_day[row.check_date] += 1

        streak = 0
        for day in sorted(by_day.keys()):
            completed = by_day.get(day, 0)
            completion_pct = (
                round((completed / total_habits) * 100.0, 2) if total_habits > 0 else 0.0
            )
            if total_habits > 0 and completion_pct >= 100.0:
                streak += 1
            else:
                streak = 0
            timeline.append(
                TimelineEvent(
                    date=day,
                    type="habits",
                    value=completion_pct,
                    label=f"{completed}/{total_habits} habits",
                    metadata={"streak": streak, "completed": completed, "total": total_habits},
                )
            )

        journal_rows = await self.db.execute(
            select(JournalEntry)
            .where(JournalEntry.user_id == user_id)
            .where(JournalEntry.entry_date >= start_date)
            .order_by(JournalEntry.entry_date.desc())
        )
        for row in journal_rows.scalars().all():
            mood = str(row.mood.value if row.mood else "okay")
            timeline.append(
                TimelineEvent(
                    date=row.entry_date,
                    type="mood",
                    value=float(MOOD_SCORE.get(mood.lower(), 55.0)),
                    label=mood,
                    metadata={"mood": mood},
                )
            )

        trade_rows = await self.db.execute(
            select(TradeLog)
            .where(TradeLog.user_id == user_id)
            .where(TradeLog.trade_date >= start_date)
            .order_by(TradeLog.trade_date.desc(), TradeLog.created_at.desc())
        )
        for row in trade_rows.scalars().all():
            action = str(row.action or "").lower()
            pnl = float(row.total_value if action == "sell" else -row.total_value)
            sign = "+" if pnl >= 0 else "-"
            timeline.append(
                TimelineEvent(
                    date=row.trade_date,
                    type="trade",
                    value=pnl,
                    label=f"Trade: {sign}${abs(pnl):.2f}",
                    metadata={"symbol": row.symbol, "action": row.action},
                )
            )

        decision_rows = await self.db.execute(
            select(Decision)
            .where(Decision.user_id == user_id)
            .where(Decision.created_at >= start_dt)
            .order_by(Decision.created_at.desc())
        )
        for row in decision_rows.scalars().all():
            status = str(row.status or "").lower()
            is_completed = (
                status in {"reviewed", "completed", "closed"}
                or row.reviewed_at is not None
                or row.outcome_rating is not None
            )
            if not is_completed:
                continue
            event_date = (
                row.reviewed_at.date()
                if row.reviewed_at is not None
                else row.chosen_at.date()
                if row.chosen_at is not None
                else row.created_at.date()
            )
            if event_date < start_date:
                continue
            timeline.append(
                TimelineEvent(
                    date=event_date,
                    type="decision",
                    value=float(row.outcome_rating or 0.0),
                    label=row.title,
                    metadata={"status": row.status},
                )
            )

        score_rows = await self.db.execute(
            select(LifeScore)
            .where(LifeScore.user_id == user_id)
            .where(LifeScore.computed_at >= start_dt)
            .order_by(LifeScore.computed_at.desc())
        )
        for row in score_rows.scalars().all():
            timeline.append(
                TimelineEvent(
                    date=row.computed_at.date(),
                    type="life_score",
                    value=float(row.score),
                    label=f"Score: {round(float(row.score))}",
                    metadata={"components": row.component_scores or {}},
                )
            )

        workout_rows = await self.db.execute(
            select(WorkoutLog)
            .where(WorkoutLog.user_id == user_id)
            .where(WorkoutLog.workout_date >= start_date)
            .order_by(WorkoutLog.workout_date.desc())
        )
        for row in workout_rows.scalars().all():
            timeline.append(
                TimelineEvent(
                    date=row.workout_date,
                    type="workout",
                    value=float(row.duration_minutes),
                    label=f"Workout: {row.duration_minutes}min",
                    metadata={"workout_type": row.workout_type},
                )
            )

        study_rows = await self.db.execute(
            select(StudySession)
            .where(StudySession.user_id == user_id)
            .where(StudySession.session_date >= start_date)
            .order_by(StudySession.session_date.desc())
        )
        for row in study_rows.scalars().all():
            comprehension = float(row.comprehension_score or 0.0)
            timeline.append(
                TimelineEvent(
                    date=row.session_date,
                    type="study",
                    value=comprehension,
                    label=f"Study: {comprehension:.0f}% comprehension",
                    metadata={"duration_minutes": row.duration_minutes},
                )
            )

        timeline.sort(key=lambda item: (item.date, item.type), reverse=True)
        return timeline

    async def ask_timeline(self, user_id: uuid.UUID, question: str) -> dict[str, object]:
        timeline = await self.get_timeline(user_id=user_id, days=90)
        if not timeline:
            return {
                "answer": (
                    "Not enough timeline data yet. Start logging sleep, habits, "
                    "and workouts to unlock this analysis."
                ),
                "relevant_dates": [],
            }

        user = await self.db.get(User, user_id)
        name = "User"
        if user is not None:
            name = str(user.display_name or user.full_name or user.username)

        timeline_summary = self._build_timeline_summary(timeline)
        answer = await self._ask_gemini_timeline(
            name=name,
            question=question,
            timeline_summary=timeline_summary,
        )
        relevant_dates = self._extract_relevant_dates(timeline)
        return {"answer": answer, "relevant_dates": relevant_dates}

    async def _ask_gemini_timeline(self, name: str, question: str, timeline_summary: str) -> str:
        api_key = self.settings.gemini_api_key.get_secret_value()
        if not api_key:
            return self._fallback_timeline_answer(
                question=question,
                timeline_summary=timeline_summary,
            )

        prompt = (
            f"You are William Salvator analyzing {name}'s life data.\n"
            f"Question: {question}\n"
            f"Timeline data (last 90 days): {timeline_summary}\n"
            "Answer directly with specific dates and numbers. Max 3 sentences."
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": 220,
            },
        }

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )

        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                    json=payload,
                )
                response.raise_for_status()
                raw = response.json()

            observe_ai_call(provider="gemini", duration_seconds=perf_counter() - started)
            text = raw["candidates"][0]["content"]["parts"][0]["text"]
            cleaned = " ".join(str(text).strip().split())
            return cleaned or self._fallback_timeline_answer(
                question=question,
                timeline_summary=timeline_summary,
            )
        except Exception as exc:
            observe_ai_call(provider="gemini", duration_seconds=perf_counter() - started)
            logger.warning("ask_timeline_failed", error=str(exc))
            return self._fallback_timeline_answer(
                question=question,
                timeline_summary=timeline_summary,
            )

    @staticmethod
    def _extract_relevant_dates(timeline: list[TimelineEvent]) -> list[str]:
        dates: list[str] = []
        seen: set[str] = set()
        for event in timeline:
            value = event.date.isoformat()
            if value in seen:
                continue
            seen.add(value)
            dates.append(value)
            if len(dates) >= 6:
                break
        return dates

    @staticmethod
    def _build_timeline_summary(timeline: list[TimelineEvent]) -> str:
        lines: list[str] = []
        for event in timeline[:240]:
            lines.append(
                f"{event.date.isoformat()} | {event.type} | value={event.value:.2f} | {event.label}"
            )
        return "\n".join(lines)

    @staticmethod
    def _fallback_timeline_answer(question: str, timeline_summary: str) -> str:
        _ = question
        if not timeline_summary:
            return "I do not have enough timeline data to answer that yet."
        return (
            "From the recent timeline, your strongest periods align with "
            "higher life-score and sleep consistency days. "
            "Your weaker periods show clustered low-sleep and low-completion habit events. "
            "Ask about a specific month or module and I will narrow it with exact dates."
        )

    async def _gather_signal_triplets(
        self,
        user_id: uuid.UUID,
    ) -> list[tuple[str, str, float]]:
        triplets: list[tuple[str, str, float]] = []
        today = date.today()

        sleep_service = SleepService(self.db)
        sleep_stats = await sleep_service.get_sleep_stats(user_id=user_id)
        sleep_quality_score = float(sleep_stats.avg_quality_30d) * 10.0
        sleep_debt_hours = max(0.0, round((450.0 - float(sleep_stats.avg_duration)) / 60.0, 2))
        triplets.extend(
            [
                ("sleep", "energy", sleep_quality_score),
                ("sleep", "risk", sleep_debt_hours),
            ]
        )

        habits_service = HabitsService(self.db)
        habits = await habits_service.list_habits(
            user_id=user_id,
            active_only=True,
            limit=200,
            offset=0,
        )
        streak_drop = any(
            (habit.best_streak or 0) >= 3 and (habit.current_streak or 0) == 0 for habit in habits
        )
        consistency = 0.0
        if habits:
            consistent_count = sum(1 for habit in habits if (habit.current_streak or 0) > 0)
            consistency = (consistent_count / len(habits)) * 100.0
        triplets.extend(
            [
                ("habits", "risk", 100.0 if streak_drop else 0.0),
                ("habits", "focus", consistency),
            ]
        )

        medicine_service = MedicineService(self.db)
        medicine_stats = await medicine_service.get_adherence_stats(user_id=user_id, days=1)
        medicine_missed = 100.0 if medicine_stats.total_skipped > 0 else 0.0
        triplets.extend(
            [
                ("medicine", "risk", medicine_missed),
                ("medicine", "energy", float(medicine_stats.adherence_rate)),
            ]
        )

        fitness_service = FitnessService(self.db)
        fitness_summary = await fitness_service.get_daily_summary(
            user_id=user_id,
            target_date=today,
        )
        stress_level = float(fitness_summary.stress or 0.0)
        energy_projection = 65.0 if stress_level <= 0 else max(0.0, 100.0 - (stress_level * 10.0))
        triplets.append(("fitness", "energy", energy_projection))

        trading_service = TradingService(self.db)
        trade_analysis = await trading_service.analyze_trades(user_id=user_id, days=7)
        trading_stress = self._calculate_trading_stress(
            total_trades=trade_analysis.total_trades,
            win_rate=trade_analysis.win_rate,
            avg_return=trade_analysis.avg_return,
        )
        triplets.append(("trading", "stress", trading_stress))

        journal_service = JournalService(self.db)
        journal_entries = await journal_service.list_entries(user_id=user_id, limit=14, offset=0)
        mood_values = [
            MOOD_SCORE.get(str(entry.mood).lower(), 55.0)
            for entry in journal_entries
            if entry.mood is not None
        ]
        mood_score = sum(mood_values) / len(mood_values) if mood_values else 55.0
        triplets.append(("journal", "mood", mood_score))

        study_service = StudyService(self.db)
        study_progress = await study_service.get_progress(user_id=user_id)
        if study_progress:
            avg_comprehension = sum(item.avg_comprehension for item in study_progress) / len(
                study_progress
            )
            due_penalty = min(20.0, sum(item.cards_due for item in study_progress) * 2.0)
            focus_score = max(0.0, (avg_comprehension * 10.0) - due_penalty)
        else:
            focus_score = 50.0
        triplets.append(("study", "focus", focus_score))

        decision_service = DecisionService(self.db)
        decision_stats = await decision_service.get_decision_quality(user_id=user_id)
        confidence = decision_stats.ai_agreement_rate if decision_stats.total > 0 else 50.0
        triplets.append(("decisions", "focus", confidence))

        return triplets

    async def _latest_signal_lookup(self, user_id: uuid.UUID) -> dict[tuple[str, str], float]:
        result = await self.db.execute(
            select(ModuleSignal)
            .where(ModuleSignal.user_id == user_id)
            .order_by(ModuleSignal.recorded_at.desc(), ModuleSignal.created_at.desc())
        )
        rows = result.scalars().all()

        latest: dict[tuple[str, str], float] = {}
        for row in rows:
            key = (row.source_module, row.signal_type)
            if key not in latest:
                latest[key] = float(row.value)
        return latest

    async def _list_active_rules(self) -> list[CrossModuleRule]:
        result = await self.db.execute(
            select(CrossModuleRule).where(CrossModuleRule.is_active.is_(True))
        )
        return list(result.scalars().all())

    @staticmethod
    def _signal_value(
        latest: dict[tuple[str, str], float],
        source_module: str,
        signal_type: str,
        fallback: float,
    ) -> float:
        return float(latest.get((source_module, signal_type), fallback))

    @staticmethod
    def _normalize_value(raw: Any) -> float:
        value = float(raw)
        if not isfinite(value):
            return 0.0
        return value

    @staticmethod
    def _calculate_trading_stress(total_trades: int, win_rate: float, avg_return: float) -> float:
        score = 20.0
        if total_trades >= 5:
            score += 25.0
        if total_trades >= 10:
            score += 10.0
        if win_rate < 40.0:
            score += 20.0
        if avg_return < 0.0:
            score += 20.0
        return max(0.0, min(100.0, score))

    @staticmethod
    def _rule_matches(
        rule: CrossModuleRule,
        latest: dict[tuple[str, str], float],
    ) -> bool:
        condition = rule.trigger_condition or {}
        signal_type = str(condition.get("signal_type", "risk"))
        operator = str(condition.get("operator", "gt"))
        threshold = float(condition.get("threshold", 0.0))

        current_value = float(latest.get((rule.trigger_module, signal_type), 0.0))

        if operator == "lt":
            return current_value < threshold
        if operator == "lte":
            return current_value <= threshold
        if operator == "gte":
            return current_value >= threshold
        if operator == "eq":
            return current_value == threshold
        return current_value > threshold


class LifeScoreService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def compute_score(self, user_id: uuid.UUID) -> LifeScoreResponse:
        intelligence_service = IntelligenceService(self.db)
        await intelligence_service.collect_signals(user_id=user_id)
        latest = await intelligence_service._latest_signal_lookup(user_id)

        component_scores = self._compute_component_scores(latest)
        score = round(
            sum(component_scores[key] * LIFE_SCORE_WEIGHTS[key] for key in LIFE_SCORE_WEIGHTS),
            2,
        )

        explanation = await self.generate_explanation(score=score, components=component_scores)

        life_score = LifeScore(
            user_id=user_id,
            score=score,
            component_scores=component_scores,
            explanation=explanation,
            computed_at=datetime.now(UTC),
        )
        self.db.add(life_score)
        await self.db.flush()
        await self.db.refresh(life_score)
        set_life_score(user_id=user_id, score=score)

        await event_bus.publish(
            Event(
                type=EventType.INTELLIGENCE_LIFE_SCORE_COMPUTED,
                data={"score": score, "components": component_scores},
                user_id=user_id,
            )
        )

        return LifeScoreResponse.model_validate(life_score)

    async def get_latest_score(self, user_id: uuid.UUID) -> LifeScoreResponse:
        result = await self.db.execute(
            select(LifeScore)
            .where(LifeScore.user_id == user_id)
            .order_by(LifeScore.computed_at.desc(), LifeScore.created_at.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()

        if latest:
            age = timedelta.max
            if latest.computed_at:
                computed_at = latest.computed_at
                if computed_at.tzinfo is None:
                    computed_at = computed_at.replace(tzinfo=UTC)
                age = datetime.now(UTC) - computed_at
            if age <= timedelta(minutes=180):
                return LifeScoreResponse.model_validate(latest)

        return await self.compute_score(user_id=user_id)

    async def get_score_history(
        self,
        user_id: uuid.UUID,
        days: int = 30,
    ) -> list[LifeScoreHistoryPoint]:
        cutoff = datetime.now(UTC) - timedelta(days=max(1, days))
        result = await self.db.execute(
            select(LifeScore)
            .where(LifeScore.user_id == user_id)
            .where(LifeScore.computed_at >= cutoff)
            .order_by(LifeScore.computed_at.asc(), LifeScore.created_at.asc())
        )
        rows = result.scalars().all()

        return [
            LifeScoreHistoryPoint(score=float(row.score), computed_at=row.computed_at)
            for row in rows
        ]

    async def generate_explanation(self, score: float, components: dict[str, float]) -> str:
        api_key = self.settings.gemini_api_key.get_secret_value()
        if not api_key:
            return self._fallback_explanation(score=score, components=components)

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are a personal wellbeing coach. "
                                "Write exactly 2 concise sentences explaining a life score.\n"
                                f"Score: {score}\n"
                                f"Components: {json.dumps(components)}\n"
                                "Mention top weakness and one recovery-positive signal."
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 180,
            },
        }

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )

        try:
            started = perf_counter()
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                    json=payload,
                )
                response.raise_for_status()
                raw = response.json()

            text = raw["candidates"][0]["content"]["parts"][0]["text"]
            observe_ai_call(provider="gemini", duration_seconds=perf_counter() - started)
            return self._normalize_explanation(text=text, score=score, components=components)
        except Exception as exc:
            observe_ai_call(provider="gemini", duration_seconds=perf_counter() - started)
            logger.warning("life_score_explanation_failed", error=str(exc))
            return self._fallback_explanation(score=score, components=components)

    @staticmethod
    def _compute_component_scores(latest: dict[tuple[str, str], float]) -> dict[str, float]:
        sleep_energy = float(latest.get(("sleep", "energy"), 50.0))
        sleep_debt = float(latest.get(("sleep", "risk"), 0.0))
        sleep_score = LifeScoreService._clamp_score(sleep_energy - min(40.0, sleep_debt * 10.0))

        habits_focus = float(latest.get(("habits", "focus"), 50.0))
        habits_risk = float(latest.get(("habits", "risk"), 0.0))
        habits_score = LifeScoreService._clamp_score(habits_focus - (habits_risk * 0.3))

        fitness_score = LifeScoreService._clamp_score(
            float(latest.get(("fitness", "energy"), 50.0))
        )
        study_score = LifeScoreService._clamp_score(float(latest.get(("study", "focus"), 50.0)))

        medicine_adherence = float(latest.get(("medicine", "energy"), 50.0))
        medicine_risk = float(latest.get(("medicine", "risk"), 0.0))
        medicine_score = LifeScoreService._clamp_score(medicine_adherence - (medicine_risk * 0.2))

        journal_score = LifeScoreService._clamp_score(float(latest.get(("journal", "mood"), 55.0)))
        decisions_score = LifeScoreService._clamp_score(
            float(latest.get(("decisions", "focus"), 50.0))
        )

        return {
            "sleep": round(sleep_score, 2),
            "habits": round(habits_score, 2),
            "fitness": round(fitness_score, 2),
            "study": round(study_score, 2),
            "medicine": round(medicine_score, 2),
            "journal": round(journal_score, 2),
            "decisions": round(decisions_score, 2),
        }

    @staticmethod
    def _clamp_score(value: float) -> float:
        return max(0.0, min(100.0, value))

    def _normalize_explanation(self, text: str, score: float, components: dict[str, float]) -> str:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return self._fallback_explanation(score=score, components=components)

        sentences: list[str] = []
        current = ""
        for char in cleaned:
            current += char
            if char in ".!?":
                candidate = current.strip()
                if candidate:
                    sentences.append(candidate)
                current = ""

        if current.strip():
            sentences.append(current.strip() + ".")

        if not sentences:
            return self._fallback_explanation(score=score, components=components)
        if len(sentences) == 1:
            sentences.append("Keep improving your lowest component to raise tomorrow's score.")

        return " ".join(sentences[:2])

    def _fallback_explanation(self, score: float, components: dict[str, float]) -> str:
        ranked = sorted(components.items(), key=lambda item: item[1])
        low_name, low_score = ranked[0]
        high_name, high_score = ranked[-1]
        return (
            f"Your Life Score is {score:.1f}, "
            f"with the biggest drag from {low_name} ({low_score:.0f}). "
        ) + (
            f"Your strongest area is {high_name} ({high_score:.0f}), "
            "so keep that consistency while fixing the weakest area."
        )

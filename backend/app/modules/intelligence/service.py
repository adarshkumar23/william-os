"""
WILLIAM OS — Intelligence Service
Cross-module signal collection and adjustment evaluation.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from math import isfinite
from typing import TYPE_CHECKING, Any

from app.core.events import Event, EventType, event_bus
from app.modules.decisions.service import DecisionService
from app.modules.fitness.service import FitnessService
from app.modules.habits.service import HabitsService
from app.modules.intelligence.models import CrossModuleRule, ModuleSignal
from app.modules.intelligence.schemas import (
    AdjustmentItem,
    AdjustmentsResponse,
    CrossModuleRuleCreate,
    CrossModuleRuleResponse,
    ModuleSignalResponse,
)
from app.modules.journal.service import JournalService
from app.modules.medicine.service import MedicineService
from app.modules.sleep.service import SleepService
from app.modules.study.service import StudyService
from app.modules.trading.service import TradingService
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    import uuid


MOOD_SCORE = {
    "great": 90.0,
    "good": 75.0,
    "okay": 55.0,
    "low": 35.0,
    "bad": 20.0,
}


class IntelligenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

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
            (habit.best_streak or 0) >= 3 and (habit.current_streak or 0) == 0
            for habit in habits
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
            avg_comprehension = sum(
                item.avg_comprehension for item in study_progress
            ) / len(study_progress)
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

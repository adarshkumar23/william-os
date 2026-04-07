"""WILLIAM OS - User automation rules service."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import structlog
from app.modules.fitness.models import WorkoutLog
from app.modules.gamification.service import GamificationService
from app.modules.habits.models import Habit
from app.modules.journal.models import JournalEntry, JournalMood
from app.modules.messaging.schemas import NotificationPayload
from app.modules.messaging.service import MessagingService
from app.modules.rules.models import RuleExecutionLog, UserRule
from app.modules.rules.schemas import (
    RuleCreate,
    RuleEvaluateResponse,
    RuleExecutionLogResponse,
    RuleResponse,
    RuleTemplate,
    RuleUpdate,
)
from app.modules.scheduler.schemas import RescheduleRequest
from app.modules.scheduler.service import SchedulerService
from app.modules.sleep.models import SleepRecord
from app.modules.study.models import MockTest
from app.modules.trading.models import PortfolioSnapshot, Watchlist
from app.shared.types import NotFoundError
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

_MOOD_SCORE = {
    JournalMood.GREAT: 90.0,
    JournalMood.GOOD: 75.0,
    JournalMood.OKAY: 55.0,
    JournalMood.LOW: 35.0,
    JournalMood.BAD: 20.0,
}

PREBUILT_RULE_TEMPLATES: list[RuleTemplate] = [
    RuleTemplate(
        name="If sleep < 5 hours -> reduce today's workload by 30%",
        trigger_module="sleep",
        trigger_condition={"field": "sleep_hours", "operator": "<", "value": 5},
        action_module="scheduler",
        action_type="reduce_workload",
        action_params={"reduction_percent": 30},
    ),
    RuleTemplate(
        name="If missed gym 3 days in a row -> send harder reminder",
        trigger_module="fitness",
        trigger_condition={"field": "missed_gym_streak_days", "operator": ">=", "value": 3},
        action_module="messaging",
        action_type="send_harder_reminder",
        action_params={
            "title": "Gym streak broken",
            "message": "You missed 3 days. Time to reset momentum now.",
        },
    ),
    RuleTemplate(
        name="If portfolio drops 10% -> disable trading alerts for 24h",
        trigger_module="trading",
        trigger_condition={"field": "portfolio_drop_pct", "operator": "<=", "value": -10},
        action_module="trading",
        action_type="disable_alerts_temporarily",
        action_params={"hours": 24},
    ),
    RuleTemplate(
        name="If mood < 40 for 4 days -> activate recovery mode",
        trigger_module="journal",
        trigger_condition={"field": "low_mood_streak_days", "operator": ">=", "value": 4},
        action_module="scheduler",
        action_type="activate_recovery_mode",
        action_params={"insert_recovery_block": True},
    ),
    RuleTemplate(
        name="If exam in 7 days -> increase study blocks by 2 per day",
        trigger_module="study",
        trigger_condition={"field": "upcoming_exams_7d", "operator": ">=", "value": 1},
        action_module="scheduler",
        action_type="increase_study_blocks",
        action_params={"extra_blocks": 2},
    ),
    RuleTemplate(
        name="If habit streak > 7 days -> award bonus XP",
        trigger_module="habits",
        trigger_condition={"field": "max_habit_streak", "operator": ">", "value": 7},
        action_module="gamification",
        action_type="award_bonus_xp",
        action_params={"xp": 40},
    ),
]


class RulesService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.messaging = MessagingService(db)
        self.scheduler = SchedulerService(db)

    async def list_templates(self) -> list[RuleTemplate]:
        return PREBUILT_RULE_TEMPLATES

    async def create_rule(self, user_id: uuid.UUID, rule_data: RuleCreate) -> RuleResponse:
        row = UserRule(user_id=user_id, **rule_data.model_dump())
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return RuleResponse.model_validate(row)

    async def list_rules(self, user_id: uuid.UUID) -> list[RuleResponse]:
        result = await self.db.execute(
            select(UserRule)
            .where(UserRule.user_id == user_id)
            .order_by(desc(UserRule.updated_at), desc(UserRule.created_at))
        )
        rows = result.scalars().all()
        return [RuleResponse.model_validate(item) for item in rows]

    async def update_rule(
        self,
        user_id: uuid.UUID,
        rule_id: uuid.UUID,
        data: RuleUpdate,
    ) -> RuleResponse:
        row = await self._get_rule(user_id=user_id, rule_id=rule_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        await self.db.flush()
        await self.db.refresh(row)
        return RuleResponse.model_validate(row)

    async def delete_rule(self, user_id: uuid.UUID, rule_id: uuid.UUID) -> None:
        row = await self._get_rule(user_id=user_id, rule_id=rule_id)
        await self.db.delete(row)
        await self.db.flush()

    async def evaluate_rules(self, user_id: uuid.UUID) -> RuleEvaluateResponse:
        context = await self._build_context(user_id=user_id)
        result = await self.db.execute(
            select(UserRule)
            .where(UserRule.user_id == user_id)
            .where(UserRule.is_active.is_(True))
            .order_by(UserRule.created_at.asc())
        )
        rules = result.scalars().all()

        logs: list[RuleExecutionLogResponse] = []
        matched_count = 0
        executed_count = 0

        for rule in rules:
            matched = self._matches_condition(rule.trigger_condition or {}, context)
            action_success = False
            action_result: dict = {}
            error: str | None = None

            if matched:
                matched_count += 1
                try:
                    action_result = await self.execute_action(rule=rule, context=context)
                    action_success = True
                    executed_count += 1
                    rule.last_triggered = datetime.now(UTC)
                except Exception as exc:
                    logger.warning(
                        "rule_execution_failed",
                        user_id=str(user_id),
                        rule_id=str(rule.id),
                        error=str(exc),
                    )
                    error = str(exc)

            log_row = RuleExecutionLog(
                user_id=user_id,
                rule_id=rule.id,
                matched=matched,
                action_success=action_success,
                context_snapshot=context,
                action_result=action_result,
                error=error,
                executed_at=datetime.now(UTC),
            )
            self.db.add(log_row)
            await self.db.flush()
            await self.db.refresh(log_row)
            logs.append(RuleExecutionLogResponse.model_validate(log_row))

        return RuleEvaluateResponse(
            evaluated=len(rules),
            matched=matched_count,
            executed=executed_count,
            logs=logs,
        )

    async def execute_action(self, rule: UserRule, context: dict) -> dict:
        action_module = rule.action_module.lower().strip()
        action_type = rule.action_type.lower().strip()
        action_params = rule.action_params or {}

        if action_module == "scheduler" and action_type == "reduce_workload":
            reduction = float(action_params.get("reduction_percent") or 30)
            await self.scheduler.reschedule(
                user_id=rule.user_id,
                plan_date=date.today(),
                request=RescheduleRequest(
                    reason=f"Rule triggered: {rule.name}",
                    trigger="rule",
                    new_constraints={
                        "intensity": "reduced",
                        "workload_reduction_pct": reduction,
                    },
                ),
            )
            return {"schedule_adjusted": True, "workload_reduction_pct": reduction}

        if action_module == "messaging" and action_type == "send_harder_reminder":
            payload = NotificationPayload(
                title=str(action_params.get("title") or "Action required"),
                body=str(action_params.get("message") or "Please get back on track now."),
                notification_type="rule_automation",
                data={"rule_id": str(rule.id), "rule_name": rule.name, "context": context},
            )
            notif = await self.messaging.send_notification(user_id=rule.user_id, payload=payload)
            return {"notification_id": str(notif.id), "delivered": notif.delivered}

        if action_module == "trading" and action_type == "disable_alerts_temporarily":
            mute_hours = int(action_params.get("hours") or 24)
            mute_until = datetime.now(UTC) + timedelta(hours=mute_hours)
            rows = await self.db.execute(
                select(Watchlist)
                .where(Watchlist.user_id == rule.user_id)
                .where(Watchlist.is_active.is_(True))
            )
            items = rows.scalars().all()
            disabled = 0
            for item in items:
                if item.alert_price_above is not None or item.alert_price_below is not None:
                    disabled += 1
                item.alert_price_above = None
                item.alert_price_below = None
                existing = (item.notes or "").strip()
                mute_note = f"alerts muted until {mute_until.isoformat()} by rule"
                item.notes = f"{existing}\n{mute_note}".strip()

            await self.db.flush()
            return {
                "alerts_muted": disabled,
                "mute_hours": mute_hours,
                "muted_until": mute_until.isoformat(),
            }

        if action_module == "scheduler" and action_type == "activate_recovery_mode":
            await self.scheduler.reschedule(
                user_id=rule.user_id,
                plan_date=date.today(),
                request=RescheduleRequest(
                    reason=f"Recovery mode by rule: {rule.name}",
                    trigger="rule",
                    new_constraints={
                        "intensity": "reduced",
                        "insert_recovery_block": bool(
                            action_params.get("insert_recovery_block", True)
                        ),
                    },
                ),
            )
            return {"recovery_mode": True}

        if action_module == "scheduler" and action_type == "increase_study_blocks":
            extra_blocks = int(action_params.get("extra_blocks") or 2)
            await self.scheduler.reschedule(
                user_id=rule.user_id,
                plan_date=date.today(),
                request=RescheduleRequest(
                    reason=f"Study boost by rule: {rule.name}",
                    trigger="rule",
                    new_constraints={"add_study_blocks": extra_blocks},
                ),
            )
            return {"extra_study_blocks": extra_blocks}

        if action_module == "gamification" and action_type == "award_bonus_xp":
            bonus_xp = int(action_params.get("xp") or 40)
            event = await GamificationService(self.db).award_xp(
                user_id=rule.user_id,
                source_module="rules",
                action="bonus_xp_rule",
                metadata={"xp": bonus_xp},
            )
            return {
                "xp_awarded": bonus_xp,
                "event_id": str(event.id) if event else None,
            }

        return {
            "skipped": True,
            "reason": f"No action handler for {action_module}:{action_type}",
        }

    async def _build_context(self, user_id: uuid.UUID) -> dict:
        today = date.today()

        sleep_result = await self.db.execute(
            select(SleepRecord)
            .where(SleepRecord.user_id == user_id)
            .order_by(desc(SleepRecord.sleep_date), desc(SleepRecord.created_at))
            .limit(1)
        )
        latest_sleep = sleep_result.scalar_one_or_none()
        sleep_hours = (
            round(float(latest_sleep.sleep_duration_minutes) / 60.0, 2)
            if latest_sleep
            else 0.0
        )

        workouts_result = await self.db.execute(
            select(WorkoutLog.workout_date)
            .where(WorkoutLog.user_id == user_id)
            .where(WorkoutLog.workout_date >= today - timedelta(days=14))
        )
        workout_dates = set(workouts_result.scalars().all())
        missed_streak = 0
        for days_back in range(0, 14):
            day = today - timedelta(days=days_back)
            if day in workout_dates:
                break
            missed_streak += 1

        snap_result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == user_id)
            .order_by(desc(PortfolioSnapshot.snapshot_date), desc(PortfolioSnapshot.created_at))
            .limit(2)
        )
        snaps = snap_result.scalars().all()
        portfolio_drop_pct = 0.0
        if len(snaps) >= 2 and float(snaps[1].current_value or 0) > 0:
            latest_value = float(snaps[0].current_value or 0)
            prev_value = float(snaps[1].current_value or 0)
            portfolio_drop_pct = round(((latest_value - prev_value) / prev_value) * 100.0, 2)

        mood_result = await self.db.execute(
            select(JournalEntry.entry_date, JournalEntry.mood)
            .where(JournalEntry.user_id == user_id)
            .where(JournalEntry.entry_date >= today - timedelta(days=14))
            .where(JournalEntry.mood.is_not(None))
            .order_by(JournalEntry.entry_date.asc())
        )
        low_mood_streak_days = 0
        for _, mood in mood_result.all():
            score = _MOOD_SCORE.get(mood, 55.0)
            if score < 40:
                low_mood_streak_days += 1
            else:
                low_mood_streak_days = 0

        exam_result = await self.db.execute(
            select(func.count(MockTest.id))
            .where(MockTest.user_id == user_id)
            .where(MockTest.date >= today)
            .where(MockTest.date <= today + timedelta(days=7))
        )
        upcoming_exams_7d = int(exam_result.scalar() or 0)

        streak_result = await self.db.execute(
            select(func.max(Habit.current_streak)).where(Habit.user_id == user_id)
        )
        max_habit_streak = int(streak_result.scalar() or 0)

        return {
            "sleep_hours": sleep_hours,
            "missed_gym_streak_days": missed_streak,
            "portfolio_drop_pct": portfolio_drop_pct,
            "low_mood_streak_days": low_mood_streak_days,
            "upcoming_exams_7d": upcoming_exams_7d,
            "max_habit_streak": max_habit_streak,
        }

    async def _get_rule(self, user_id: uuid.UUID, rule_id: uuid.UUID) -> UserRule:
        result = await self.db.execute(
            select(UserRule)
            .where(UserRule.user_id == user_id)
            .where(UserRule.id == rule_id)
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("UserRule", str(rule_id))
        return row

    def _matches_condition(self, condition: dict, context: dict) -> bool:
        if not condition:
            return False

        if "all" in condition and isinstance(condition["all"], list):
            return all(self._matches_condition(item, context) for item in condition["all"])

        if "any" in condition and isinstance(condition["any"], list):
            return any(self._matches_condition(item, context) for item in condition["any"])

        field = str(condition.get("field") or "").strip()
        operator = str(condition.get("operator") or "==").strip()
        expected = condition.get("value")
        actual = self._resolve_context_value(context=context, field=field)

        if operator in {"<", "<=", ">", ">="}:
            return self._compare_ordered(actual=actual, expected=expected, operator=operator)
        if operator == "!=":
            return actual != expected
        if operator == "in":
            return actual in (expected or [])
        if operator == "not_in":
            return actual not in (expected or [])

        return actual == expected

    @staticmethod
    def _resolve_context_value(context: dict, field: str):
        if not field:
            return None
        value = context
        for key in field.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(key)
        return value

    @staticmethod
    def _compare_ordered(actual, expected, operator: str) -> bool:
        if actual is None or expected is None:
            return False
        try:
            if operator == "<":
                return bool(actual < expected)
            if operator == "<=":
                return bool(actual <= expected)
            if operator == ">":
                return bool(actual > expected)
            return bool(actual >= expected)
        except TypeError:
            return False

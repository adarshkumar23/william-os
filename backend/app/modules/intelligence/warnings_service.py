"""WILLIAM OS - Predictive warnings service."""

from __future__ import annotations

import contextlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import redis.asyncio as redis
import structlog
from sqlalchemy import desc, func, select

from app.core.config import get_settings
from app.modules.auth.models import User
from app.modules.decisions.models import Decision
from app.modules.habits.models import Habit, HabitCheckIn
from app.modules.intelligence.models import LifeScore, PredictiveWarning
from app.modules.intelligence.schemas import PredictiveWarningResponse
from app.modules.journal.models import JournalEntry, JournalMood
from app.modules.medicine.models import Medicine, MedicineLog
from app.modules.messaging.schemas import NotificationPayload
from app.modules.messaging.service import MessagingService
from app.modules.scheduler.models import BlockCategory, BlockStatus, DailyPlan, ScheduleBlock
from app.modules.scheduler.schemas import RescheduleRequest, ScheduleGenerateRequest
from app.modules.scheduler.service import SchedulerService
from app.modules.sleep.models import SleepDebt, SleepRecord
from app.modules.study.models import MockTest, StudySession, Subject
from app.modules.trading.models import PortfolioSnapshot, TradeLog

if TYPE_CHECKING:
    import uuid

logger = structlog.get_logger(__name__)

_MOOD_SCORE = {
    JournalMood.GREAT: 90.0,
    JournalMood.GOOD: 75.0,
    JournalMood.OKAY: 55.0,
    JournalMood.LOW: 35.0,
    JournalMood.BAD: 20.0,
}


class PredictiveWarningService:
    def __init__(self, db):
        self.db = db
        self.messaging = MessagingService(db)
        self.scheduler = SchedulerService(db)
        settings = get_settings()
        self._cache_ttl_seconds = max(60, int(settings.redis_cache_ttl))
        self._redis = redis.from_url(settings.redis_url, decode_responses=True)

    async def resolve_warning(
        self,
        user_id: uuid.UUID,
        warning_id: uuid.UUID,
    ) -> PredictiveWarningResponse:
        result = await self.db.execute(
            select(PredictiveWarning)
            .where(PredictiveWarning.id == warning_id)
            .where(PredictiveWarning.user_id == user_id)
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            from app.shared.types import NotFoundError

            raise NotFoundError("PredictiveWarning", str(warning_id))

        row.is_active = False
        row.resolved_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.flush()
        await self.db.refresh(row)
        return PredictiveWarningResponse.model_validate(row)

    async def get_burnout_score(
        self,
        user_id: uuid.UUID,
        force_refresh: bool = False,
    ) -> dict[str, object]:
        cache_key = f"intelligence:burnout-score:{user_id}"
        if not force_refresh:
            cached = await self._cache_get_json(cache_key)
            if isinstance(cached, dict):
                return cached

        score, signals = await self._calculate_burnout_score(user_id)
        severity = self._burnout_severity(score)
        if score < 30:
            recommendation = "Maintain current pace and keep sleep consistency high."
        elif score < 60:
            recommendation = "Reduce load by 20% and protect recovery windows."
        elif score < 80:
            recommendation = "Scale tomorrow down to essentials and prioritize sleep recovery."
        else:
            recommendation = "Immediate recovery mode: cut workload, rest, and replan tomorrow."

        payload = {
            "score": round(score, 2),
            "severity": severity,
            "signals": signals,
            "recommendation": recommendation,
        }
        await self._cache_set_json(cache_key, payload)
        return payload

    async def get_trends(
        self,
        user_id: uuid.UUID,
        force_refresh: bool = False,
    ) -> dict[str, object]:
        cache_key = f"intelligence:trends:{user_id}"
        if not force_refresh:
            cached = await self._cache_get_json(cache_key)
            if isinstance(cached, dict):
                return cached

        today = date.today()
        current_start = today - timedelta(days=6)
        previous_start = today - timedelta(days=13)
        previous_end = today - timedelta(days=7)

        sleep_current = await self._avg_sleep_quality(user_id, current_start, today)
        sleep_previous = await self._avg_sleep_quality(user_id, previous_start, previous_end)

        habits_current = await self._habit_completion_rate(user_id, current_start, today)
        habits_previous = await self._habit_completion_rate(user_id, previous_start, previous_end)

        study_minutes_current = await self._study_minutes(user_id, current_start, today)
        study_minutes_previous = await self._study_minutes(user_id, previous_start, previous_end)

        life_score_current = await self._avg_life_score(user_id, current_start, today)
        life_score_previous = await self._avg_life_score(user_id, previous_start, previous_end)

        mood_current = await self._avg_mood_score(user_id, current_start, today)
        mood_previous = await self._avg_mood_score(user_id, previous_start, previous_end)

        burnout_score, burnout_signals = await self._calculate_burnout_score(user_id)

        payload = {
            "window": {
                "current": {
                    "from": current_start.isoformat(),
                    "to": today.isoformat(),
                },
                "previous": {
                    "from": previous_start.isoformat(),
                    "to": previous_end.isoformat(),
                },
            },
            "trends": {
                "sleep_quality": self._trend_payload(sleep_current, sleep_previous),
                "habit_completion_rate": self._trend_payload(habits_current, habits_previous),
                "study_minutes": self._trend_payload(study_minutes_current, study_minutes_previous),
                "life_score": self._trend_payload(life_score_current, life_score_previous),
                "mood_score": self._trend_payload(mood_current, mood_previous),
            },
            "burnout": {
                "score": round(burnout_score, 2),
                "severity": self._burnout_severity(burnout_score),
                "signals": burnout_signals,
            },
            "generated_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        }

        await self._cache_set_json(cache_key, payload)
        return payload

    async def invalidate_cache(self, user_id: uuid.UUID) -> None:
        keys = [
            f"intelligence:burnout-score:{user_id}",
            f"intelligence:trends:{user_id}",
        ]
        try:
            await self._redis.delete(*keys)
        except Exception:
            return

    async def intervene_burnout(self, user_id: uuid.UUID) -> dict[str, object]:
        from app.modules.chat.proactive import ProactiveMessageService

        score, signals = await self._calculate_burnout_score(user_id)
        if score < 60:
            return {
                "status": "no_intervention_needed",
                "score": round(score, 2),
                "signals": signals,
            }

        tomorrow = date.today() + timedelta(days=1)
        plan_result = await self.db.execute(
            select(DailyPlan)
            .where(DailyPlan.user_id == user_id)
            .where(DailyPlan.plan_date == tomorrow)
            .order_by(DailyPlan.created_at.desc())
            .limit(1)
        )
        plan = plan_result.scalar_one_or_none()

        if plan is None:
            with contextlib.suppress(Exception):
                await self.scheduler.generate_daily_plan(
                    user_id=user_id,
                    request=ScheduleGenerateRequest(target_date=tomorrow),
                )
            plan_result = await self.db.execute(
                select(DailyPlan)
                .where(DailyPlan.user_id == user_id)
                .where(DailyPlan.plan_date == tomorrow)
                .order_by(DailyPlan.created_at.desc())
                .limit(1)
            )
            plan = plan_result.scalar_one_or_none()

        adjusted = 0
        kept = 0
        if plan is not None:
            blocks_result = await self.db.execute(
                select(ScheduleBlock)
                .where(ScheduleBlock.plan_id == plan.id)
                .order_by(ScheduleBlock.priority.asc(), ScheduleBlock.start_time.asc())
            )
            blocks = list(blocks_result.scalars().all())

            keep_ids: set[uuid.UUID] = set()
            for block in blocks:
                if block.is_fixed:
                    keep_ids.add(block.id)

            flexible = [b for b in blocks if not b.is_fixed]
            top_three = flexible[:3]
            for block in top_three:
                keep_ids.add(block.id)

            kept = len(keep_ids)
            for block in blocks:
                if block.id in keep_ids:
                    continue
                block.status = BlockStatus.RESCHEDULED
                adjusted += 1

            if adjusted > 0:
                journal_prompt_block = ScheduleBlock(
                    plan_id=plan.id,
                    title="Recovery Journal Prompt",
                    description=("How are you really feeling? William noticed signs of burnout."),
                    category=BlockCategory.PERSONAL,
                    start_time=__import__("datetime").time(hour=20, minute=30),
                    end_time=__import__("datetime").time(hour=20, minute=45),
                    duration_minutes=15,
                    status=BlockStatus.PENDING,
                    priority=1,
                    is_fixed=False,
                    is_ai_generated=False,
                    tags=["burnout", "journal", "recovery"],
                    linked_module="journal",
                )
                self.db.add(journal_prompt_block)

        proactive = ProactiveMessageService(self.db)
        message = "I've lightened tomorrow's schedule. You need rest."
        await proactive.send_proactive_message(
            user_id=user_id,
            message=message,
            trigger="burnout_intervention",
        )

        await self.db.flush()
        return {
            "status": "intervened",
            "score": round(score, 2),
            "signals": signals,
            "summary": "I have adjusted your next-day load and added a recovery journal prompt.",
            "schedule_adjusted_blocks": adjusted,
            "schedule_kept_blocks": kept,
        }

    async def get_active_warnings(self, user_id: uuid.UUID) -> list[PredictiveWarningResponse]:
        result = await self.db.execute(
            select(PredictiveWarning)
            .where(PredictiveWarning.user_id == user_id)
            .where(PredictiveWarning.is_active.is_(True))
            .order_by(desc(PredictiveWarning.detected_at), desc(PredictiveWarning.created_at))
        )
        return [PredictiveWarningResponse.model_validate(row) for row in result.scalars().all()]

    async def scan_user(self, user_id: uuid.UUID) -> list[PredictiveWarningResponse]:
        detected: dict[str, dict] = {}

        burnout = await self._detect_burnout_risk(user_id)
        if burnout:
            detected["burnout_risk"] = burnout

        sleep_collapse = await self._detect_sleep_collapse_risk(user_id)
        if sleep_collapse:
            detected["sleep_collapse_risk"] = sleep_collapse

        med_streak = await self._detect_missed_medication_streak(user_id)
        if med_streak:
            detected["missed_medication_streak"] = med_streak

        study_dropout = await self._detect_study_dropout_risk(user_id)
        if study_dropout:
            detected["study_dropout_risk"] = study_dropout

        mood_downturn = await self._detect_emotional_downturn(user_id)
        if mood_downturn:
            detected["emotional_downturn"] = mood_downturn

        overtrading = await self._detect_overtrading_risk(user_id)
        if overtrading:
            detected["overtrading_risk"] = overtrading

        collision = await self._detect_deadline_collision(user_id)
        if collision:
            detected["deadline_collision"] = collision

        active_result = await self.db.execute(
            select(PredictiveWarning)
            .where(PredictiveWarning.user_id == user_id)
            .where(PredictiveWarning.is_active.is_(True))
        )
        active_rows = {row.warning_type: row for row in active_result.scalars().all()}

        for warning_type, row in active_rows.items():
            if warning_type not in detected:
                row.is_active = False
                row.resolved_at = datetime.now(UTC)

        output: list[PredictiveWarningResponse] = []
        for warning_type, details in detected.items():
            row = await self.generate_warning(
                user_id=user_id,
                warning_type=warning_type,
                details=details,
            )
            output.append(row)
            await self.trigger_response(user_id=user_id, warning=row)

        return output

    async def generate_warning(
        self,
        user_id: uuid.UUID,
        warning_type: str,
        details: dict,
    ) -> PredictiveWarningResponse:
        explanation, severity, recommended_action = self._compose_warning_payload(
            warning_type, details
        )

        existing_result = await self.db.execute(
            select(PredictiveWarning)
            .where(PredictiveWarning.user_id == user_id)
            .where(PredictiveWarning.warning_type == warning_type)
            .where(PredictiveWarning.is_active.is_(True))
            .limit(1)
        )
        row = existing_result.scalar_one_or_none()
        if row is None:
            row = PredictiveWarning(
                user_id=user_id,
                warning_type=warning_type,
                severity=severity,
                explanation=explanation,
                recommended_action=recommended_action,
                details=details,
                is_active=True,
                detected_at=datetime.now(UTC),
                resolved_at=None,
            )
            self.db.add(row)
        else:
            row.severity = severity
            row.explanation = explanation
            row.recommended_action = recommended_action
            row.details = details
            row.detected_at = datetime.now(UTC)
            row.is_active = True
            row.resolved_at = None

        await self.db.flush()
        await self.db.refresh(row)
        return PredictiveWarningResponse.model_validate(row)

    async def trigger_response(
        self, user_id: uuid.UUID, warning: PredictiveWarningResponse
    ) -> dict:
        actions: list[str] = []

        payload = NotificationPayload(
            title=f"Predictive warning: {warning.warning_type}",
            body=f"[{warning.severity.upper()}] {warning.explanation}",
            notification_type="predictive_warning",
            data=warning.model_dump(mode="json"),
        )

        in_app = await self.messaging.send_in_app_notification(user_id=user_id, payload=payload)
        actions.append(f"in_app:{in_app.id}")

        if warning.severity in {"high", "critical"}:
            telegram = await self.messaging.send_notification(user_id=user_id, payload=payload)
            actions.append(f"telegram_delivered:{telegram.delivered}")

            try:
                await self.scheduler.reschedule(
                    user_id=user_id,
                    plan_date=date.today(),
                    request=RescheduleRequest(
                        reason=f"Predictive warning response: {warning.warning_type}",
                        trigger="predictive_warning",
                        new_constraints={"intensity": "reduced", "insert_recovery_block": True},
                    ),
                )
                actions.append("schedule_reduced")
            except Exception as exc:
                logger.warning(
                    "warning_schedule_adjustment_failed",
                    user_id=str(user_id),
                    warning_type=warning.warning_type,
                    error=str(exc),
                )

        return {"actions": actions}

    async def _detect_burnout_risk(self, user_id: uuid.UUID) -> dict | None:
        score, signals = await self._calculate_burnout_score(user_id)
        if score < 30:
            return None

        severity = self._burnout_severity(score)
        return {
            "warning_type": "burnout_risk",
            "severity": severity,
            "explanation": (
                f"Burnout risk score: {score:.0f}/100. {self._burnout_explanation(signals)}"
            ),
            "recommended_action": ("Schedule a recovery day. Reduce tomorrow's workload by 50%."),
            "details": {"score": round(score, 2), "signals": signals},
        }

    async def _calculate_burnout_score(
        self,
        user_id: uuid.UUID,
    ) -> tuple[float, dict[str, object]]:
        score = 0.0
        signals: dict[str, object] = {}

        # Signal 1: Sleep debt (0-25)
        sleep_rows_result = await self.db.execute(
            select(SleepRecord.sleep_duration_minutes)
            .where(SleepRecord.user_id == user_id)
            .where(SleepRecord.sleep_date >= date.today() - timedelta(days=7))
            .order_by(SleepRecord.sleep_date.asc())
        )
        sleep_minutes = [float(value or 0.0) for value in sleep_rows_result.scalars().all()]
        user = await self.db.get(User, user_id)
        sleep_goal_hours = float(user.sleep_goal) if user and user.sleep_goal else 7.5
        sleep_debt_hours = 0.0
        for minutes in sleep_minutes:
            duration_hours = minutes / 60.0
            sleep_debt_hours += max(0.0, sleep_goal_hours - duration_hours)

        sleep_points = 0.0
        if sleep_debt_hours > 5.0:
            sleep_points = 25.0
        elif sleep_debt_hours >= 3.0:
            sleep_points = 15.0
        elif sleep_debt_hours >= 1.0:
            sleep_points = 5.0
        score += sleep_points
        signals["sleep_debt_hours"] = round(sleep_debt_hours, 2)
        signals["sleep_points"] = sleep_points

        # Signal 2: Habit completion decline (0-20)
        habits_count_result = await self.db.execute(
            select(func.count(Habit.id))
            .where(Habit.user_id == user_id)
            .where(Habit.is_active.is_(True))
        )
        active_habits = int(habits_count_result.scalar() or 0)
        current_start = date.today() - timedelta(days=6)
        previous_start = date.today() - timedelta(days=13)
        previous_end = date.today() - timedelta(days=7)

        current_checkins_result = await self.db.execute(
            select(func.count(HabitCheckIn.id))
            .join(Habit, Habit.id == HabitCheckIn.habit_id)
            .where(Habit.user_id == user_id)
            .where(HabitCheckIn.check_date >= current_start)
            .where(HabitCheckIn.check_date <= date.today())
            .where(HabitCheckIn.completed.is_(True))
            .where(HabitCheckIn.skipped.is_(False))
        )
        previous_checkins_result = await self.db.execute(
            select(func.count(HabitCheckIn.id))
            .join(Habit, Habit.id == HabitCheckIn.habit_id)
            .where(Habit.user_id == user_id)
            .where(HabitCheckIn.check_date >= previous_start)
            .where(HabitCheckIn.check_date <= previous_end)
            .where(HabitCheckIn.completed.is_(True))
            .where(HabitCheckIn.skipped.is_(False))
        )

        denom = max(1, active_habits * 7)
        current_rate = (int(current_checkins_result.scalar() or 0) / denom) * 100.0
        previous_rate = (int(previous_checkins_result.scalar() or 0) / denom) * 100.0
        decline = max(0.0, previous_rate - current_rate)
        habit_points = 0.0
        if decline > 30.0:
            habit_points = 20.0
        elif decline >= 15.0:
            habit_points = 10.0
        score += habit_points
        signals["habit_decline_pct"] = round(decline, 2)
        signals["habit_points"] = habit_points

        # Signal 3: Mood trend (0-20)
        mood_rows_result = await self.db.execute(
            select(JournalEntry.mood)
            .where(JournalEntry.user_id == user_id)
            .where(JournalEntry.mood.is_not(None))
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
            .limit(5)
        )
        mood_rows = [item for item in mood_rows_result.scalars().all() if item is not None]
        low_count = sum(1 for mood in mood_rows if mood in {JournalMood.LOW, JournalMood.BAD})
        mood_points = 0.0
        if len(mood_rows) >= 5 and low_count == len(mood_rows):
            mood_points = 20.0
        elif low_count >= 3:
            mood_points = 10.0
        score += mood_points
        signals["low_mood_count_last5"] = low_count
        signals["mood_points"] = mood_points

        # Signal 4: Life score decline (0-20)
        life_rows_result = await self.db.execute(
            select(LifeScore.computed_at, LifeScore.score)
            .where(LifeScore.user_id == user_id)
            .where(LifeScore.computed_at >= datetime.now(UTC) - timedelta(days=14))
            .order_by(LifeScore.computed_at.asc())
        )
        current_scores: list[float] = []
        previous_scores: list[float] = []
        for computed_at, life_value in life_rows_result.all():
            if computed_at.date() >= current_start:
                current_scores.append(float(life_value))
            elif previous_start <= computed_at.date() <= previous_end:
                previous_scores.append(float(life_value))
        current_avg = sum(current_scores) / len(current_scores) if current_scores else 0.0
        previous_avg = sum(previous_scores) / len(previous_scores) if previous_scores else 0.0
        score_drop = max(0.0, previous_avg - current_avg)
        life_points = 0.0
        if score_drop > 15.0:
            life_points = 20.0
        elif score_drop >= 5.0:
            life_points = 10.0
        score += life_points
        signals["life_score_drop"] = round(score_drop, 2)
        signals["life_score_points"] = life_points

        # Signal 5: Overwork signals (0-15)
        study_rows_result = await self.db.execute(
            select(StudySession.session_date, func.sum(StudySession.duration_minutes))
            .where(StudySession.user_id == user_id)
            .where(StudySession.session_date >= current_start)
            .group_by(StudySession.session_date)
        )
        heavy_study_days = sum(
            1 for _, total_minutes in study_rows_result.all() if float(total_minutes or 0) > 300.0
        )

        schedule_rows_result = await self.db.execute(
            select(DailyPlan.plan_date, func.sum(ScheduleBlock.duration_minutes))
            .join(ScheduleBlock, ScheduleBlock.plan_id == DailyPlan.id)
            .where(DailyPlan.user_id == user_id)
            .where(DailyPlan.plan_date >= current_start)
            .group_by(DailyPlan.plan_date)
        )
        long_schedule_days = sum(
            1
            for _, total_minutes in schedule_rows_result.all()
            if float(total_minutes or 0) > 720.0
        )
        overwork_points = 0.0
        if heavy_study_days >= 3:
            overwork_points += 10.0
        if long_schedule_days >= 1:
            overwork_points += 5.0
        score += overwork_points
        signals["heavy_study_days"] = heavy_study_days
        signals["long_schedule_days"] = long_schedule_days
        signals["overwork_points"] = overwork_points

        return min(100.0, score), signals

    async def _detect_sleep_collapse_risk(self, user_id: uuid.UUID) -> dict | None:
        debt_result = await self.db.execute(
            select(SleepDebt)
            .where(SleepDebt.user_id == user_id)
            .order_by(desc(SleepDebt.calculated_date))
            .limit(1)
        )
        debt = debt_result.scalar_one_or_none()

        quality_result = await self.db.execute(
            select(SleepRecord.sleep_quality)
            .where(SleepRecord.user_id == user_id)
            .where(SleepRecord.sleep_date >= date.today() - timedelta(days=7))
            .order_by(SleepRecord.sleep_date.asc())
        )
        quality_points = [float(item) for item in quality_result.scalars().all()]
        if len(quality_points) < 3:
            return None

        trend_down = quality_points[-1] < quality_points[0]
        debt_hours = float(debt.debt_hours) if debt else 0.0

        if debt_hours > 4.0 and trend_down:
            return {
                "sleep_debt_hours": debt_hours,
                "quality_start": quality_points[0],
                "quality_latest": quality_points[-1],
            }
        return None

    async def _detect_missed_medication_streak(self, user_id: uuid.UUID) -> dict | None:
        result = await self.db.execute(
            select(func.count(MedicineLog.id))
            .join(Medicine, Medicine.id == MedicineLog.medicine_id)
            .where(Medicine.user_id == user_id)
            .where(MedicineLog.log_date >= date.today() - timedelta(days=7))
            .where(MedicineLog.skipped.is_(True))
        )
        skipped = int(result.scalar() or 0)
        if skipped >= 3:
            return {"missed_doses_7d": skipped}
        return None

    async def _detect_study_dropout_risk(self, user_id: uuid.UUID) -> dict | None:
        subjects_result = await self.db.execute(
            select(func.count(Subject.id)).where(Subject.user_id == user_id)
        )
        subjects_count = int(subjects_result.scalar() or 0)
        if subjects_count == 0:
            return None

        recent_sessions_result = await self.db.execute(
            select(func.count(StudySession.id))
            .where(StudySession.user_id == user_id)
            .where(StudySession.session_date >= date.today() - timedelta(days=5))
        )
        sessions = int(recent_sessions_result.scalar() or 0)
        if sessions == 0:
            return {"active_subjects": subjects_count, "study_sessions_5d": sessions}
        return None

    async def _detect_emotional_downturn(self, user_id: uuid.UUID) -> dict | None:
        result = await self.db.execute(
            select(JournalEntry.entry_date, JournalEntry.mood)
            .where(JournalEntry.user_id == user_id)
            .where(JournalEntry.entry_date >= date.today() - timedelta(days=7))
            .where(JournalEntry.mood.is_not(None))
            .order_by(JournalEntry.entry_date.asc())
        )
        rows = result.all()
        streak = 0
        for _, mood in rows:
            score = _MOOD_SCORE.get(mood, 55.0)
            if score < 40.0:
                streak += 1
            else:
                streak = 0
        if streak >= 3:
            return {"low_mood_streak_days": streak}
        return None

    async def _detect_overtrading_risk(self, user_id: uuid.UUID) -> dict | None:
        trades_result = await self.db.execute(
            select(func.count(TradeLog.id))
            .where(TradeLog.user_id == user_id)
            .where(TradeLog.trade_date >= date.today() - timedelta(days=1))
        )
        trades_24h = int(trades_result.scalar() or 0)

        snapshot_result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == user_id)
            .order_by(desc(PortfolioSnapshot.snapshot_date))
            .limit(1)
        )
        latest = snapshot_result.scalar_one_or_none()
        down = bool(latest and latest.total_pnl < 0)

        if trades_24h > 5 and down:
            return {
                "trades_24h": trades_24h,
                "portfolio_total_pnl": float(latest.total_pnl) if latest else 0.0,
            }
        return None

    async def _detect_deadline_collision(self, user_id: uuid.UUID) -> dict | None:
        horizon = date.today() + timedelta(days=2)
        decision_result = await self.db.execute(
            select(func.count(Decision.id))
            .where(Decision.user_id == user_id)
            .where(Decision.deadline.is_not(None))
            .where(Decision.deadline <= horizon)
            .where(Decision.status != "reviewed")
        )
        decisions_due = int(decision_result.scalar() or 0)

        mock_result = await self.db.execute(
            select(func.count(MockTest.id))
            .where(MockTest.user_id == user_id)
            .where(MockTest.date <= horizon)
            .where(MockTest.date >= date.today())
        )
        mocks_due = int(mock_result.scalar() or 0)

        major_due = decisions_due + mocks_due
        if major_due >= 2:
            return {
                "major_items_due_48h": major_due,
                "decision_deadlines": decisions_due,
                "mock_tests": mocks_due,
            }
        return None

    @staticmethod
    def _compose_warning_payload(warning_type: str, details: dict) -> tuple[str, str, str]:
        if warning_type == "burnout_risk":
            if "severity" in details:
                return (
                    str(details.get("explanation", "Burnout risk detected.")),
                    str(details.get("severity", "high")),
                    str(
                        details.get(
                            "recommended_action",
                            "Schedule a recovery day and reduce workload.",
                        )
                    ),
                )
            return (
                "Multi-signal burnout pattern detected for the last 3+ days (low sleep, low energy, and habit decline).",
                "high",
                "reduce schedule intensity and activate recovery routine",
            )
        if warning_type == "sleep_collapse_risk":
            return (
                "Sleep debt exceeds 4 hours while sleep quality trend is declining.",
                "critical",
                "prioritize sleep recovery and lighten tomorrow's schedule",
            )
        if warning_type == "missed_medication_streak":
            return (
                "Three or more missed medication logs were detected in the last 7 days.",
                "high",
                "send medication escalation alert and reinforce reminders",
            )
        if warning_type == "study_dropout_risk":
            return (
                "No study sessions were recorded in 5+ days despite active study subjects.",
                "medium",
                "insert short focused study blocks immediately",
            )
        if warning_type == "emotional_downturn":
            return (
                "Journal mood indicates a sustained emotional downturn over consecutive days.",
                "high",
                "reduce cognitive load and activate emotional recovery routine",
            )
        if warning_type == "overtrading_risk":
            return (
                "Trade frequency is elevated while portfolio trend is negative.",
                "high",
                "enforce trading cooldown and reduce discretionary trades",
            )
        if warning_type == "deadline_collision":
            return (
                "Two or more major deadlines are clustered within 48 hours.",
                "medium",
                "rebalance schedule and protect deep work blocks",
            )

        return (
            f"Predictive risk detected: {warning_type}",
            "medium",
            "review and rebalance workload",
        )

    @staticmethod
    def _burnout_severity(score: float) -> str:
        if score >= 75:
            return "critical"
        if score >= 50:
            return "high"
        if score >= 30:
            return "low"
        return "low"

    @staticmethod
    def _burnout_explanation(signals: dict[str, object]) -> str:
        segments: list[str] = []
        if float(signals.get("sleep_points", 0.0)) > 0:
            segments.append(f"Sleep debt is {float(signals.get('sleep_debt_hours', 0.0)):.1f}h")
        if float(signals.get("habit_points", 0.0)) > 0:
            segments.append(
                f"habit completion dropped {float(signals.get('habit_decline_pct', 0.0)):.0f}%"
            )
        if float(signals.get("mood_points", 0.0)) > 0:
            segments.append(
                f"{int(signals.get('low_mood_count_last5', 0))}/5 recent moods were low"
            )
        if float(signals.get("life_score_points", 0.0)) > 0:
            segments.append(
                f"life score declined {float(signals.get('life_score_drop', 0.0)):.1f} points"
            )
        if float(signals.get("overwork_points", 0.0)) > 0:
            segments.append("overwork signals were detected")

        if not segments:
            return "Multiple burnout indicators were observed."
        return "; ".join(segments) + "."

    async def _avg_sleep_quality(self, user_id: uuid.UUID, start: date, end: date) -> float:
        result = await self.db.execute(
            select(func.avg(SleepRecord.sleep_quality))
            .where(SleepRecord.user_id == user_id)
            .where(SleepRecord.sleep_date >= start)
            .where(SleepRecord.sleep_date <= end)
        )
        value = result.scalar()
        return round(float(value or 0.0), 2)

    async def _habit_completion_rate(self, user_id: uuid.UUID, start: date, end: date) -> float:
        habits_result = await self.db.execute(
            select(func.count(Habit.id))
            .where(Habit.user_id == user_id)
            .where(Habit.is_active.is_(True))
        )
        habits_count = int(habits_result.scalar() or 0)
        if habits_count == 0:
            return 0.0

        completed_result = await self.db.execute(
            select(func.count(HabitCheckIn.id))
            .join(Habit, Habit.id == HabitCheckIn.habit_id)
            .where(Habit.user_id == user_id)
            .where(HabitCheckIn.check_date >= start)
            .where(HabitCheckIn.check_date <= end)
            .where(HabitCheckIn.completed.is_(True))
            .where(HabitCheckIn.skipped.is_(False))
        )
        completed = int(completed_result.scalar() or 0)
        days = (end - start).days + 1
        denom = max(1, habits_count * days)
        return round((completed / denom) * 100.0, 2)

    async def _study_minutes(self, user_id: uuid.UUID, start: date, end: date) -> float:
        result = await self.db.execute(
            select(func.sum(StudySession.duration_minutes))
            .where(StudySession.user_id == user_id)
            .where(StudySession.session_date >= start)
            .where(StudySession.session_date <= end)
        )
        return round(float(result.scalar() or 0.0), 2)

    async def _avg_life_score(self, user_id: uuid.UUID, start: date, end: date) -> float:
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end, datetime.max.time())
        result = await self.db.execute(
            select(func.avg(LifeScore.score))
            .where(LifeScore.user_id == user_id)
            .where(LifeScore.computed_at >= start_dt)
            .where(LifeScore.computed_at <= end_dt)
        )
        return round(float(result.scalar() or 0.0), 2)

    async def _avg_mood_score(self, user_id: uuid.UUID, start: date, end: date) -> float:
        result = await self.db.execute(
            select(JournalEntry.mood)
            .where(JournalEntry.user_id == user_id)
            .where(JournalEntry.entry_date >= start)
            .where(JournalEntry.entry_date <= end)
            .where(JournalEntry.mood.is_not(None))
        )
        moods = [m for m in result.scalars().all() if m is not None]
        if not moods:
            return 0.0
        total = sum(_MOOD_SCORE.get(mood, 55.0) for mood in moods)
        return round(total / len(moods), 2)

    @staticmethod
    def _trend_payload(current: float, previous: float) -> dict[str, object]:
        delta = round(current - previous, 2)
        if delta > 0:
            direction = "up"
        elif delta < 0:
            direction = "down"
        else:
            direction = "flat"

        pct_change = 0.0
        if previous != 0:
            pct_change = round((delta / previous) * 100.0, 2)

        return {
            "current": round(current, 2),
            "previous": round(previous, 2),
            "delta": delta,
            "pct_change": pct_change,
            "direction": direction,
        }

    async def _cache_get_json(self, key: str) -> dict | None:
        try:
            raw = await self._redis.get(key)
            if not raw:
                return None
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    async def _cache_set_json(self, key: str, payload: dict) -> None:
        try:
            await self._redis.setex(key, self._cache_ttl_seconds, json.dumps(payload, default=str))
        except Exception:
            return

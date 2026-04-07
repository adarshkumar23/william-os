"""
WILLIAM OS — Morning Briefing Service
Unified cross-module morning context assembly and delivery.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from time import perf_counter
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import httpx
import structlog
from app.core.config import get_settings
from app.core.metrics import observe_ai_call
from app.modules.briefing.schemas import (
    BriefingDeadlineItem,
    BriefingEnergyPrediction,
    BriefingHabitItem,
    BriefingLifeScore,
    BriefingMedicineMissItem,
    BriefingScheduleItem,
    MorningBriefingResponse,
    MorningBriefingSendResult,
)
from app.modules.decisions.models import Decision
from app.modules.fitness.service import FitnessService
from app.modules.habits.models import HabitFrequency
from app.modules.habits.service import HabitsService
from app.modules.intelligence.service import LifeScoreService
from app.modules.medicine.models import Medicine, MedicineLog
from app.modules.messaging.models import NotificationLog
from app.modules.messaging.schemas import NotificationPayload
from app.modules.messaging.service import MessagingService
from app.modules.scheduler.service import SchedulerService
from app.modules.sleep.service import SleepService
from app.modules.study.models import MockTest, RevisionCard, Subject
from app.modules.trading.service import TradingService
from sqlalchemy import select

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class MorningBriefingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def assemble_briefing(self, user_id: UUID) -> MorningBriefingResponse:
        sleep_quality = await self._collect_sleep_quality(user_id)
        today_schedule = await self._collect_today_schedule(user_id)
        priority_habits = await self._collect_priority_habits(user_id)
        missed_medicines = await self._collect_missed_medicines(user_id)
        upcoming_deadlines = await self._collect_upcoming_deadlines(user_id)
        market_watchlist_movement = await self._collect_market_movement(user_id)
        energy_prediction = await self._collect_energy_prediction(user_id)
        life_score = await self._collect_life_score(user_id)

        recommendation = await self._generate_recommendation(
            {
                "sleep_quality": sleep_quality,
                "today_schedule": [item.model_dump() for item in today_schedule],
                "priority_habits": [item.model_dump() for item in priority_habits],
                "missed_medicines": [item.model_dump(mode="json") for item in missed_medicines],
                "upcoming_deadlines": [item.model_dump(mode="json") for item in upcoming_deadlines],
                "market_watchlist_movement": market_watchlist_movement,
                "energy_prediction": energy_prediction.model_dump() if energy_prediction else None,
                "life_score": life_score.model_dump(mode="json"),
            }
        )

        return MorningBriefingResponse(
            generated_at=datetime.now(UTC),
            sleep_quality=sleep_quality,
            today_schedule=today_schedule,
            priority_habits=priority_habits,
            missed_medicines=missed_medicines,
            upcoming_deadlines=upcoming_deadlines,
            market_watchlist_movement=market_watchlist_movement,
            energy_prediction=energy_prediction,
            life_score=life_score,
            ai_recommendation_of_day=recommendation,
        )

    async def send_briefing(self, user_id: UUID) -> MorningBriefingSendResult:
        briefing = await self.assemble_briefing(user_id=user_id)
        message = self._format_message(briefing)

        payload = NotificationPayload(
            title="Morning OS Briefing",
            body=message,
            notification_type="morning_briefing",
            data=briefing.model_dump(mode="json"),
        )

        messaging = MessagingService(self.db)
        telegram_log = await messaging.send_notification(user_id=user_id, payload=payload)
        in_app_log = await messaging.send_in_app_notification(user_id=user_id, payload=payload)

        return MorningBriefingSendResult(
            briefing=briefing,
            telegram=telegram_log,
            in_app=in_app_log,
        )

    async def was_briefing_sent_today(
        self,
        user_id: UUID,
        timezone_name: str,
        now_utc: datetime | None = None,
    ) -> bool:
        now = now_utc or datetime.now(UTC)
        tz = self._resolve_timezone(timezone_name)
        local_now = now.astimezone(tz)
        local_day_start = datetime.combine(local_now.date(), time.min, tzinfo=tz)
        local_next_day = local_day_start + timedelta(days=1)

        start_utc = local_day_start.astimezone(UTC)
        end_utc = local_next_day.astimezone(UTC)

        result = await self.db.execute(
            select(NotificationLog.id)
            .where(NotificationLog.user_id == user_id)
            .where(NotificationLog.notification_type == "morning_briefing")
            .where(NotificationLog.sent_at >= start_utc)
            .where(NotificationLog.sent_at < end_utc)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _collect_sleep_quality(self, user_id: UUID) -> dict:
        service = SleepService(self.db)
        try:
            stats = await service.get_sleep_stats(user_id=user_id)
            return {
                "avg_quality_30d": stats.avg_quality_30d,
                "avg_duration_minutes": stats.avg_duration,
                "consistency_score": stats.consistency_score,
            }
        except Exception as exc:
            logger.warning("briefing_sleep_quality_failed", user_id=str(user_id), error=str(exc))
            return {
                "avg_quality_30d": 0.0,
                "avg_duration_minutes": 0.0,
                "consistency_score": 0.0,
            }

    async def _collect_today_schedule(self, user_id: UUID) -> list[BriefingScheduleItem]:
        service = SchedulerService(self.db)
        try:
            plan = await service.get_today(user_id=user_id)
            ordered = sorted(plan.blocks, key=lambda item: (str(item.start_time), item.priority))
            return [
                BriefingScheduleItem(
                    id=str(block.id),
                    title=block.title,
                    category=self._enum_or_value(block.category),
                    start_time=str(block.start_time),
                    end_time=str(block.end_time),
                    priority=int(block.priority),
                    status=self._enum_or_value(block.status),
                )
                for block in ordered[:5]
            ]
        except Exception as exc:
            logger.warning("briefing_schedule_failed", user_id=str(user_id), error=str(exc))
            return []

    async def _collect_priority_habits(self, user_id: UUID) -> list[BriefingHabitItem]:
        service = HabitsService(self.db)
        today = date.today()
        habits = await service.list_habits(user_id=user_id, active_only=True, limit=200, offset=0)
        check_ins = await service.get_daily_check_ins(user_id=user_id, target_date=today)
        check_in_by_habit = {item.habit_id: item for item in check_ins}

        due: list[BriefingHabitItem] = []
        for habit in habits:
            if not self._is_habit_due_today(habit.frequency, habit.days_of_week, today):
                continue
            check_in = check_in_by_habit.get(habit.id)
            completed = bool(check_in and check_in.completed and not check_in.skipped)
            if completed:
                continue
            due.append(
                BriefingHabitItem(
                    id=str(habit.id),
                    name=habit.name,
                    preferred_time=str(habit.preferred_time) if habit.preferred_time else None,
                    current_streak=habit.current_streak,
                )
            )

        return sorted(
            due,
            key=lambda item: (item.preferred_time is None, item.preferred_time or "99:99"),
        )

    async def _collect_missed_medicines(self, user_id: UUID) -> list[BriefingMedicineMissItem]:
        cutoff = date.today() - timedelta(days=1)
        result = await self.db.execute(
            select(MedicineLog, Medicine)
            .join(Medicine, Medicine.id == MedicineLog.medicine_id)
            .where(Medicine.user_id == user_id)
            .where(MedicineLog.log_date >= cutoff)
            .where(MedicineLog.skipped.is_(True))
            .order_by(MedicineLog.log_date.desc(), MedicineLog.scheduled_time.desc())
        )
        rows = result.all()

        missed = [
            BriefingMedicineMissItem(
                medicine_name=medicine.name,
                log_date=log.log_date,
                scheduled_time=str(log.scheduled_time),
                skip_reason=log.skip_reason,
            )
            for log, medicine in rows
        ]
        return missed[:10]

    async def _collect_upcoming_deadlines(self, user_id: UUID) -> list[BriefingDeadlineItem]:
        today = date.today()
        horizon = today + timedelta(days=7)

        card_result = await self.db.execute(
            select(RevisionCard, Subject)
            .join(Subject, Subject.id == RevisionCard.subject_id)
            .where(RevisionCard.user_id == user_id)
            .where(RevisionCard.next_review_date >= today)
            .where(RevisionCard.next_review_date <= horizon)
            .order_by(RevisionCard.next_review_date.asc())
        )

        mock_result = await self.db.execute(
            select(MockTest)
            .where(MockTest.user_id == user_id)
            .where(MockTest.date >= today)
            .where(MockTest.date <= horizon)
            .order_by(MockTest.date.asc())
        )

        decision_result = await self.db.execute(
            select(Decision)
            .where(Decision.user_id == user_id)
            .where(Decision.deadline.is_not(None))
            .where(Decision.deadline >= today)
            .where(Decision.deadline <= horizon)
            .where(Decision.status != "reviewed")
            .order_by(Decision.deadline.asc())
        )

        items: list[BriefingDeadlineItem] = []

        for card, subject in card_result.all():
            items.append(
                BriefingDeadlineItem(
                    source="study",
                    title=f"Revision card: {subject.name}",
                    due_date=card.next_review_date,
                    detail=card.question[:80],
                )
            )

        for mock in mock_result.scalars().all():
            items.append(
                BriefingDeadlineItem(
                    source="study",
                    title=f"Mock test: {mock.test_name}",
                    due_date=mock.date,
                    detail=None,
                )
            )

        for decision in decision_result.scalars().all():
            if decision.deadline is None:
                continue
            items.append(
                BriefingDeadlineItem(
                    source="decisions",
                    title=decision.title,
                    due_date=decision.deadline,
                    detail=decision.status,
                )
            )

        items.sort(key=lambda item: item.due_date)
        return items[:10]

    async def _collect_market_movement(self, user_id: UUID) -> dict:
        service = TradingService(self.db)
        watchlist = await service.list_watchlist(user_id=user_id)
        trades = await service.list_trades(user_id=user_id, limit=500, offset=0)
        holdings, _, _ = service._build_holdings(trades)
        top_gainers, top_losers = service._top_movers(holdings)

        return {
            "watchlist_count": len(watchlist),
            "top_gainers": top_gainers,
            "top_losers": top_losers,
        }

    async def _collect_energy_prediction(
        self,
        user_id: UUID,
    ) -> BriefingEnergyPrediction | None:
        service = FitnessService(self.db)
        target = date.today()
        try:
            forecast = await service.get_energy_forecast(user_id=user_id, forecast_date=target)
            if forecast is None:
                forecast = await service.generate_energy_forecast(
                    user_id=user_id,
                    forecast_date=target,
                )

            return BriefingEnergyPrediction(
                peak_hours=list(forecast.peak_hours),
                low_hours=list(forecast.low_hours),
                suggestions=list((forecast.suggestions or [])[:4]),
                generated_by=forecast.generated_by,
            )
        except Exception as exc:
            logger.warning(
                "briefing_energy_prediction_failed",
                user_id=str(user_id),
                error=str(exc),
            )
            return None

    async def _collect_life_score(self, user_id: UUID) -> BriefingLifeScore:
        service = LifeScoreService(self.db)
        try:
            score = await service.get_latest_score(user_id=user_id)
            return BriefingLifeScore(
                score=score.score,
                component_scores=score.component_scores,
                explanation=score.explanation,
                computed_at=score.computed_at,
            )
        except Exception as exc:
            logger.warning("briefing_life_score_failed", user_id=str(user_id), error=str(exc))
            return BriefingLifeScore(
                score=50.0,
                component_scores={
                    "sleep": 50.0,
                    "habits": 50.0,
                    "fitness": 50.0,
                    "study": 50.0,
                    "stability": 50.0,
                },
                explanation=(
                    "Life score unavailable right now; "
                    "focus on one high-impact task early."
                ),
                computed_at=datetime.now(UTC),
            )

    async def _generate_recommendation(self, context: dict) -> str:
        api_key = self.settings.gemini_api_key.get_secret_value()
        if not api_key:
            return self._fallback_recommendation(context)

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Create a single practical recommendation-of-the-day "
                                "for this user. "
                                "Use max 2 sentences, direct and actionable.\n"
                                f"Context: {json.dumps(context, default=str)}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": 140,
            },
        }

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                raw = response.json()
            observe_ai_call(provider="gemini", duration_seconds=perf_counter() - started)
            text = raw["candidates"][0]["content"]["parts"][0]["text"]
            cleaned = " ".join(str(text).strip().split())
            return cleaned or self._fallback_recommendation(context)
        except Exception as exc:
            observe_ai_call(provider="gemini", duration_seconds=perf_counter() - started)
            logger.warning("briefing_recommendation_failed", error=str(exc))
            return self._fallback_recommendation(context)

    @staticmethod
    def _fallback_recommendation(context: dict) -> str:
        life_score = float(context.get("life_score", {}).get("score", 50.0))
        pending_habits = len(context.get("priority_habits") or [])
        if life_score < 60:
            return (
                "Prioritize recovery in the first 90 minutes today: hydration, "
                "short movement, and one deep-focus block. "
                "Keep commitments minimal until your energy stabilizes."
            )
        if pending_habits >= 3:
            return (
                "Clear the first two priority habits before noon to lock momentum for the day. "
                "Use your peak energy window for the hardest schedule block."
            )
        return (
            "Your baseline looks stable; start with the highest-priority block "
            "and protect your peak energy hours from context switching. "
            "End the day by reviewing deadlines and tomorrow's first task."
        )

    @staticmethod
    def _format_message(briefing: MorningBriefingResponse) -> str:
        first_blocks = (
            ", ".join(item.title for item in briefing.today_schedule[:3]) or "No schedule yet"
        )
        pending_habits = ", ".join(item.name for item in briefing.priority_habits[:3]) or "None"
        missed_meds = len(briefing.missed_medicines)

        return (
            f"{briefing.ai_recommendation_of_day}\n\n"
            f"Life Score: {briefing.life_score.score:.1f}/100\n"
            f"Top schedule: {first_blocks}\n"
            f"Pending habits: {pending_habits}\n"
            f"Missed medicines (24h): {missed_meds}"
        )

    @staticmethod
    def _resolve_timezone(name: str | None) -> ZoneInfo:
        try:
            return ZoneInfo(name or "UTC")
        except Exception:
            return ZoneInfo("UTC")

    @staticmethod
    def _is_habit_due_today(
        frequency: str | HabitFrequency,
        days_of_week: list[int],
        today: date,
    ) -> bool:
        weekday = today.weekday()
        try:
            freq = HabitFrequency(frequency)
        except Exception:
            freq = HabitFrequency.DAILY

        if freq == HabitFrequency.DAILY:
            return True
        if freq == HabitFrequency.WEEKDAYS:
            return weekday <= 4
        if freq == HabitFrequency.WEEKENDS:
            return weekday >= 5
        if freq == HabitFrequency.CUSTOM:
            return weekday in (days_of_week or [])
        return False

    @staticmethod
    def _enum_or_value(raw) -> str:
        return getattr(raw, "value", str(raw))

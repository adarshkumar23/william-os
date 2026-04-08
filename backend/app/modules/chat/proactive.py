"""WILLIAM OS - Proactive chat messaging service."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from time import perf_counter
from zoneinfo import ZoneInfo

import httpx
import structlog
from app.core.config import get_settings
from app.core.metrics import observe_ai_call
from app.modules.auth.models import User
from app.modules.chat.models import AgentName, ChatMessage, ChatSession, MessageRole
from app.modules.habits.models import Habit, ProcrastinationSignal
from app.modules.intelligence.models import LifeScore, ModuleSignal
from app.modules.messaging.schemas import NotificationPayload
from app.modules.messaging.service import MessagingService
from app.modules.scheduler.models import BlockStatus, DailyPlan, ScheduleBlock
from app.modules.sleep.models import SleepRecord
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class ProactiveMessageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.messaging = MessagingService(db)

    async def generate_morning_message(self, user_id: uuid.UUID) -> str:
        user = await self.db.get(User, user_id)
        name = str(user.display_name or user.full_name or user.username) if user else "User"

        sleep_result = await self.db.execute(
            select(SleepRecord.sleep_duration_minutes)
            .where(SleepRecord.user_id == user_id)
            .where(SleepRecord.sleep_date == (date.today()))
            .order_by(SleepRecord.created_at.desc())
            .limit(1)
        )
        sleep_minutes = float(sleep_result.scalar() or 0.0)
        sleep_hours = round(sleep_minutes / 60.0, 1) if sleep_minutes > 0 else 0.0

        plan_result = await self.db.execute(
            select(DailyPlan.id)
            .where(DailyPlan.user_id == user_id)
            .where(DailyPlan.plan_date == date.today())
            .order_by(DailyPlan.created_at.desc())
            .limit(1)
        )
        plan_id = plan_result.scalar_one_or_none()
        block_count = 0
        if plan_id is not None:
            block_count_result = await self.db.execute(
                select(func.count(ScheduleBlock.id)).where(ScheduleBlock.plan_id == plan_id)
            )
            block_count = int(block_count_result.scalar() or 0)

        streak_result = await self.db.execute(
            select(func.max(Habit.current_streak)).where(Habit.user_id == user_id)
        )
        streak = int(streak_result.scalar() or 0)

        score_result = await self.db.execute(
            select(LifeScore.score)
            .where(LifeScore.user_id == user_id)
            .order_by(LifeScore.computed_at.desc(), LifeScore.created_at.desc())
            .limit(1)
        )
        score = round(float(score_result.scalar() or 50.0), 1)

        prompt = (
            f"You are William Salvator. Generate a brief morning message for {name}.\n"
            f"Sleep: {sleep_hours}h. Schedule: {block_count} blocks. Streak: {streak} days.\n"
            f"Life score: {score}. Be direct, warm, specific. Max 2 sentences. "
            "No generic greetings."
        )
        fallback = (
            f"Sleep logged: {sleep_hours}h. You have {block_count} blocks today, "
            f"streak at {streak} days, life score {score:.0f}. Execute the first hard block early."
        )
        return await self._generate_with_gemini(prompt=prompt, fallback=fallback)

    async def generate_afternoon_check(self, user_id: uuid.UUID) -> str:
        plan_result = await self.db.execute(
            select(DailyPlan.id)
            .where(DailyPlan.user_id == user_id)
            .where(DailyPlan.plan_date == date.today())
            .order_by(DailyPlan.created_at.desc())
            .limit(1)
        )
        plan_id = plan_result.scalar_one_or_none()

        total_blocks = 0
        completed_blocks = 0
        if plan_id is not None:
            total_result = await self.db.execute(
                select(func.count(ScheduleBlock.id)).where(ScheduleBlock.plan_id == plan_id)
            )
            done_result = await self.db.execute(
                select(func.count(ScheduleBlock.id))
                .where(ScheduleBlock.plan_id == plan_id)
                .where(ScheduleBlock.status == BlockStatus.COMPLETED)
            )
            total_blocks = int(total_result.scalar() or 0)
            completed_blocks = int(done_result.scalar() or 0)

        completion_rate = (completed_blocks / total_blocks * 100.0) if total_blocks else 0.0

        procrastination_result = await self.db.execute(
            select(ProcrastinationSignal)
            .where(ProcrastinationSignal.user_id == user_id)
            .where(ProcrastinationSignal.signal_date == date.today())
            .order_by(ProcrastinationSignal.created_at.desc())
            .limit(1)
        )
        procrastination = procrastination_result.scalar_one_or_none()

        energy_result = await self.db.execute(
            select(ModuleSignal.value)
            .where(ModuleSignal.user_id == user_id)
            .where(ModuleSignal.source_module == "fitness")
            .where(ModuleSignal.signal_type == "energy")
            .order_by(ModuleSignal.recorded_at.desc(), ModuleSignal.created_at.desc())
            .limit(1)
        )
        energy = round(float(energy_result.scalar() or 50.0), 1)

        if procrastination is not None:
            base = "I've noticed you've been off-task. 5-min reset?"
        elif completion_rate < 50.0:
            base = f"You've completed {completion_rate:.0f}% of today's schedule. Want to reset?"
        else:
            base = f"You are at {completion_rate:.0f}% completion. Keep momentum for the final stretch."

        prompt = (
            "You are William Salvator. Rewrite this afternoon check to be concise and motivational. "
            f"Completion={completion_rate:.0f}%, energy={energy:.0f}/100, "
            f"procrastination_detected={procrastination is not None}. Base: {base}"
        )
        return await self._generate_with_gemini(prompt=prompt, fallback=base)

    async def generate_evening_summary(self, user_id: uuid.UUID) -> str:
        habits_total_result = await self.db.execute(
            select(func.count(Habit.id))
            .where(Habit.user_id == user_id)
            .where(Habit.is_active.is_(True))
        )
        total_habits = int(habits_total_result.scalar() or 0)

        completed_habits_result = await self.db.execute(
            select(func.count(ScheduleBlock.id))
            .join(DailyPlan, DailyPlan.id == ScheduleBlock.plan_id)
            .where(DailyPlan.user_id == user_id)
            .where(DailyPlan.plan_date == date.today())
            .where(ScheduleBlock.linked_module == "habits")
            .where(ScheduleBlock.status == BlockStatus.COMPLETED)
        )
        completed_habits = int(completed_habits_result.scalar() or 0)

        life_score_result = await self.db.execute(
            select(LifeScore.score)
            .where(LifeScore.user_id == user_id)
            .order_by(LifeScore.computed_at.desc(), LifeScore.created_at.desc())
            .limit(1)
        )
        score = round(float(life_score_result.scalar() or 50.0), 1)

        achievement_result = await self.db.execute(
            select(ScheduleBlock.title)
            .join(DailyPlan, DailyPlan.id == ScheduleBlock.plan_id)
            .where(DailyPlan.user_id == user_id)
            .where(DailyPlan.plan_date == date.today())
            .where(ScheduleBlock.status == BlockStatus.COMPLETED)
            .order_by(ScheduleBlock.priority.asc(), ScheduleBlock.end_time.desc())
            .limit(1)
        )
        best_achievement = str(achievement_result.scalar() or "You showed up and kept moving.")

        prompt = (
            "You are William Salvator. Create a 2-sentence evening summary. "
            f"Habits: {completed_habits}/{total_habits}. Life score: {score}. "
            f"Best achievement: {best_achievement}. Include one improvement suggestion for tomorrow."
        )
        fallback = (
            f"You hit {completed_habits}/{max(1, total_habits)} habits today. "
            f"Best achievement: {best_achievement}. Tomorrow, start with one high-impact block early."
        )
        return await self._generate_with_gemini(prompt=prompt, fallback=fallback)

    async def send_proactive_message(self, user_id: uuid.UUID, message: str, trigger: str):
        session = await self._get_or_create_os_session(user_id)
        proactive_message = ChatMessage(
            session_id=session.id,
            user_id=user_id,
            role=MessageRole.ASSISTANT,
            content=message,
            extra_metadata={"proactive": True, "trigger": trigger},
        )
        self.db.add(proactive_message)
        session.updated_at = datetime.now(UTC).replace(tzinfo=None)

        payload = NotificationPayload(
            title="William proactive check-in",
            body=message,
            notification_type=f"proactive_{trigger}",
            data={"trigger": trigger, "session_id": str(session.id)},
        )
        await self.messaging.send_in_app_notification(user_id=user_id, payload=payload)
        await self.messaging.send_notification(user_id=user_id, payload=payload)

        await self.db.flush()
        await self.db.refresh(proactive_message)
        return proactive_message

    async def should_send_morning(self, user_id: uuid.UUID) -> bool:
        now_utc = datetime.now(UTC)
        start = now_utc - timedelta(hours=8)

        result = await self.db.execute(
            select(func.count(ChatMessage.id))
            .where(ChatMessage.user_id == user_id)
            .where(ChatMessage.role == MessageRole.ASSISTANT)
            .where(ChatMessage.created_at >= start)
            .where(ChatMessage.extra_metadata.is_not(None))
        )
        recent_count = int(result.scalar() or 0)
        if recent_count == 0:
            return True

        rows = await self.db.execute(
            select(ChatMessage.extra_metadata)
            .where(ChatMessage.user_id == user_id)
            .where(ChatMessage.role == MessageRole.ASSISTANT)
            .where(ChatMessage.created_at >= start)
            .where(ChatMessage.extra_metadata.is_not(None))
            .order_by(ChatMessage.created_at.desc())
            .limit(20)
        )
        for metadata in rows.scalars().all():
            if isinstance(metadata, dict) and metadata.get("trigger") == "morning":
                return False
        return True

    async def should_send_afternoon(self, user_id: uuid.UUID) -> bool:
        user = await self.db.get(User, user_id)
        tz_name = str(user.timezone or "UTC") if user else "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")

        local_now = datetime.now(UTC).astimezone(tz)
        if local_now.hour < 14 or local_now.hour > 17:
            return False

        local_start = datetime.combine(local_now.date(), time(hour=14, minute=0), tzinfo=tz)
        local_end = datetime.combine(local_now.date(), time(hour=17, minute=59), tzinfo=tz)
        start_utc = local_start.astimezone(UTC).replace(tzinfo=None)
        end_utc = local_end.astimezone(UTC).replace(tzinfo=None)

        rows = await self.db.execute(
            select(ChatMessage.extra_metadata)
            .where(ChatMessage.user_id == user_id)
            .where(ChatMessage.role == MessageRole.ASSISTANT)
            .where(ChatMessage.created_at >= start_utc)
            .where(ChatMessage.created_at <= end_utc)
            .where(ChatMessage.extra_metadata.is_not(None))
        )
        for metadata in rows.scalars().all():
            if isinstance(metadata, dict) and metadata.get("trigger") == "afternoon":
                return False
        return True

    async def should_send_evening(self, user_id: uuid.UUID) -> bool:
        user = await self.db.get(User, user_id)
        tz_name = str(user.timezone or "UTC") if user else "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")

        local_now = datetime.now(UTC).astimezone(tz)
        local_start = datetime.combine(local_now.date(), time(hour=20, minute=0), tzinfo=tz)
        local_end = datetime.combine(local_now.date(), time(hour=23, minute=59), tzinfo=tz)
        start_utc = local_start.astimezone(UTC).replace(tzinfo=None)
        end_utc = local_end.astimezone(UTC).replace(tzinfo=None)

        rows = await self.db.execute(
            select(ChatMessage.extra_metadata)
            .where(ChatMessage.user_id == user_id)
            .where(ChatMessage.role == MessageRole.ASSISTANT)
            .where(ChatMessage.created_at >= start_utc)
            .where(ChatMessage.created_at <= end_utc)
            .where(ChatMessage.extra_metadata.is_not(None))
        )
        for metadata in rows.scalars().all():
            if isinstance(metadata, dict) and metadata.get("trigger") == "evening":
                return False
        return True

    async def _get_or_create_os_session(self, user_id: uuid.UUID) -> ChatSession:
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .where(ChatSession.agent_name == AgentName.OS)
            .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
            .limit(1)
        )
        session = result.scalar_one_or_none()
        if session is not None:
            return session

        session = ChatSession(
            user_id=user_id,
            agent_name=AgentName.OS,
            title="William OS",
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def _generate_with_gemini(self, prompt: str, fallback: str) -> str:
        api_key = self.settings.gemini_api_key.get_secret_value()
        if not api_key:
            return fallback

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": 180,
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
            return cleaned or fallback
        except Exception as exc:
            observe_ai_call(provider="gemini", duration_seconds=perf_counter() - started)
            logger.warning("proactive_message_generation_failed", error=str(exc))
            return fallback

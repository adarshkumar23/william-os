"""
William Salvator — Chat Service
Handles standard messaging, calling Gemini, parsing actions, and retrieving context.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from time import perf_counter
from uuid import UUID

import httpx
import structlog
from app.core.config import get_settings
from app.core.metrics import observe_ai_call
from app.modules.auth.service import AuthService
from app.modules.chat.calendar_actions import execute_calendar_action
from app.modules.chat.executor import ActionExecutor, ActionParser
from app.modules.chat.models import AgentName, ChatMessage, ChatSession, MessageRole
from app.modules.chat.prompts import get_agent_prompt
from app.modules.decisions.service import DecisionService
from app.modules.fitness.models import WorkoutLog
from app.modules.fitness.service import FitnessService
from app.modules.intelligence.models import PredictiveWarning
from app.modules.intelligence.service import LifeScoreService
from app.modules.journal.models import JournalEntry
from app.modules.medicine.service import MedicineService
from app.modules.memory.service import MemoryService
from app.modules.scheduler.service import SchedulerService
from app.modules.sleep.models import SleepRecord
from app.modules.sleep.service import SleepService
from app.modules.study.service import StudyService
from app.modules.trading.service import TradingService
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)
ACTION_TAG_PATTERN = re.compile(r"<action>\s*(.*?)\s*</action>", re.DOTALL)


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def create_session(self, user_id: UUID, agent_name: AgentName, title: str) -> ChatSession:
        session = ChatSession(
            user_id=user_id,
            agent_name=agent_name,
            title=title,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_sessions(self, user_id: UUID) -> list[ChatSession]:
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(desc(ChatSession.updated_at))
        )
        # Preload the last message manually or via selectin since it's used for list preview
        sessions = list(result.scalars().all())
        return sessions

    async def delete_session(self, session_id: UUID, user_id: UUID) -> bool:
        result = await self.db.execute(
            select(ChatSession)
            .where(ChatSession.id == session_id)
            .where(ChatSession.user_id == user_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return False
        await self.db.delete(session)
        await self.db.flush()
        return True

    async def get_messages(
        self, session_id: UUID, user_id: UUID, limit: int = 50
    ) -> list[ChatMessage]:
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .where(ChatMessage.user_id == user_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def send_message(
        self, session_id: UUID, user_id: UUID, content: str
    ) -> tuple[ChatMessage, ChatMessage]:
        # Log user message
        user_msg = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            role=MessageRole.USER,
            content=content,
        )
        self.db.add(user_msg)
        await self.db.flush()
        await self.db.refresh(user_msg)

        # Load session & history
        session = await self.db.get(ChatSession, session_id)
        if not session or session.user_id != user_id:
            raise ValueError("Session not found")

        session.updated_at = datetime.now(UTC)
        await self.db.flush()

        history = await self.get_messages(session_id, user_id, limit=30)

        # Determine and fetch context based on agent
        context = await self._gather_context(user_id, session.agent_name)

        # If session has > 30 messages, summarize older ones
        all_msgs = await self.get_messages(session_id, user_id, limit=100)
        if len(all_msgs) > 30:
            older_msgs = all_msgs[:-30]
            summary = await self._summarize_conversation(older_msgs)
            # Inject summary into context
            context["conversation_summary"] = f"Earlier in this conversation: {summary}"
            history = all_msgs[-30:]  # Use only recent 30

        system_prompt = get_agent_prompt(session.agent_name).format(**context)

        # Call Gemini
        assistant_content = await self._call_gemini(system_prompt, history, content)

        # Parse and execute actions
        actions = ActionParser.parse_actions(assistant_content)
        display_text = ActionParser.strip_actions(assistant_content)

        actions_taken = []
        if actions:
            executor = ActionExecutor(self.db, user_id)
            for act in actions:
                res = await executor.execute(act)
                actions_taken.append(
                    {
                        "type": act.type,
                        "params": act.params,
                        "success": res.success,
                        "message": res.message,
                        "data": res.data,
                    }
                )

        # Parse and execute JSON calendar actions:
        # <action>{"type": "calendar_create", ...}</action>
        for payload in ACTION_TAG_PATTERN.findall(assistant_content):
            try:
                action_json = json.loads(payload)
            except Exception:
                continue

            if not isinstance(action_json, dict):
                continue

            action_type = str(action_json.get("type") or "").strip().lower()
            if action_type not in {"calendar_create", "calendar_list", "calendar_delete"}:
                continue

            result_text = await execute_calendar_action(action_json, self.db, user_id)
            actions_taken.append(
                {
                    "type": action_type,
                    "params": action_json,
                    "success": True,
                    "message": result_text,
                    "data": None,
                }
            )

        # Remove JSON action tags from visible response text.
        display_text = ACTION_TAG_PATTERN.sub("", display_text).strip()

        # Prepare final assistant message
        if not display_text.strip():
            display_text = "I have completed those tasks for you."

        if actions_taken:
            confirmations = [a["message"] for a in actions_taken if a["success"]]
            if confirmations:
                display_text += "\n\n" + "\n".join(confirmations)

        assistant_msg = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            role=MessageRole.ASSISTANT,
            content=display_text,
            actions_taken=actions_taken,
        )
        self.db.add(assistant_msg)
        await self.db.flush()
        await self.db.refresh(assistant_msg)

        return user_msg, assistant_msg

    async def _gather_context(self, user_id: UUID, agent_name: AgentName) -> dict:
        auth_service = AuthService(self.db)
        profile = await auth_service.get_profile(user_id)
        now = datetime.now()

        memory_service = MemoryService(self.db)
        memory_insights = await memory_service.get_relevant_memory_context(user_id)

        # Defaults for OS Agent (injects everything)
        context = {
            "name": profile.full_name or profile.username,
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": profile.timezone or "UTC",
            "memory_insights": memory_insights,
            "life_score": 0,
            "schedule_summary": "None",
            "streak": 0,
            "sleep_hours": 0.0,
            "sleep_quality": 0,
            "energy": 0,
            "decisions_count": 0,
            "adherence": 0,
            "cards_due": 0,
            "health_data": "None",
            "study_data": "None",
            "trading_data": "None",
            "executive_data": "None",
            "recovery_data": "None",
            "burnout_score": 0,
            "recent_mood": "unknown",
            "sleep_trend": "unknown",
            "last_workout": "none",
            "calendar_today": "None",
            "recent_journal": "None",
            "conversation_summary": "",
        }

        try:
            if agent_name in [AgentName.OS, AgentName.EXECUTIVE]:
                sched = SchedulerService(self.db)
                plan = await sched.get_today(user_id)
                context["schedule_summary"] = ", ".join(
                    f"{b.start_time.strftime('%H:%M')} {b.title}" for b in plan.blocks[:5]
                )
                context["calendar_today"] = context["schedule_summary"]

            if agent_name in [AgentName.OS, AgentName.HEALTH, AgentName.RECOVERY]:
                sleep = SleepService(self.db)
                stats = await sleep.get_sleep_stats(user_id)
                context["sleep_hours"] = stats.avg_duration / 60
                context["sleep_quality"] = stats.avg_quality_30d

                fitness = FitnessService(self.db)
                en = await fitness.get_energy_forecast(user_id, date.today())
                if en and en.hourly_scores:
                    context["energy"] = next(iter(en.hourly_scores.values()), 50)

                sleep_rows_result = await self.db.execute(
                    select(SleepRecord.sleep_duration_minutes)
                    .where(SleepRecord.user_id == user_id)
                    .order_by(desc(SleepRecord.sleep_date), desc(SleepRecord.created_at))
                    .limit(6)
                )
                recent_sleep_rows = [
                    float(v or 0.0) / 60.0 for v in sleep_rows_result.scalars().all()
                ]
                if len(recent_sleep_rows) >= 6:
                    recent_avg = sum(recent_sleep_rows[:3]) / 3.0
                    previous_avg = sum(recent_sleep_rows[3:6]) / 3.0
                    if recent_avg > previous_avg + 0.3:
                        context["sleep_trend"] = "improving"
                    elif recent_avg < previous_avg - 0.3:
                        context["sleep_trend"] = "declining"
                    else:
                        context["sleep_trend"] = "stable"

                journal_result = await self.db.execute(
                    select(JournalEntry.mood, JournalEntry.word_count, JournalEntry.entry_date)
                    .where(JournalEntry.user_id == user_id)
                    .order_by(desc(JournalEntry.entry_date), desc(JournalEntry.created_at))
                    .limit(1)
                )
                latest_journal = journal_result.first()
                if latest_journal:
                    mood, word_count, entry_date = latest_journal
                    mood_value = str(getattr(mood, "value", mood or "unknown"))
                    context["recent_mood"] = mood_value
                    context["recent_journal"] = (
                        f"{entry_date.isoformat()} mood={mood_value} words={int(word_count or 0)}"
                    )

                workout_result = await self.db.execute(
                    select(
                        WorkoutLog.workout_type,
                        WorkoutLog.duration_minutes,
                        WorkoutLog.workout_date,
                    )
                    .where(WorkoutLog.user_id == user_id)
                    .order_by(desc(WorkoutLog.workout_date), desc(WorkoutLog.created_at))
                    .limit(1)
                )
                latest_workout = workout_result.first()
                if latest_workout:
                    workout_type, duration_minutes, workout_date = latest_workout
                    context["last_workout"] = (
                        f"{workout_type} {int(duration_minutes)}m on {workout_date.isoformat()}"
                    )

                burnout_result = await self.db.execute(
                    select(PredictiveWarning.details)
                    .where(PredictiveWarning.user_id == user_id)
                    .where(PredictiveWarning.warning_type == "burnout_risk")
                    .where(PredictiveWarning.is_active.is_(True))
                    .order_by(
                        desc(PredictiveWarning.detected_at),
                        desc(PredictiveWarning.created_at),
                    )
                    .limit(1)
                )
                burnout_details = burnout_result.scalar_one_or_none() or {}
                if isinstance(burnout_details, dict):
                    context["burnout_score"] = int(float(burnout_details.get("score", 0) or 0))

            if agent_name in [AgentName.OS, AgentName.HEALTH]:
                meds = MedicineService(self.db)
                adh = await meds.get_adherence_stats(user_id)
                context["adherence"] = round(adh.get("overall_adherence", 0) * 100, 1)

            if agent_name in [AgentName.OS, AgentName.STUDY]:
                study = StudyService(self.db)
                cards = await study.get_due_cards(user_id, date.today())
                context["cards_due"] = len(cards)
                context["study_data"] = f"Cards due: {len(cards)}"

            if agent_name in [AgentName.OS, AgentName.TRADING]:
                trading = TradingService(self.db)
                wl = await trading.list_watchlist(user_id)
                context["trading_data"] = f"Watchlist count: {len(wl)}"

            if agent_name in [AgentName.OS, AgentName.EXECUTIVE]:
                dec = DecisionService(self.db)
                decs = await dec.list_decisions(user_id)
                context["decisions_count"] = len([d for d in decs if d.status == "pending"])
                context["executive_data"] = (
                    f"Pending decisions: {context['decisions_count']}\n"
                    f"Schedule: {context['schedule_summary']}"
                )

            if agent_name in [AgentName.OS]:
                ls_service = LifeScoreService(self.db)
                score = await ls_service.get_latest_score(user_id)
                context["life_score"] = int(score.score)

            if agent_name in [AgentName.RECOVERY]:
                context["recovery_data"] = (
                    "Energy forecast suggests dips inside low hours. "
                    "Please ensure prompt alignment."
                )

        except Exception as e:
            logger.warning("chat_context_gather_error", error=str(e))

        return context

    async def _summarize_conversation(self, messages: list[ChatMessage]) -> str:
        if not messages:
            return ""
        text = "\n".join(f"{m.role.value}: {m.content[:200]}" for m in messages[-20:])
        prompt = (
            "Summarize this conversation in 2 sentences, focusing on key topics and "
            f"decisions:\n{text}"
        )
        try:
            summary = await self._call_gemini(
                "You are a conversation summarizer.",
                [],
                prompt,
            )
            return summary[:300]
        except Exception:
            return ""

    async def _call_gemini(
        self, system_prompt: str, history: list[ChatMessage], new_content: str
    ) -> str:
        api_key = self.settings.gemini_api_key.get_secret_value()
        if not api_key:
            return "William Salvator is running in limited mode. AI functionality is not available."

        messages = [{"role": "system", "parts": [{"text": system_prompt}]}]
        for msg in history:
            # Skip storing empty contents if we only had actions
            if not msg.content.strip() and not msg.actions_taken:
                continue
            r = "user" if msg.role == MessageRole.USER else "model"
            messages.append({"role": r, "parts": [{"text": msg.content}]})

        messages.append({"role": "user", "parts": [{"text": new_content}]})

        payload = {
            "systemInstruction": {"role": "system", "parts": [{"text": system_prompt}]},
            "contents": [m for m in messages if m["role"] != "system"],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048,
                "topP": 0.95,
                "topK": 40,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE",
                },
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ],
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
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                raw = response.json()
            observe_ai_call(provider="gemini", duration_seconds=perf_counter() - started)
            if "candidates" in raw and len(raw["candidates"]) > 0:
                parts = raw["candidates"][0]["content"]["parts"]
                text = ""
                for part in parts:
                    text += part.get("text", "")
                return text.strip()
            return "I did not understand that."
        except Exception as exc:
            observe_ai_call(provider="gemini", duration_seconds=perf_counter() - started)
            logger.error("chat_gemini_call_failed", error=str(exc))
            return "I am having trouble connecting to my neural core right now."

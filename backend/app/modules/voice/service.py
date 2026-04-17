"""
WILLIAM OS — Voice Service
Transcription, intent parsing, and voice command execution.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import httpx
import structlog
from app.core.config import get_settings
from app.modules.habits.models import Habit
from app.modules.habits.schemas import HabitCheckInCreate
from app.modules.habits.service import HabitsService
from app.modules.journal.schemas import JournalCreate
from app.modules.journal.service import JournalService
from app.modules.medicine.models import Medicine
from app.modules.medicine.service import MedicineService
from app.modules.scheduler.schemas import RescheduleRequest
from app.modules.scheduler.service import SchedulerService
from app.modules.voice.models import VoiceCommand
from app.modules.voice.schemas import VoiceCommandLogResponse, VoiceCommandResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

INTENT_PROMPT = (
    "Classify this command into one of: reschedule, check_in, journal, query, medicine, unknown. "
    "Return JSON with keys: intent, confidence, extracted_params. Command: {command}"
)


class VoiceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def transcribe(self, audio_bytes: bytes) -> str:
        api_key = self.settings.whisper_api_key.get_secret_value()
        if not api_key or not audio_bytes:
            logger.warning("voice_transcription_skipped", reason="missing_api_key_or_audio")
            return ""

        headers = {"Authorization": f"Bearer {api_key}"}
        files = {"file": ("voice.wav", audio_bytes, "audio/wav")}
        data = {"model": "whisper-1"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers,
                    files=files,
                    data=data,
                )
                response.raise_for_status()
            payload = response.json()
            return str(payload.get("text") or "").strip()
        except Exception as exc:
            logger.warning("voice_transcription_failed", error=str(exc))
            return ""

    async def parse_intent(self, text: str) -> tuple[str, float, dict]:
        api_key = self.settings.gemini_api_key.get_secret_value()
        if not api_key:
            return self._fallback_parse_intent(text)

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )
        payload = {
            "contents": [{"parts": [{"text": INTENT_PROMPT.format(command=text)}]}],
            "generationConfig": {"temperature": 0.1},
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            raw = response.json()
            candidates = raw.get("candidates") or []
            if not candidates:
                return self._fallback_parse_intent(text)

            content = candidates[0].get("content", {})
            parts = content.get("parts") or []
            model_text = (parts[0].get("text") if parts else "") or ""
            parsed = self._extract_json(model_text)
            if not parsed:
                return self._fallback_parse_intent(text)

            intent = str(parsed.get("intent") or "unknown").strip().lower()
            confidence = float(parsed.get("confidence") or 0.0)
            params = parsed.get("extracted_params") or {}
            return intent, confidence, params
        except Exception as exc:
            logger.warning("voice_intent_parse_failed", error=str(exc))
            return self._fallback_parse_intent(text)

    async def execute_intent(
        self,
        user_id: uuid.UUID,
        intent: str,
        params: dict,
        journal_passphrase: str | None = None,
    ) -> str:
        if intent == "reschedule":
            reason = str(params.get("reason") or "Voice reschedule request")
            service = SchedulerService(self.db)
            try:
                await service.reschedule(
                    user_id=user_id,
                    plan_date=date.today(),
                    request=RescheduleRequest(reason=reason, trigger="voice"),
                )
                return "I have rescheduled your day based on your request."
            except Exception as exc:
                return f"I could not reschedule right now: {exc}"

        if intent == "check_in":
            habit_name = str(params.get("habit_name") or "").strip()
            if not habit_name:
                return "Please say which habit to check in, for example: check in meditation."

            result = await self.db.execute(
                select(Habit).where(
                    and_(
                        Habit.user_id == user_id,
                        Habit.is_active.is_(True),
                        func.lower(Habit.name) == habit_name.lower(),
                    )
                )
            )
            habit = result.scalar_one_or_none()
            if habit is None:
                return f"I could not find habit: {habit_name}."

            service = HabitsService(self.db)
            await service.check_in_habit(
                user_id=user_id,
                habit_id=habit.id,
                data=HabitCheckInCreate(completed=True, skipped=False),
            )
            return f"Habit checked in: {habit.name}."

        if intent == "journal":
            content = str(params.get("content") or "").strip()
            if not content:
                return "Please provide journal text after the command."

            supplied = params.get("passphrase")
            passphrase = supplied.strip() if isinstance(supplied, str) else None
            if not passphrase and journal_passphrase:
                passphrase = journal_passphrase.strip()
            if not passphrase:
                return (
                    "Journal passphrase is required for voice journal commands. "
                    "Send journal_passphrase in the request body."
                )

            service = JournalService(self.db)
            await service.create_entry(
                user_id=user_id,
                data=JournalCreate(
                    content=content,
                    passphrase=passphrase,
                    tags=["voice"],
                ),
            )
            return "Journal entry saved."

        if intent == "medicine":
            medicine_name = str(params.get("medicine_name") or "").strip()
            if not medicine_name:
                return "Please specify medicine name, for example: log medicine Vitamin D."

            result = await self.db.execute(
                select(Medicine).where(
                    and_(
                        Medicine.user_id == user_id,
                        Medicine.is_active.is_(True),
                        func.lower(Medicine.name) == medicine_name.lower(),
                    )
                )
            )
            medicine = result.scalar_one_or_none()
            if medicine is None:
                return f"I could not find medicine: {medicine_name}."

            service = MedicineService(self.db)
            # H16: use user's local time, not UTC, for medicine scheduled_time
            from app.modules.auth.models import User

            _user = await self.db.get(User, user_id)
            try:
                _tz = ZoneInfo(_user.timezone or "UTC") if _user else ZoneInfo("UTC")
            except Exception:
                _tz = ZoneInfo("UTC")
            _local_now = datetime.now(UTC).astimezone(_tz)
            await service.log_dose(
                user_id=user_id,
                medicine_id=medicine.id,
                log_date=_local_now.date(),
                scheduled_time=_local_now.time().replace(microsecond=0),
                taken=True,
                skipped=False,
                skip_reason=None,
            )
            return f"Logged medicine as taken: {medicine.name}."

        if intent == "query":
            query_type = str(params.get("query_type") or "today_schedule").strip().lower()
            if query_type == "today_schedule":
                service = SchedulerService(self.db)
                try:
                    today_plan = await service.get_today(user_id)
                    return (
                        f"Today's schedule has {len(today_plan.blocks)} blocks and "
                        f"status {today_plan.status.value}."
                    )
                except Exception:
                    return "No schedule found for today yet."

            if query_type == "medicine_upcoming":
                service = MedicineService(self.db)
                reminders = await service.get_upcoming(user_id=user_id, within_minutes=60)
                return f"You have {len(reminders)} medicine reminders in the next 60 minutes."

            return "I could not understand your query request."

        return (
            "I didn't understand that. Try: reschedule my afternoon, "
            "check in meditation, log journal..."
        )

    async def process_voice_command(
        self,
        user_id: uuid.UUID,
        text_or_audio: str | bytes,
        journal_passphrase: str | None = None,
    ) -> VoiceCommandResponse:
        started = time.monotonic()

        source = "text"
        audio_hash: str | None = None
        if isinstance(text_or_audio, bytes):
            source = "whisper"
            audio_hash = hashlib.sha256(text_or_audio).hexdigest()
            transcription = await self.transcribe(text_or_audio)
        else:
            transcription = text_or_audio.strip()

        intent = "unknown"
        confidence = 0.0
        params: dict = {}
        if transcription:
            intent, confidence, params = await self.parse_intent(transcription)
            if "content" not in params and intent == "journal":
                journal_text = self._extract_after_keyword(transcription, "journal")
                if journal_text:
                    params["content"] = journal_text
            if "habit_name" not in params and intent == "check_in":
                habit_name = self._extract_after_keyword(transcription, "check in")
                if habit_name:
                    params["habit_name"] = habit_name
            if "medicine_name" not in params and intent == "medicine":
                medicine_name = self._extract_after_keyword(transcription, "medicine")
                if medicine_name:
                    params["medicine_name"] = medicine_name

        response_text = await self.execute_intent(
            user_id=user_id,
            intent=intent,
            params=params,
            journal_passphrase=journal_passphrase,
        )
        processing_ms = int((time.monotonic() - started) * 1000)

        command = VoiceCommand(
            user_id=user_id,
            audio_hash=audio_hash,
            transcription=transcription,
            intent=intent,
            intent_confidence=confidence,
            response_text=response_text,
            processing_time_ms=processing_ms,
            source=source,
        )
        self.db.add(command)
        await self.db.flush()

        logger.info(
            "voice_command_processed",
            user_id=str(user_id),
            intent=intent,
            confidence=confidence,
            processing_time_ms=processing_ms,
            source=source,
        )

        return VoiceCommandResponse(
            transcription=transcription,
            intent=intent,
            response_text=response_text,
            processing_time_ms=processing_ms,
        )

    async def get_history(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[VoiceCommandLogResponse]:
        result = await self.db.execute(
            select(VoiceCommand)
            .where(VoiceCommand.user_id == user_id)
            .order_by(VoiceCommand.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        commands = result.scalars().all()
        return [VoiceCommandLogResponse.model_validate(item) for item in commands]

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        candidate = text.strip()
        if not candidate:
            return None

        if "```" in candidate:
            candidate = candidate.replace("```json", "").replace("```", "").strip()

        try:
            loaded = json.loads(candidate)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            return None
        return None

    @staticmethod
    def _extract_after_keyword(text: str, keyword: str) -> str:
        lower = text.lower()
        pos = lower.find(keyword)
        if pos < 0:
            return ""
        return text[pos + len(keyword) :].strip(" :,-")

    @staticmethod
    def _fallback_parse_intent(text: str) -> tuple[str, float, dict]:
        lowered = text.strip().lower()

        if "reschedule" in lowered:
            return "reschedule", 0.7, {"reason": text}
        if "check in" in lowered or "checkin" in lowered:
            habit_name = lowered.replace("check in", "").replace("checkin", "").strip(" :,-")
            return "check_in", 0.7, {"habit_name": habit_name}
        if lowered.startswith("journal") or "journal" in lowered:
            return (
                "journal",
                0.75,
                {"content": VoiceService._extract_after_keyword(text, "journal")},
            )
        if "medicine" in lowered or "tablet" in lowered or "pill" in lowered:
            medicine_name = VoiceService._extract_after_keyword(text, "medicine")
            return "medicine", 0.65, {"medicine_name": medicine_name}
        if "today" in lowered or "schedule" in lowered or "what" in lowered:
            return "query", 0.6, {"query_type": "today_schedule"}
        return "unknown", 0.2, {}

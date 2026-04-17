"""WILLIAM OS - Integrations service implementation."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import desc, func, select

from app.core.events import Event, EventType, event_bus
from app.core.security import decode_token, hash_token
from app.modules.auth.models import ApiKey
from app.modules.decisions.schemas import DecisionChoose, DecisionCreate, DecisionOutcome
from app.modules.decisions.service import DecisionService
from app.modules.fitness.schemas import WorkoutLogCreate
from app.modules.fitness.service import FitnessService
from app.modules.habits.models import Habit
from app.modules.habits.schemas import HabitCheckInCreate
from app.modules.habits.service import HabitsService
from app.modules.integrations.models import IntegrationLog
from app.modules.integrations.schemas import (
    IntegrationApiKeyCreateIn,
    IntegrationApiKeyResponse,
    IntegrationAuthMeta,
    IntegrationDailySummary,
    IntegrationDecisionChooseIn,
    IntegrationDecisionCreateIn,
    IntegrationDecisionOutcomeIn,
    IntegrationHabitCheckInIn,
    IntegrationJournalEntryIn,
    IntegrationMedicineLogIn,
    IntegrationMoodIn,
    IntegrationScheduleBlockIn,
    IntegrationScheduleGenerateIn,
    IntegrationSleepIn,
    IntegrationStudySessionIn,
    IntegrationTelegramDailyIn,
    IntegrationTradeIn,
    IntegrationTriggerIn,
    IntegrationWorkoutIn,
)
from app.modules.intelligence.service import LifeScoreService
from app.modules.intelligence.warnings_service import PredictiveWarningService
from app.modules.journal.schemas import JournalCreate
from app.modules.journal.service import JournalService
from app.modules.medicine.models import Medicine
from app.modules.medicine.service import MedicineService
from app.modules.scheduler.models import BlockCategory
from app.modules.scheduler.schemas import BlockCreate, ScheduleGenerateRequest
from app.modules.scheduler.service import SchedulerService
from app.modules.sleep.schemas import SleepRecordCreate
from app.modules.sleep.service import SleepService
from app.modules.study.models import Subject
from app.modules.study.schemas import StudySessionCreate, SubjectCreate
from app.modules.study.service import StudyService
from app.modules.trading.schemas import TradeLogCreate
from app.modules.trading.service import TradingService
from app.shared.types import AuthenticationError, NotFoundError, ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class IntegrationsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_bearer(self, authorization: str) -> IntegrationAuthMeta:
        if not authorization or not authorization.startswith("Bearer "):
            raise AuthenticationError("Invalid authorization header")
        token = authorization[7:].strip()
        if token.startswith("wos-"):
            return await self._authenticate_api_key(token)
        # M19: decode JWT directly to avoid importing from auth.routes (layering violation)
        try:
            payload = decode_token(token)
            user_id = uuid.UUID(str(payload["sub"]))
        except Exception as exc:
            raise AuthenticationError("Invalid access token") from exc
        return IntegrationAuthMeta(user_id=user_id, source="jwt", token_type="jwt")

    async def log_integration_call(
        self,
        user_id: uuid.UUID,
        endpoint: str,
        source: str,
        payload: dict,
        success: bool,
        error_message: str | None = None,
    ) -> None:
        row = IntegrationLog(
            user_id=user_id,
            endpoint=endpoint,
            source=source,
            payload=payload,
            success=success,
            error_message=error_message,
            processed_at=self._utcnow_naive(),
        )
        self.db.add(row)
        await self.db.flush()

    async def create_api_key(
        self,
        user_id: uuid.UUID,
        data: IntegrationApiKeyCreateIn,
    ) -> IntegrationApiKeyResponse:
        raw_key = self._generate_wos_api_key()
        row = ApiKey(
            user_id=user_id,
            name=data.name.strip(),
            key_hash=hash_token(raw_key),
            key_prefix=raw_key[:16],
            is_active=True,
            last_used_at=None,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return IntegrationApiKeyResponse(
            id=row.id,
            name=row.name,
            key_prefix=row.key_prefix,
            is_active=row.is_active,
            last_used_at=row.last_used_at,
            created_at=row.created_at,
            api_key=raw_key,
        )

    async def list_api_keys(self, user_id: uuid.UUID) -> list[IntegrationApiKeyResponse]:
        result = await self.db.execute(
            select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
        )
        rows = result.scalars().all()
        return [
            IntegrationApiKeyResponse(
                id=row.id,
                name=row.name,
                key_prefix=row.key_prefix,
                is_active=row.is_active,
                last_used_at=row.last_used_at,
                created_at=row.created_at,
                api_key=None,
            )
            for row in rows
        ]

    async def revoke_api_key(self, user_id: uuid.UUID, key_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(ApiKey).where(ApiKey.user_id == user_id).where(ApiKey.id == key_id).limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        row.is_active = False
        await self.db.flush()
        return True

    async def ingest_sleep(self, user_id: uuid.UUID, data: IntegrationSleepIn) -> dict:
        created = await SleepService(self.db).log_sleep(
            user_id=user_id,
            data=SleepRecordCreate(
                sleep_date=data.sleep_date,
                bedtime=data.bedtime,
                wake_time=data.wake_time,
                sleep_quality=data.sleep_quality,
                source=(data.source_device or "integration")[:20],
            ),
        )
        return created.model_dump(mode="json")

    async def ingest_workout(self, user_id: uuid.UUID, data: IntegrationWorkoutIn) -> dict:
        created = await FitnessService(self.db).log_workout(
            user_id=user_id,
            data=WorkoutLogCreate(
                workout_date=data.workout_date,
                workout_type=data.workout_type,
                duration_minutes=data.duration_minutes,
                calories_burned=data.calories,
                notes=data.notes,
            ),
        )
        return created.model_dump(mode="json")

    async def ingest_habit_checkin(
        self,
        user_id: uuid.UUID,
        data: IntegrationHabitCheckInIn,
    ) -> dict:
        habit_id = data.habit_id
        if habit_id is None:
            if not data.habit_name:
                raise ValidationError("Either habit_id or habit_name is required")
            result = await self.db.execute(
                select(Habit)
                .where(Habit.user_id == user_id)
                .where(func.lower(Habit.name) == data.habit_name.strip().lower())
                .limit(1)
            )
            habit = result.scalar_one_or_none()
            if habit is None:
                raise NotFoundError("Habit", data.habit_name)
            habit_id = habit.id

        checkin = await HabitsService(self.db).check_in_habit(
            user_id=user_id,
            habit_id=habit_id,
            data=HabitCheckInCreate(
                check_date=data.check_date or date.today(),
                completed=data.completed,
                skipped=not data.completed,
                notes=data.note,
            ),
        )
        return checkin.model_dump(mode="json")

    async def ingest_journal_entry(
        self,
        user_id: uuid.UUID,
        data: IntegrationJournalEntryIn,
        passphrase: str,
    ) -> dict:
        if not passphrase:
            raise AuthenticationError("X-Journal-Passphrase header is required")
        created = await JournalService(self.db).create_entry(
            user_id=user_id,
            data=JournalCreate(
                content=data.content,
                passphrase=passphrase,
                mood=data.mood,
                tags=data.tags,
            ),
        )
        return created.model_dump(mode="json")

    async def ingest_trade(self, user_id: uuid.UUID, data: IntegrationTradeIn) -> dict:
        created = await TradingService(self.db).log_trade(
            user_id=user_id,
            data=TradeLogCreate(
                symbol=data.symbol,
                exchange=data.exchange,
                action=data.action,
                quantity=data.quantity,
                price=data.price,
                trade_date=data.trade_date or date.today(),
            ),
        )
        return created.model_dump(mode="json")

    async def ingest_medicine_log(self, user_id: uuid.UUID, data: IntegrationMedicineLogIn) -> dict:
        medicine_id = data.medicine_id
        if medicine_id is None:
            if not data.medicine_name:
                raise ValidationError("Either medicine_id or medicine_name is required")
            result = await self.db.execute(
                select(Medicine)
                .where(Medicine.user_id == user_id)
                .where(func.lower(Medicine.name) == data.medicine_name.strip().lower())
                .limit(1)
            )
            med = result.scalar_one_or_none()
            if med is None:
                raise NotFoundError("Medicine", data.medicine_name)
            medicine_id = med.id

        taken_dt = data.taken_at or self._utcnow_naive()
        created = await MedicineService(self.db).log_dose(
            user_id=user_id,
            medicine_id=medicine_id,
            log_date=taken_dt.date(),
            scheduled_time=taken_dt.time().replace(microsecond=0),
            taken=data.taken,
            skipped=not data.taken,
            skip_reason=None if data.taken else (data.note or "integration"),
        )
        return created.model_dump(mode="json")

    async def ingest_mood(
        self,
        user_id: uuid.UUID,
        data: IntegrationMoodIn,
        passphrase: str,
    ) -> dict:
        if not passphrase:
            raise AuthenticationError("X-Journal-Passphrase header is required")
        note = (data.note or "Mood check-in via integration").strip()
        created = await JournalService(self.db).create_entry(
            user_id=user_id,
            data=JournalCreate(
                content=note,
                passphrase=passphrase,
                mood=data.mood,
                tags=["integration", "mood"],
            ),
        )
        return created.model_dump(mode="json")

    async def ingest_study_session(
        self,
        user_id: uuid.UUID,
        data: IntegrationStudySessionIn,
    ) -> dict:
        subject_id = data.subject_id
        if subject_id is None:
            if not data.subject_name:
                raise ValidationError("Either subject_id or subject_name is required")
            result = await self.db.execute(
                select(Subject)
                .where(Subject.user_id == user_id)
                .where(func.lower(Subject.name) == data.subject_name.strip().lower())
                .limit(1)
            )
            subject = result.scalar_one_or_none()
            if subject is None:
                created_subject = await StudyService(self.db).create_subject(
                    user_id=user_id,
                    data=SubjectCreate(
                        name=data.subject_name.strip(),
                        syllabus_topics=[],
                        total_weight=0.0,
                        color="#3B82F6",
                    ),
                )
                subject_id = created_subject.id
            else:
                subject_id = subject.id

        created = await StudyService(self.db).log_session(
            user_id=user_id,
            subject_id=subject_id,
            data=StudySessionCreate(
                subject_id=subject_id,
                duration_minutes=data.duration_minutes,
                comprehension_score=data.comprehension_score,
                topics_covered=data.topics_covered,
                session_date=date.today(),
            ),
        )
        return created.model_dump(mode="json")

    async def ingest_schedule_generate(
        self,
        user_id: uuid.UUID,
        data: IntegrationScheduleGenerateIn,
    ) -> dict:
        plan = await SchedulerService(self.db).generate_daily_plan(
            user_id=user_id,
            request=ScheduleGenerateRequest(
                target_date=data.target_date,
                force_regenerate=data.force_regenerate,
                extra_context=data.extra_context,
            ),
        )
        return plan.model_dump(mode="json")

    async def ingest_schedule_block(
        self,
        user_id: uuid.UUID,
        data: IntegrationScheduleBlockIn,
    ) -> dict:
        scheduler = SchedulerService(self.db)
        try:
            plan = await scheduler.add_block(
                user_id=user_id,
                plan_date=data.plan_date,
                data=BlockCreate(
                    title=data.title,
                    description=data.description,
                    category=BlockCategory(data.category),
                    start_time=data.start_time,
                    end_time=data.end_time,
                    priority=data.priority,
                    is_fixed=data.is_fixed,
                    tags=data.tags,
                    linked_module="integration",
                ),
            )
        except NotFoundError:
            await scheduler.generate_daily_plan(
                user_id=user_id,
                request=ScheduleGenerateRequest(target_date=data.plan_date),
            )
            plan = await scheduler.add_block(
                user_id=user_id,
                plan_date=data.plan_date,
                data=BlockCreate(
                    title=data.title,
                    description=data.description,
                    category=BlockCategory(data.category),
                    start_time=data.start_time,
                    end_time=data.end_time,
                    priority=data.priority,
                    is_fixed=data.is_fixed,
                    tags=data.tags,
                    linked_module="integration",
                ),
            )
        return plan.model_dump(mode="json")

    async def ingest_decision_create(
        self,
        user_id: uuid.UUID,
        data: IntegrationDecisionCreateIn,
    ) -> dict:
        created = await DecisionService(self.db).create_decision(
            user_id=user_id,
            data=DecisionCreate(
                title=data.title,
                description=data.description,
                decision_type=data.decision_type,
                deadline=data.deadline,
                options=data.options,
                criteria=data.criteria,
            ),
        )
        return created.model_dump(mode="json")

    async def ingest_decision_choose(
        self,
        user_id: uuid.UUID,
        data: IntegrationDecisionChooseIn,
    ) -> dict:
        updated = await DecisionService(self.db).choose_option(
            user_id=user_id,
            decision_id=data.decision_id,
            payload=DecisionChoose(
                chosen_option=data.chosen_option,
                reasoning=data.reasoning,
            ),
        )
        return updated.model_dump(mode="json")

    async def ingest_decision_outcome(
        self,
        user_id: uuid.UUID,
        data: IntegrationDecisionOutcomeIn,
    ) -> dict:
        updated = await DecisionService(self.db).log_outcome(
            user_id=user_id,
            decision_id=data.decision_id,
            payload=DecisionOutcome(
                outcome=data.outcome,
                outcome_rating=data.outcome_rating,
            ),
        )
        return updated.model_dump(mode="json")

    async def telegram_daily_action(
        self,
        user_id: uuid.UUID,
        data: IntegrationTelegramDailyIn,
    ) -> dict:
        if data.action == "today_schedule":
            scheduler = SchedulerService(self.db)
            try:
                plan = await scheduler.get_today(user_id=user_id)
            except NotFoundError:
                return {"action": "today_schedule", "plan_date": str(date.today()), "blocks": []}
            return {
                "action": "today_schedule",
                "plan_date": str(plan.plan_date),
                "blocks": [item.model_dump(mode="json") for item in plan.blocks],
            }

        if data.action == "daily_summary":
            return {"action": "daily_summary", "summary": await self.daily_summary(user_id)}

        if data.action == "habit_checkin":
            if not data.habit_name:
                raise ValidationError("habit_name is required")
            payload = IntegrationHabitCheckInIn(
                habit_name=data.habit_name,
                completed=True,
                check_date=date.today(),
            )
            result = await self.ingest_habit_checkin(user_id=user_id, data=payload)
            return {"action": "habit_checkin", "result": result}

        if data.action == "quick_journal":
            if not data.journal_content:
                raise ValidationError("journal_content is required")
            if not data.journal_passphrase:
                raise AuthenticationError("journal_passphrase is required")
            payload = IntegrationJournalEntryIn(
                content=data.journal_content, tags=["telegram", "daily"]
            )
            result = await self.ingest_journal_entry(
                user_id=user_id,
                data=payload,
                passphrase=data.journal_passphrase,
            )
            return {"action": "quick_journal", "result": result}

        if data.action == "study_log":
            if not data.study_subject_name:
                raise ValidationError("study_subject_name is required")
            payload = IntegrationStudySessionIn(
                subject_name=data.study_subject_name,
                duration_minutes=data.study_duration_minutes or 30,
                comprehension_score=data.study_comprehension_score or 5,
                topics_covered=data.study_topics,
            )
            result = await self.ingest_study_session(user_id=user_id, data=payload)
            return {"action": "study_log", "result": result}

        raise ValidationError(f"Unsupported action: {data.action}")

    async def trigger_event(self, user_id: uuid.UUID, data: IntegrationTriggerIn) -> dict:
        await event_bus.publish(
            Event(
                type=EventType.INTEGRATION_TRIGGERED,
                data={"event_name": data.event_name, "payload": data.payload},
                user_id=user_id,
            )
        )

        queued_webhooks = 0
        try:
            from app.modules.rules.service import WebhookDispatcher

            queued_webhooks = await WebhookDispatcher(self.db).dispatch_event(
                user_id=user_id,
                event_type=data.event_name,
                payload={
                    "event_type": data.event_name,
                    "source": "integrations.trigger",
                    "payload": data.payload,
                    "triggered_at": self._utcnow_naive().isoformat(),
                },
            )
        except Exception:
            queued_webhooks = 0

        return {
            "accepted": True,
            "event_name": data.event_name,
            "queued_webhooks": queued_webhooks,
        }

    async def daily_summary(self, user_id: uuid.UUID) -> dict:
        sleep = await self._safe_call(SleepService(self.db).get_sleep_stats(user_id), {})
        habits = await self._safe_call(HabitsService(self.db).list_habits(user_id, True, 20, 0), [])
        fitness = await self._safe_call(
            FitnessService(self.db).get_daily_summary(user_id, date.today()),
            {},
        )
        study = await self._safe_call(StudyService(self.db).get_progress(user_id), [])
        medicine = await self._safe_call(
            MedicineService(self.db).get_adherence_stats(user_id, days=30), {}
        )
        life_score = await self._safe_call(LifeScoreService(self.db).get_latest_score(user_id), {})
        warnings = await self._safe_call(
            PredictiveWarningService(self.db).get_active_warnings(user_id), []
        )

        payload = IntegrationDailySummary(
            sleep=sleep.model_dump(mode="json") if hasattr(sleep, "model_dump") else sleep,
            habits={
                "active_count": len(habits),
                "items": [item.model_dump(mode="json") for item in habits],
            },
            fitness=fitness.model_dump(mode="json") if hasattr(fitness, "model_dump") else fitness,
            study={
                "subjects": [item.model_dump(mode="json") for item in study],
                "weak_subjects": [
                    item.model_dump(mode="json")
                    for item in study
                    if float(item.avg_comprehension) < 6.0
                ],
            },
            medicine=medicine.model_dump(mode="json")
            if hasattr(medicine, "model_dump")
            else medicine,
            life_score=life_score.model_dump(mode="json")
            if hasattr(life_score, "model_dump")
            else life_score,
            warnings={
                "count": len(warnings),
                "items": [item.model_dump(mode="json") for item in warnings],
            },
        )
        return payload.model_dump(mode="json")

    async def sync_status(self, user_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(IntegrationLog)
            .where(IntegrationLog.user_id == user_id)
            .order_by(desc(IntegrationLog.processed_at), desc(IntegrationLog.created_at))
            .limit(100)
        )
        rows = result.scalars().all()
        errors = [item for item in rows if not item.success]
        return {
            "total_calls": len(rows),
            "error_count": len(errors),
            "last_processed_at": rows[0].processed_at.isoformat() if rows else None,
            "last_error": errors[0].error_message if errors else None,
        }

    async def _authenticate_api_key(self, token: str) -> IntegrationAuthMeta:
        digest = hash_token(token)
        prefix = token[:16]
        result = await self.db.execute(
            select(ApiKey)
            .where(ApiKey.key_prefix == prefix)
            .where(ApiKey.is_active.is_(True))
            .limit(5)
        )
        candidates = result.scalars().all()
        api_key = next((item for item in candidates if item.key_hash == digest), None)
        if api_key is None:
            raise AuthenticationError("Invalid API key")
        api_key.last_used_at = self._utcnow_naive()
        await self.db.flush()
        return IntegrationAuthMeta(
            user_id=api_key.user_id, source=api_key.name, token_type="api_key"
        )

    @staticmethod
    async def _safe_call(coro, default):
        try:
            return await coro
        except Exception:
            return default

    @staticmethod
    def _generate_wos_api_key() -> str:
        return f"wos-{secrets.token_urlsafe(32)}"

    @staticmethod
    def _utcnow_naive() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

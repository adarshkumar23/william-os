"""
WILLIAM OS — Export Service
User data export (full + journal decrypted), summary counts, and account deletion.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import uuid
import zipfile
from datetime import date, datetime, time
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.inspection import inspect as sa_inspect

from app.core.security import decrypt_text, encrypt_text
from app.modules.audit.models import AuditAction, AuditLog
from app.modules.auth.models import User, UserDevice
from app.modules.decisions.models import Decision
from app.modules.email_intel.models import EmailAccount, EmailSummary
from app.modules.fitness.models import EnergyForecast, FitnessDevice, HealthMetric, WorkoutLog
from app.modules.habits.models import Habit, HabitCheckIn, ProcrastinationSignal
from app.modules.journal.models import JournalEntry
from app.modules.medicine.models import Medicine, MedicineLog
from app.modules.messaging.models import NotificationLog, TelegramUser
from app.modules.scheduler.models import DailyPlan, RescheduleEvent, ScheduleBlock
from app.modules.sleep.models import SleepDebt, SleepRecommendation, SleepRecord
from app.modules.study.models import MockTest, RevisionCard, StudySession, Subject
from app.modules.trading.models import PortfolioSnapshot, PriceAlert, TradeLog, Watchlist
from app.modules.voice.models import VoiceCommand
from app.shared.types import EncryptionError, NotFoundError, ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class ExportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_data_summary(self, user_id: uuid.UUID) -> dict[str, int]:
        summary = {
            "devices": await self._count(UserDevice, UserDevice.user_id == user_id),
            "schedule_plans": await self._count(DailyPlan, DailyPlan.user_id == user_id),
            "schedule_blocks": await self._count_for_plan_children(
                ScheduleBlock,
                DailyPlan,
                user_id,
            ),
            "reschedule_events": await self._count_for_plan_children(
                RescheduleEvent,
                DailyPlan,
                user_id,
            ),
            "habits": await self._count(Habit, Habit.user_id == user_id),
            "habit_check_ins": await self._count_for_parent_children(
                HabitCheckIn,
                Habit,
                HabitCheckIn.habit_id,
                Habit.id,
                user_id,
            ),
            "procrastination_signals": await self._count(
                ProcrastinationSignal,
                ProcrastinationSignal.user_id == user_id,
            ),
            "journal_entries": await self._count(JournalEntry, JournalEntry.user_id == user_id),
            "medicines": await self._count(Medicine, Medicine.user_id == user_id),
            "medicine_logs": await self._count_for_parent_children(
                MedicineLog,
                Medicine,
                MedicineLog.medicine_id,
                Medicine.id,
                user_id,
            ),
            "email_accounts": await self._count(EmailAccount, EmailAccount.user_id == user_id),
            "email_summaries": await self._count(EmailSummary, EmailSummary.user_id == user_id),
            "subjects": await self._count(Subject, Subject.user_id == user_id),
            "study_sessions": await self._count(StudySession, StudySession.user_id == user_id),
            "revision_cards": await self._count(RevisionCard, RevisionCard.user_id == user_id),
            "mock_tests": await self._count(MockTest, MockTest.user_id == user_id),
            "fitness_devices": await self._count(FitnessDevice, FitnessDevice.user_id == user_id),
            "health_metrics": await self._count(HealthMetric, HealthMetric.user_id == user_id),
            "workout_logs": await self._count(WorkoutLog, WorkoutLog.user_id == user_id),
            "energy_forecasts": await self._count(
                EnergyForecast,
                EnergyForecast.user_id == user_id,
            ),
            "watchlist": await self._count(Watchlist, Watchlist.user_id == user_id),
            "trade_logs": await self._count(TradeLog, TradeLog.user_id == user_id),
            "portfolio_snapshots": await self._count(
                PortfolioSnapshot,
                PortfolioSnapshot.user_id == user_id,
            ),
            "price_alerts": await self._count(PriceAlert, PriceAlert.user_id == user_id),
            "sleep_records": await self._count(SleepRecord, SleepRecord.user_id == user_id),
            "sleep_recommendations": await self._count(
                SleepRecommendation,
                SleepRecommendation.user_id == user_id,
            ),
            "sleep_debts": await self._count(SleepDebt, SleepDebt.user_id == user_id),
            "decisions": await self._count(Decision, Decision.user_id == user_id),
            "audit_logs": await self._count(AuditLog, AuditLog.user_id == user_id),
            "voice_commands": await self._count(VoiceCommand, VoiceCommand.user_id == user_id),
            "telegram_links": await self._count(TelegramUser, TelegramUser.user_id == user_id),
            "notifications": await self._count(NotificationLog, NotificationLog.user_id == user_id),
        }
        summary["total_records"] = sum(summary.values())
        return summary

    async def export_full(self, user_id: uuid.UUID) -> bytes:
        payload = await self._build_full_payload(user_id)

        await self._log_export(user_id, export_type="full")
        return self._to_zip_bytes(payload, filename="william_export_full.json")

    async def export_lifetime(self, user_id: uuid.UUID, passphrase: str) -> bytes:
        payload = await self._build_full_payload(user_id)
        json_content = json.dumps(payload, indent=2, default=str)
        csv_content = self._summary_to_csv(payload["summary"])

        encrypted_json = encrypt_text(json_content, passphrase)
        encrypted_csv = encrypt_text(csv_content, passphrase)

        files = {
            "william_lifetime_export.json.enc": encrypted_json,
            "william_lifetime_export.csv.enc": encrypted_csv,
            "manifest.json": json.dumps(
                {
                    "generated_at": payload["generated_at"],
                    "user_id": payload["user_id"],
                    "encryption": "AES-256-GCM (PBKDF2-HMAC-SHA256)",
                    "files": [
                        "william_lifetime_export.json.enc",
                        "william_lifetime_export.csv.enc",
                    ],
                },
                indent=2,
            ).encode("utf-8"),
        }

        await self._log_export(user_id, export_type="lifetime_encrypted")
        return self._to_zip_multi_bytes(files)

    async def export_journal(self, user_id: uuid.UUID, passphrase: str) -> bytes:
        result = await self.db.execute(
            select(JournalEntry)
            .where(JournalEntry.user_id == user_id)
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
        )
        entries = result.scalars().all()

        exported_entries: list[dict[str, Any]] = []
        for entry in entries:
            try:
                content = decrypt_text(entry.encrypted_content, passphrase)
                summary = (
                    decrypt_text(entry.encrypted_summary, passphrase)
                    if entry.encrypted_summary is not None
                    else None
                )
            except Exception as exc:
                raise EncryptionError() from exc

            exported_entries.append(
                {
                    "id": str(entry.id),
                    "entry_date": entry.entry_date.isoformat(),
                    "mood": entry.mood.value if entry.mood else None,
                    "tags": entry.tags,
                    "word_count": entry.word_count,
                    "content": content,
                    "summary": summary,
                    "created_at": entry.created_at.isoformat(),
                }
            )

        payload = {
            "generated_at": datetime.now().isoformat(),
            "user_id": str(user_id),
            "entry_count": len(exported_entries),
            "entries": exported_entries,
        }

        await self._log_export(user_id, export_type="journal_decrypted")
        return self._to_zip_bytes(payload, filename="william_export_journal.json")

    async def delete_account(self, user_id: uuid.UUID) -> None:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User", str(user_id))

        summary_before = await self.get_data_summary(user_id)

        # Child rows that do not have direct user_id.
        await self._delete_plan_children(ScheduleBlock, user_id)
        await self._delete_plan_children(RescheduleEvent, user_id)
        await self._delete_parent_children(
            HabitCheckIn,
            Habit,
            HabitCheckIn.habit_id,
            Habit.id,
            user_id,
        )
        await self._delete_parent_children(
            MedicineLog,
            Medicine,
            MedicineLog.medicine_id,
            Medicine.id,
            user_id,
        )

        # Direct user-scoped rows.
        direct_models = [
            NotificationLog,
            TelegramUser,
            VoiceCommand,
            AuditLog,
            Decision,
            SleepDebt,
            SleepRecommendation,
            SleepRecord,
            PriceAlert,
            PortfolioSnapshot,
            TradeLog,
            Watchlist,
            EnergyForecast,
            WorkoutLog,
            HealthMetric,
            FitnessDevice,
            MockTest,
            RevisionCard,
            StudySession,
            Subject,
            EmailSummary,
            EmailAccount,
            Medicine,
            JournalEntry,
            ProcrastinationSignal,
            Habit,
            DailyPlan,
            UserDevice,
        ]
        for model in direct_models:
            await self.db.execute(delete(model).where(model.user_id == user_id))

        await self.db.execute(delete(User).where(User.id == user_id))

        # Verify no user-scoped records remain.
        post_counts = await self.get_data_summary(user_id)
        still_present = {k: v for k, v in post_counts.items() if v > 0 and k != "total_records"}
        user_still_exists = await self.db.get(User, user_id) is not None
        verified = not still_present and not user_still_exists
        if not verified:
            raise ValidationError("Account deletion verification failed")

        self.db.add(
            AuditLog(
                user_id=None,
                action=AuditAction.DATA_DELETE,
                module="export",
                details={
                    "deleted_user_id": str(user_id),
                    "verified": verified,
                    "summary_before": summary_before,
                },
            )
        )
        await self.db.flush()

        logger.info("account_deleted", user_id=str(user_id), verified=verified)

    async def _rows(self, model, where_clause) -> list[dict[str, Any]]:
        result = await self.db.execute(select(model).where(where_clause))
        rows = result.scalars().all()
        return [self._serialize_model(row) for row in rows]

    async def _rows_for_plan_children(
        self,
        child_model,
        user_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(child_model)
            .join(DailyPlan, child_model.plan_id == DailyPlan.id)
            .where(DailyPlan.user_id == user_id)
        )
        rows = result.scalars().all()
        return [self._serialize_model(row) for row in rows]

    async def _rows_for_parent_children(
        self,
        child_model,
        parent_model,
        child_fk_col,
        parent_pk_col,
        user_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        parent_ids = (
            select(parent_pk_col)
            .select_from(parent_model)
            .where(parent_model.user_id == user_id)
            .scalar_subquery()
        )
        result = await self.db.execute(select(child_model).where(child_fk_col.in_(parent_ids)))
        rows = result.scalars().all()
        return [self._serialize_model(row) for row in rows]

    async def _journal_metadata_rows(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        result = await self.db.execute(select(JournalEntry).where(JournalEntry.user_id == user_id))
        entries = result.scalars().all()
        metadata_rows = []
        for entry in entries:
            metadata_rows.append(
                {
                    "id": str(entry.id),
                    "user_id": str(entry.user_id),
                    "entry_date": entry.entry_date.isoformat(),
                    "mood": entry.mood.value if entry.mood else None,
                    "tags": entry.tags,
                    "word_count": entry.word_count,
                    "has_summary": entry.encrypted_summary is not None,
                    "created_at": entry.created_at.isoformat(),
                }
            )
        return metadata_rows

    async def _count(self, model, where_clause) -> int:
        result = await self.db.execute(select(func.count()).select_from(model).where(where_clause))
        return int(result.scalar() or 0)

    async def _count_for_plan_children(self, child_model, parent_model, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(child_model)
            .join(parent_model, child_model.plan_id == parent_model.id)
            .where(parent_model.user_id == user_id)
        )
        return int(result.scalar() or 0)

    async def _count_for_parent_children(
        self,
        child_model,
        parent_model,
        child_fk_col,
        parent_pk_col,
        user_id: uuid.UUID,
    ) -> int:
        parent_ids = (
            select(parent_pk_col)
            .select_from(parent_model)
            .where(parent_model.user_id == user_id)
            .scalar_subquery()
        )
        result = await self.db.execute(
            select(func.count())
            .select_from(child_model)
            .where(child_fk_col.in_(parent_ids))
        )
        return int(result.scalar() or 0)

    async def _delete_plan_children(self, child_model, user_id: uuid.UUID) -> None:
        plan_ids = (
            select(DailyPlan.id)
            .where(DailyPlan.user_id == user_id)
            .scalar_subquery()
        )
        await self.db.execute(delete(child_model).where(child_model.plan_id.in_(plan_ids)))

    async def _delete_parent_children(
        self,
        child_model,
        parent_model,
        child_fk_col,
        parent_pk_col,
        user_id: uuid.UUID,
    ) -> None:
        parent_ids = (
            select(parent_pk_col)
            .select_from(parent_model)
            .where(parent_model.user_id == user_id)
            .scalar_subquery()
        )
        await self.db.execute(delete(child_model).where(child_fk_col.in_(parent_ids)))

    async def _log_export(self, user_id: uuid.UUID, export_type: str) -> None:
        self.db.add(
            AuditLog(
                user_id=user_id,
                action=AuditAction.DATA_EXPORT,
                module="export",
                details={"export_type": export_type},
            )
        )
        await self.db.flush()

    async def _build_full_payload(self, user_id: uuid.UUID) -> dict[str, Any]:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User", str(user_id))

        return {
            "generated_at": datetime.now().isoformat(),
            "user_id": str(user_id),
            "summary": await self.get_data_summary(user_id),
            "data": {
                "auth_profile": [self._serialize_model(user)],
                "devices": await self._rows(UserDevice, UserDevice.user_id == user_id),
                "schedule_plans": await self._rows(DailyPlan, DailyPlan.user_id == user_id),
                "schedule_blocks": await self._rows_for_plan_children(ScheduleBlock, user_id),
                "reschedule_events": await self._rows_for_plan_children(RescheduleEvent, user_id),
                "habits": await self._rows(Habit, Habit.user_id == user_id),
                "habit_check_ins": await self._rows_for_parent_children(
                    HabitCheckIn,
                    Habit,
                    HabitCheckIn.habit_id,
                    Habit.id,
                    user_id,
                ),
                "procrastination_signals": await self._rows(
                    ProcrastinationSignal,
                    ProcrastinationSignal.user_id == user_id,
                ),
                "journal_metadata": await self._journal_metadata_rows(user_id),
                "medicines": await self._rows(Medicine, Medicine.user_id == user_id),
                "medicine_logs": await self._rows_for_parent_children(
                    MedicineLog,
                    Medicine,
                    MedicineLog.medicine_id,
                    Medicine.id,
                    user_id,
                ),
                "email_accounts": await self._rows(EmailAccount, EmailAccount.user_id == user_id),
                "email_summaries": await self._rows(EmailSummary, EmailSummary.user_id == user_id),
                "subjects": await self._rows(Subject, Subject.user_id == user_id),
                "study_sessions": await self._rows(StudySession, StudySession.user_id == user_id),
                "revision_cards": await self._rows(RevisionCard, RevisionCard.user_id == user_id),
                "mock_tests": await self._rows(MockTest, MockTest.user_id == user_id),
                "fitness_devices": await self._rows(
                    FitnessDevice,
                    FitnessDevice.user_id == user_id,
                ),
                "health_metrics": await self._rows(HealthMetric, HealthMetric.user_id == user_id),
                "workout_logs": await self._rows(WorkoutLog, WorkoutLog.user_id == user_id),
                "energy_forecasts": await self._rows(
                    EnergyForecast,
                    EnergyForecast.user_id == user_id,
                ),
                "watchlist": await self._rows(Watchlist, Watchlist.user_id == user_id),
                "trade_logs": await self._rows(TradeLog, TradeLog.user_id == user_id),
                "portfolio_snapshots": await self._rows(
                    PortfolioSnapshot,
                    PortfolioSnapshot.user_id == user_id,
                ),
                "price_alerts": await self._rows(PriceAlert, PriceAlert.user_id == user_id),
                "sleep_records": await self._rows(SleepRecord, SleepRecord.user_id == user_id),
                "sleep_recommendations": await self._rows(
                    SleepRecommendation,
                    SleepRecommendation.user_id == user_id,
                ),
                "sleep_debts": await self._rows(SleepDebt, SleepDebt.user_id == user_id),
                "decisions": await self._rows(Decision, Decision.user_id == user_id),
                "audit_logs": await self._rows(AuditLog, AuditLog.user_id == user_id),
                "voice_commands": await self._rows(VoiceCommand, VoiceCommand.user_id == user_id),
                "telegram_links": await self._rows(TelegramUser, TelegramUser.user_id == user_id),
                "notifications": await self._rows(
                    NotificationLog,
                    NotificationLog.user_id == user_id,
                ),
            },
        }

    @staticmethod
    def _summary_to_csv(summary: dict[str, int]) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["dataset", "records"])
        for key, value in summary.items():
            writer.writerow([key, value])
        return buffer.getvalue()

    def _serialize_model(self, row) -> dict[str, Any]:
        mapper = sa_inspect(row.__class__)
        data: dict[str, Any] = {}
        for column in mapper.columns:
            data[column.key] = self._serialize_value(getattr(row, column.key))
        return data

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, uuid.UUID):
            return str(value)
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, bytes):
            return base64.b64encode(value).decode("ascii")
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        if isinstance(value, dict):
            return {str(k): self._serialize_value(v) for k, v in value.items()}
        return value

    @staticmethod
    def _to_zip_bytes(payload: dict[str, Any], filename: str) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(filename, json.dumps(payload, indent=2, default=str))
        return buffer.getvalue()

    @staticmethod
    def _to_zip_multi_bytes(files: dict[str, bytes]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for filename, content in files.items():
                archive.writestr(filename, content)
        return buffer.getvalue()

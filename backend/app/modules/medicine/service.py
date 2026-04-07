"""
WILLIAM OS — Medicine Reminder Service
CRUD, dose logging, upcoming reminders, adherence metrics, and refill checks.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

import structlog
from app.core.events import Event, EventType, event_bus
from app.modules.medicine.models import Medicine, MedicineLog
from app.modules.medicine.schemas import (
    AdherenceStats,
    MedicineCreate,
    MedicineLogResponse,
    MedicineResponse,
    MedicineUpdate,
    UpcomingReminder,
)
from app.shared.types import NotFoundError, ValidationError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class MedicineService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_medicine(self, user_id: uuid.UUID, data: MedicineCreate) -> MedicineResponse:
        medicine = Medicine(user_id=user_id, **data.model_dump())
        self.db.add(medicine)
        await self.db.flush()
        await self.db.refresh(medicine)

        logger.info("medicine_created", user_id=str(user_id), medicine_id=str(medicine.id))
        return MedicineResponse.model_validate(medicine)

    async def update_medicine(
        self,
        user_id: uuid.UUID,
        medicine_id: uuid.UUID,
        data: MedicineUpdate,
    ) -> MedicineResponse:
        medicine = await self._get_medicine_for_user(user_id=user_id, medicine_id=medicine_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(medicine, field, value)

        await self.db.flush()
        await self.db.refresh(medicine)

        logger.info("medicine_updated", user_id=str(user_id), medicine_id=str(medicine_id))
        return MedicineResponse.model_validate(medicine)

    async def delete_medicine(self, user_id: uuid.UUID, medicine_id: uuid.UUID) -> None:
        medicine = await self._get_medicine_for_user(user_id=user_id, medicine_id=medicine_id)
        await self.db.delete(medicine)
        await self.db.flush()

        logger.info("medicine_deleted", user_id=str(user_id), medicine_id=str(medicine_id))

    async def list_active(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MedicineResponse]:
        today = date.today()
        query = (
            select(Medicine)
            .where(Medicine.user_id == user_id)
            .where(Medicine.is_active.is_(True))
            .where((Medicine.start_date.is_(None)) | (Medicine.start_date <= today))
            .where((Medicine.end_date.is_(None)) | (Medicine.end_date >= today))
            .order_by(Medicine.name.asc())
        )
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        medicines = result.scalars().all()
        return [MedicineResponse.model_validate(medicine) for medicine in medicines]

    async def get_medicine(self, user_id: uuid.UUID, medicine_id: uuid.UUID) -> MedicineResponse:
        medicine = await self._get_medicine_for_user(user_id=user_id, medicine_id=medicine_id)
        return MedicineResponse.model_validate(medicine)

    async def log_dose(
        self,
        user_id: uuid.UUID,
        medicine_id: uuid.UUID,
        log_date: date,
        scheduled_time: time,
        taken: bool,
        skipped: bool,
        skip_reason: str | None,
    ) -> MedicineLogResponse:
        medicine = await self._get_medicine_for_user(user_id=user_id, medicine_id=medicine_id)

        if taken and skipped:
            raise ValidationError("Dose cannot be both taken and skipped")
        if not taken and not skipped:
            raise ValidationError("Dose must be marked taken or skipped")
        if skipped and not skip_reason:
            raise ValidationError("skip_reason is required when skipped=true")

        existing_result = await self.db.execute(
            select(MedicineLog).where(
                and_(
                    MedicineLog.medicine_id == medicine.id,
                    MedicineLog.log_date == log_date,
                    MedicineLog.scheduled_time == scheduled_time,
                )
            )
        )
        log = existing_result.scalar_one_or_none()

        taken_at = datetime.now(UTC).replace(tzinfo=None).time().replace(microsecond=0) if taken else None

        if log:
            log.taken = taken
            log.skipped = skipped
            log.skip_reason = skip_reason
            log.taken_at = taken_at
        else:
            log = MedicineLog(
                medicine_id=medicine.id,
                log_date=log_date,
                scheduled_time=scheduled_time,
                taken=taken,
                taken_at=taken_at,
                skipped=skipped,
                skip_reason=skip_reason,
            )
            self.db.add(log)

        if taken and medicine.remaining_count is not None:
            medicine.remaining_count = max(0, medicine.remaining_count - 1)

        await self.db.flush()
        await self.db.refresh(log)

        if taken:
            scheduled_dt = datetime.combine(log_date, scheduled_time)
            taken_dt = datetime.combine(log_date, taken_at) if taken_at else scheduled_dt
            delta_minutes = (taken_dt - scheduled_dt).total_seconds() / 60.0
            is_on_time = abs(delta_minutes) <= 30.0

            await event_bus.publish(
                Event(
                    type=EventType.MEDICINE_TAKEN,
                    data={
                        "medicine_id": str(medicine.id),
                        "medicine_name": medicine.name,
                        "log_date": str(log_date),
                        "scheduled_time": scheduled_time.isoformat(),
                        "taken_at": taken_at.isoformat() if taken_at else None,
                        "is_on_time": is_on_time,
                    },
                    user_id=user_id,
                )
            )
        else:
            await event_bus.publish(
                Event(
                    type=EventType.MEDICINE_MISSED,
                    data={
                        "medicine_id": str(medicine.id),
                        "medicine_name": medicine.name,
                        "log_date": str(log_date),
                        "scheduled_time": scheduled_time.isoformat(),
                        "reason": skip_reason,
                    },
                    user_id=user_id,
                )
            )

        logger.info(
            "medicine_logged",
            user_id=str(user_id),
            medicine_id=str(medicine.id),
            taken=taken,
            skipped=skipped,
        )

        return MedicineLogResponse(
            id=log.id,
            medicine_id=log.medicine_id,
            log_date=log.log_date,
            scheduled_time=log.scheduled_time.isoformat(),
            taken=log.taken,
            taken_at=log.taken_at.isoformat() if log.taken_at else None,
            skipped=log.skipped,
            skip_reason=log.skip_reason,
            created_at=log.created_at,
            updated_at=log.updated_at,
        )

    async def get_upcoming(
        self,
        user_id: uuid.UUID,
        within_minutes: int = 30,
    ) -> list[UpcomingReminder]:
        now = datetime.now(UTC).replace(tzinfo=None)
        today = now.date()

        result = await self.db.execute(
            select(Medicine)
            .where(Medicine.user_id == user_id)
            .where(Medicine.is_active.is_(True))
            .where((Medicine.start_date.is_(None)) | (Medicine.start_date <= today))
            .where((Medicine.end_date.is_(None)) | (Medicine.end_date >= today))
            .order_by(Medicine.name.asc())
        )
        medicines = result.scalars().all()

        reminders: list[UpcomingReminder] = []
        for medicine in medicines:
            existing_logs = await self.db.execute(
                select(MedicineLog).where(
                    and_(
                        MedicineLog.medicine_id == medicine.id,
                        MedicineLog.log_date == today,
                    )
                )
            )
            logged_slots = {
                item.scheduled_time.isoformat(timespec="minutes")
                for item in existing_logs.scalars().all()
            }

            for reminder_time in medicine.reminder_times:
                parsed_time = self._parse_time(reminder_time)
                if parsed_time is None:
                    continue

                slot = parsed_time.isoformat(timespec="minutes")
                if slot in logged_slots:
                    continue

                scheduled = datetime.combine(today, parsed_time)
                delta_minutes = (scheduled - now).total_seconds() / 60
                if 0 <= delta_minutes <= within_minutes:
                    reminders.append(
                        UpcomingReminder(
                            medicine_id=medicine.id,
                            medicine_name=medicine.name,
                            dosage=medicine.dosage,
                            scheduled_time=slot,
                            with_food=medicine.with_food,
                            instructions=medicine.instructions,
                        )
                    )

        reminders.sort(key=lambda item: item.scheduled_time)
        return reminders

    async def get_adherence_stats(self, user_id: uuid.UUID, days: int = 30) -> AdherenceStats:
        if days <= 0:
            raise ValidationError("days must be greater than 0")

        cutoff = date.today() - timedelta(days=days - 1)
        result = await self.db.execute(
            select(MedicineLog)
            .join(Medicine, Medicine.id == MedicineLog.medicine_id)
            .where(Medicine.user_id == user_id)
            .where(MedicineLog.log_date >= cutoff)
        )
        logs = result.scalars().all()

        total_scheduled = len(logs)
        total_taken = sum(1 for log in logs if log.taken)
        total_skipped = sum(1 for log in logs if log.skipped)
        adherence_rate = 0.0
        if total_scheduled > 0:
            adherence_rate = round((total_taken / total_scheduled) * 100, 2)

        return AdherenceStats(
            total_scheduled=total_scheduled,
            total_taken=total_taken,
            total_skipped=total_skipped,
            adherence_rate=adherence_rate,
        )

    async def check_refills(self, user_id: uuid.UUID) -> list[MedicineResponse]:
        medicines = await self.list_active(user_id)
        low_stock: list[MedicineResponse] = []

        for medicine in medicines:
            if medicine.remaining_count is None:
                continue

            refill_threshold = medicine.refill_reminder_days * max(1, medicine.times_per_day)
            if medicine.remaining_count <= refill_threshold:
                low_stock.append(medicine)

        return low_stock

    async def _get_medicine_for_user(self, user_id: uuid.UUID, medicine_id: uuid.UUID) -> Medicine:
        result = await self.db.execute(
            select(Medicine).where(
                and_(
                    Medicine.id == medicine_id,
                    Medicine.user_id == user_id,
                )
            )
        )
        medicine = result.scalar_one_or_none()
        if not medicine:
            raise NotFoundError("Medicine", str(medicine_id))
        return medicine

    @staticmethod
    def _parse_time(value: str) -> time | None:
        for format_str in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(value, format_str).time()
            except ValueError:
                continue
        return None

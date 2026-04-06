"""
WILLIAM OS — Medicine Reminder Routes
CRUD, dose logging, upcoming reminders, adherence stats, and refill checks.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.medicine.schemas import MedicineCreate, MedicineLogCreate, MedicineUpdate
from app.modules.medicine.service import MedicineService
from app.shared.types import success
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/medicine", tags=["Medicine Reminders"])


@router.post("", status_code=201)
async def create_medicine(
    data: MedicineCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MedicineService(db)
    medicine = await service.create_medicine(user_id=user_id, data=data)
    return success(medicine.model_dump(mode="json"))


@router.get("")
async def list_medicines(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MedicineService(db)
    medicines = await service.list_active(user_id=user_id, limit=limit, offset=offset)
    return success([medicine.model_dump(mode="json") for medicine in medicines])


@router.get("/upcoming")
async def get_upcoming(
    within_minutes: int = Query(default=30, ge=1, le=720),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MedicineService(db)
    reminders = await service.get_upcoming(user_id=user_id, within_minutes=within_minutes)
    return success([item.model_dump() for item in reminders])


@router.get("/adherence")
async def get_adherence(
    days: int = Query(default=30, ge=1, le=3650),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MedicineService(db)
    stats = await service.get_adherence_stats(user_id=user_id, days=days)
    return success(stats.model_dump())


@router.get("/refills")
async def get_refills(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MedicineService(db)
    refill_list = await service.check_refills(user_id=user_id)
    return success([medicine.model_dump(mode="json") for medicine in refill_list])


@router.get("/{medicine_id}")
async def get_medicine(
    medicine_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MedicineService(db)
    medicine = await service.get_medicine(user_id=user_id, medicine_id=medicine_id)
    return success(medicine.model_dump(mode="json"))


@router.patch("/{medicine_id}")
async def update_medicine(
    medicine_id: uuid.UUID,
    data: MedicineUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MedicineService(db)
    medicine = await service.update_medicine(
        user_id=user_id,
        medicine_id=medicine_id,
        data=data,
    )
    return success(medicine.model_dump(mode="json"))


@router.delete("/{medicine_id}")
async def delete_medicine(
    medicine_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MedicineService(db)
    await service.delete_medicine(user_id=user_id, medicine_id=medicine_id)
    return success({"deleted": True})


@router.post("/{medicine_id}/log")
async def log_dose(
    medicine_id: uuid.UUID,
    data: MedicineLogCreate,
    log_date: date | None = Query(default=None),
    scheduled_time: time | None = Query(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MedicineService(db)
    resolved_log_date = log_date or date.today()
    resolved_scheduled_time = scheduled_time or datetime.now(UTC).time().replace(microsecond=0)

    log = await service.log_dose(
        user_id=user_id,
        medicine_id=medicine_id,
        log_date=resolved_log_date,
        scheduled_time=resolved_scheduled_time,
        taken=data.taken,
        skipped=data.skipped,
        skip_reason=data.skip_reason,
    )
    return success(log.model_dump(mode="json"))

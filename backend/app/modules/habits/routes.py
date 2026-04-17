"""
WILLIAM OS — Habits Routes
Habit CRUD, daily check-ins, and procrastination detection endpoints.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.habits.schemas import (
    HabitCheckInCreate,
    HabitCreate,
    HabitUpdate,
    ProcrastinationDetectRequest,
)
from app.modules.habits.service import HabitsService
from app.shared.types import success

router = APIRouter(prefix="/habits", tags=["Habits"])


@router.post("", status_code=201)
async def create_habit(
    data: HabitCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = HabitsService(db)
    habit = await service.create_habit(user_id, data)
    return success(habit.model_dump(mode="json"))


@router.get("")
async def list_habits(
    active_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = HabitsService(db)
    habits = await service.list_habits(
        user_id,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return success([habit.model_dump(mode="json") for habit in habits])


@router.get("/check-ins/{target_date}")
async def get_daily_check_ins(
    target_date: date,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = HabitsService(db)
    check_ins = await service.get_daily_check_ins(user_id, target_date)
    return success([check_in.model_dump(mode="json") for check_in in check_ins])


@router.post("/procrastination/detect")
async def detect_procrastination(
    data: ProcrastinationDetectRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = HabitsService(db)
    signal = await service.detect_procrastination(
        user_id=user_id,
        target_date=data.target_date,
        threshold_minutes=data.threshold_minutes,
        missed_habit_threshold=data.missed_habit_threshold,
    )
    return success(signal.model_dump(mode="json") if signal else None)


@router.get("/{habit_id}")
async def get_habit(
    habit_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = HabitsService(db)
    habit = await service.get_habit(user_id, habit_id)
    return success(habit.model_dump(mode="json"))


@router.patch("/{habit_id}")
async def update_habit(
    habit_id: uuid.UUID,
    data: HabitUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = HabitsService(db)
    habit = await service.update_habit(user_id, habit_id, data)
    return success(habit.model_dump(mode="json"))


@router.delete("/{habit_id}")
async def delete_habit(
    habit_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = HabitsService(db)
    await service.delete_habit(user_id, habit_id)
    return success({"deleted": True})


@router.post("/{habit_id}/check-in")
async def check_in_habit(
    habit_id: uuid.UUID,
    data: HabitCheckInCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = HabitsService(db)
    check_in = await service.check_in_habit(user_id, habit_id, data)
    return success(check_in.model_dump(mode="json"))

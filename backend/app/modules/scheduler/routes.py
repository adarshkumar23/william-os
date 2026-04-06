"""
WILLIAM OS — Scheduler Routes
Schedule generation, retrieval, block management, rescheduling.
"""

from __future__ import annotations

import uuid
from datetime import date

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.scheduler.schemas import (
    BlockCreate,
    BlockUpdate,
    DayScoreUpdate,
    RescheduleRequest,
    ScheduleGenerateRequest,
)
from app.modules.scheduler.service import SchedulerService
from app.shared.types import success
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/schedule", tags=["Scheduler"])


@router.post("/generate")
async def generate_plan(
    request: ScheduleGenerateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SchedulerService(db)
    plan = await service.generate_daily_plan(user_id, request)
    return success(plan.model_dump(mode="json"))


@router.get("/today")
async def get_today(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SchedulerService(db)
    plan = await service.get_today(user_id)
    return success(plan.model_dump(mode="json"))


@router.get("/{plan_date}")
async def get_plan(
    plan_date: date,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SchedulerService(db)
    plan = await service.get_plan(user_id, plan_date)
    return success(plan.model_dump(mode="json"))


@router.post("/{plan_date}/blocks")
async def add_block(
    plan_date: date,
    data: BlockCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SchedulerService(db)
    plan = await service.add_block(user_id, plan_date, data)
    return success(plan.model_dump(mode="json"))


@router.patch("/blocks/{block_id}")
async def update_block(
    block_id: uuid.UUID,
    data: BlockUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SchedulerService(db)
    plan = await service.update_block(user_id, block_id, data)
    return success(plan.model_dump(mode="json"))


@router.post("/blocks/{block_id}/start")
async def start_block(
    block_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SchedulerService(db)
    plan = await service.start_block(user_id, block_id)
    return success(plan.model_dump(mode="json"))


@router.post("/{plan_date}/reschedule")
async def reschedule(
    plan_date: date,
    request: RescheduleRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SchedulerService(db)
    plan = await service.reschedule(user_id, plan_date, request)
    return success(plan.model_dump(mode="json"))


@router.post("/{plan_date}/optimize")
async def optimize_by_energy(
    plan_date: date,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SchedulerService(db)
    plan = await service.optimize_schedule_by_energy(user_id=user_id, plan_date=plan_date)
    return success(plan.model_dump(mode="json"))

"""
WILLIAM OS — Sleep Routes
Sleep optimizer endpoints for logging, debt, recommendations, and analysis.
"""

from __future__ import annotations

import uuid
from datetime import date

import structlog
from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.sleep.schemas import SleepRecordCreate
from app.modules.sleep.service import SleepService
from app.shared.types import success
from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sleep", tags=["Sleep Optimizer"])


@router.post("/log", status_code=201)
async def log_sleep(
    data: SleepRecordCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SleepService(db)
    record = await service.log_sleep(user_id=user_id, data=data)
    return success(record.model_dump(mode="json"))


@router.get("/history")
async def get_sleep_history(
    days: int = Query(default=30, ge=1, le=3650),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SleepService(db)
    history = await service.get_sleep_history(
        user_id=user_id,
        days=days,
        limit=limit,
        offset=offset,
    )
    return success([item.model_dump(mode="json") for item in history])


@router.get("/stats")
async def get_sleep_stats(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SleepService(db)
    stats = await service.get_sleep_stats(user_id=user_id)
    return success(stats.model_dump(mode="json"))


@router.get("/debt")
async def get_sleep_debt(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SleepService(db)
    debt = await service.calculate_sleep_debt(user_id=user_id)
    return success(debt.model_dump(mode="json"))


@router.post("/recommendation/generate")
async def generate_recommendation(
    target_date: date | None = Query(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SleepService(db)
    resolved_date = target_date or date.today()
    recommendation = await service.generate_recommendation(user_id=user_id, for_date=resolved_date)
    return success(recommendation.model_dump(mode="json"))


@router.get("/recommendation/{target_date}")
async def get_recommendation(
    target_date: date,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SleepService(db)
    recommendation = await service.get_recommendation(
        user_id=user_id,
        recommendation_date=target_date,
    )
    return success(recommendation.model_dump(mode="json"))


@router.patch("/recommendation/{recommendation_id}/followed")
async def mark_recommendation_followed(
    recommendation_id: uuid.UUID,
    payload: dict = Body(default_factory=dict),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SleepService(db)
    followed = bool(payload.get("followed", True))
    recommendation = await service.mark_recommendation_followed(
        user_id=user_id,
        recommendation_id=recommendation_id,
        followed=followed,
    )
    return success(recommendation.model_dump(mode="json"))


@router.post("/analyze")
async def analyze_sleep(
    days: int = Query(default=90, ge=7, le=3650),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SleepService(db)
    analysis = await service.analyze_sleep_patterns(user_id=user_id, days=days)
    return success(analysis.model_dump(mode="json"))

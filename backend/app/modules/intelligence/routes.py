"""
WILLIAM OS — Intelligence Routes
Cross-module signal and adjustment endpoints.
"""

from __future__ import annotations

import uuid

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.intelligence.schemas import CrossModuleRuleCreate
from app.modules.intelligence.service import IntelligenceService, LifeScoreService
from app.shared.types import success
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/intelligence", tags=["Cross-Module Intelligence"])


@router.get("/signals")
async def get_signals(
    source_module: str | None = Query(default=None),
    signal_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = IntelligenceService(db)
    signals = await service.list_signals(
        user_id=user_id,
        source_module=source_module,
        signal_type=signal_type,
        limit=limit,
        offset=offset,
    )
    return success([item.model_dump(mode="json") for item in signals])


@router.get("/adjustments")
async def get_adjustments(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = IntelligenceService(db)
    await service.collect_signals(user_id=user_id)
    adjustments = await service.get_active_adjustments(user_id=user_id)
    return success(adjustments.model_dump(mode="json"))


@router.post("/rules", status_code=201)
async def create_rule(
    payload: CrossModuleRuleCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ = user_id
    service = IntelligenceService(db)
    rule = await service.create_rule(payload)
    return success(rule.model_dump(mode="json"))


@router.get("/life-score")
async def get_life_score(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = LifeScoreService(db)
    score = await service.get_latest_score(user_id=user_id)
    return success(score.model_dump(mode="json"))


@router.get("/life-score/history")
async def get_life_score_history(
    days: int = Query(default=30, ge=1, le=365),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = LifeScoreService(db)
    history = await service.get_score_history(user_id=user_id, days=days)
    return success([item.model_dump(mode="json") for item in history])

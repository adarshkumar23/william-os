"""
WILLIAM OS — Intelligence Routes
Cross-module signal and adjustment endpoints.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.fitness.service import FitnessService
from app.modules.intelligence.schemas import AskTimelineRequest, CrossModuleRuleCreate
from app.modules.intelligence.service import IntelligenceService, LifeScoreService
from app.modules.intelligence.warnings_service import PredictiveWarningService
from app.shared.types import success

router = APIRouter(prefix="/intelligence", tags=["Cross-Module Intelligence"])


@router.post("/signals/collect")
async def collect_signals(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = IntelligenceService(db)
    signals = await service.collect_signals(user_id=user_id)
    return success([item.model_dump(mode="json") for item in signals])


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


@router.get("/energy-forecast")
async def get_intelligence_energy_forecast(
    target_date: date | None = Query(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = FitnessService(db)
    resolved_date = target_date or date.today()
    forecast = await service.get_energy_forecast(user_id=user_id, forecast_date=resolved_date)
    if forecast is None:
        forecast = await service.generate_energy_forecast(
            user_id=user_id,
            forecast_date=resolved_date,
        )
    return success(forecast.model_dump(mode="json"))


@router.get("/warnings")
async def get_predictive_warnings(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PredictiveWarningService(db)
    warnings = await service.get_active_warnings(user_id=user_id)
    return success([item.model_dump(mode="json") for item in warnings])


@router.post("/warnings/scan")
async def scan_predictive_warnings(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PredictiveWarningService(db)
    warnings = await service.scan_user(user_id=user_id)
    return success([item.model_dump(mode="json") for item in warnings])


@router.post("/scan")
async def scan_predictive_warnings_alias(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PredictiveWarningService(db)
    warnings = await service.scan_user(user_id=user_id)
    return success([item.model_dump(mode="json") for item in warnings])


@router.patch("/warnings/{warning_id}/resolve")
async def resolve_predictive_warning(
    warning_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PredictiveWarningService(db)
    warning = await service.resolve_warning(user_id=user_id, warning_id=warning_id)
    return success(warning.model_dump(mode="json"))


@router.get("/burnout/score")
async def get_burnout_score(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PredictiveWarningService(db)
    payload = await service.get_burnout_score(user_id=user_id)
    return success(payload)


@router.post("/burnout/intervene")
async def intervene_burnout(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PredictiveWarningService(db)
    payload = await service.intervene_burnout(user_id=user_id)
    return success(payload)


@router.get("/trends")
async def get_intelligence_trends(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PredictiveWarningService(db)
    payload = await service.get_trends(user_id=user_id)
    return success(payload)


@router.post("/refresh")
async def refresh_intelligence(
    scan_warnings: bool = Query(default=False),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = PredictiveWarningService(db)
    await service.invalidate_cache(user_id=user_id)

    burnout = await service.get_burnout_score(user_id=user_id, force_refresh=True)
    trends = await service.get_trends(user_id=user_id, force_refresh=True)
    warnings = (
        await service.scan_user(user_id=user_id)
        if scan_warnings
        else await service.get_active_warnings(user_id=user_id)
    )

    payload = {
        "burnout": burnout,
        "trends": trends,
        "warnings": [item.model_dump(mode="json") for item in warnings],
        "scanned": scan_warnings,
    }
    return success(payload)


@router.get("/timeline")
async def get_timeline(
    days: int = Query(default=90, ge=7, le=365),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = IntelligenceService(db)
    events = await service.get_timeline(user_id=user_id, days=days)
    return success([item.model_dump(mode="json") for item in events])


@router.post("/ask-timeline")
async def ask_timeline(
    payload: AskTimelineRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = IntelligenceService(db)
    response = await service.ask_timeline(user_id=user_id, question=payload.question)
    return success(response)


@router.post("/timeline/ask")
async def ask_timeline_alias(
    payload: AskTimelineRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = IntelligenceService(db)
    response = await service.ask_timeline(user_id=user_id, question=payload.question)
    return success(response)

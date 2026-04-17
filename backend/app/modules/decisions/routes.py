"""
WILLIAM OS — Decisions Routes
Decision assistant endpoints for analysis and outcomes.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.decisions.schemas import DecisionChoose, DecisionCreate, DecisionOutcome
from app.modules.decisions.service import DecisionService
from app.shared.types import success

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/decisions", tags=["Decision Assistant"])


@router.post("", status_code=201)
async def create_decision(
    data: DecisionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = DecisionService(db)
    decision = await service.create_decision(user_id=user_id, data=data)
    return success(decision.model_dump(mode="json"))


@router.get("")
async def list_decisions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = DecisionService(db)
    rows = await service.list_decisions(user_id=user_id, limit=limit, offset=offset)
    return success([item.model_dump(mode="json") for item in rows])


@router.patch("/{decision_id}")
async def update_decision(
    decision_id: uuid.UUID,
    data: DecisionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = DecisionService(db)
    decision = await service.update_decision(
        user_id=user_id,
        decision_id=decision_id,
        data=data,
    )
    return success(decision.model_dump(mode="json"))


@router.delete("/{decision_id}")
async def delete_decision(
    decision_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = DecisionService(db)
    await service.delete_decision(user_id=user_id, decision_id=decision_id)
    return success({"deleted": True})


@router.post("/{decision_id}/analyze")
async def analyze_decision(
    decision_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = DecisionService(db)
    analysis = await service.analyze_decision(user_id=user_id, decision_id=decision_id)
    return success(analysis.model_dump(mode="json"))


@router.post("/{decision_id}/choose")
async def choose_option(
    decision_id: uuid.UUID,
    data: DecisionChoose,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = DecisionService(db)
    decision = await service.choose_option(
        user_id=user_id,
        decision_id=decision_id,
        payload=data,
    )
    return success(decision.model_dump(mode="json"))


@router.post("/{decision_id}/outcome")
async def log_outcome(
    decision_id: uuid.UUID,
    data: DecisionOutcome,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = DecisionService(db)
    decision = await service.log_outcome(
        user_id=user_id,
        decision_id=decision_id,
        payload=data,
    )
    return success(decision.model_dump(mode="json"))


@router.get("/stats")
async def get_decision_stats(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = DecisionService(db)
    stats = await service.get_decision_quality(user_id=user_id)
    return success(stats.model_dump(mode="json"))


@router.get("/templates")
async def list_templates(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ = user_id
    service = DecisionService(db)
    templates = await service.list_templates()
    return success(templates)

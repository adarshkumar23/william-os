"""WILLIAM OS - Agent layer routes."""

from __future__ import annotations

import uuid

from app.core.database import get_db
from app.modules.agents.schemas import AgentActionLogResponse, AgentRecommendationLogResponse, AgentStatusResponse
from app.modules.agents.service import OrchestratorAgentService
from app.modules.auth.routes import get_current_user_id
from app.shared.types import success
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("/status")
async def get_agents_status(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = OrchestratorAgentService(db)
    rows = await service.list_statuses(user_id=user_id)
    payload = [AgentStatusResponse.model_validate(item).model_dump(mode="json") for item in rows]
    return success(payload)


@router.get("/recommendations")
async def get_agent_recommendations(
    limit: int = Query(default=20, ge=1, le=100),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = OrchestratorAgentService(db)
    rows = await service.list_recommendations(user_id=user_id, limit=limit)
    payload = [AgentRecommendationLogResponse.model_validate(item).model_dump(mode="json") for item in rows]
    return success(payload)


@router.post("/{name}/trigger")
async def trigger_agent(
    name: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = OrchestratorAgentService(db)
    result = await service.trigger_agent(user_id=user_id, agent_name=name)
    return success(result)

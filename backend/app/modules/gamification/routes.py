"""
WILLIAM OS — Gamification Routes
XP profile, history, and record endpoints.
"""

from __future__ import annotations

import uuid

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.gamification.service import GamificationService
from app.shared.types import success
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/gamification", tags=["Gamification"])


@router.get("/profile")
async def get_profile(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = GamificationService(db)
    profile = await service.get_profile(user_id=user_id)
    return success(profile.model_dump(mode="json"))


@router.get("/xp-history")
async def get_xp_history(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = GamificationService(db)
    rows = await service.list_xp_history(user_id=user_id, limit=limit, offset=offset)
    return success([item.model_dump(mode="json") for item in rows])


@router.get("/records")
async def get_records(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = GamificationService(db)
    rows = await service.list_records(user_id=user_id, limit=limit, offset=offset)
    return success([item.model_dump(mode="json") for item in rows])

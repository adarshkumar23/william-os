"""WILLIAM OS - Personal memory graph routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.memory.service import MemoryService
from app.shared.types import success

router = APIRouter(prefix="/memory", tags=["Memory Graph"])


@router.get("/profile")
async def get_memory_profile(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MemoryService(db)
    profile = await service.get_memory_profile(user_id=user_id)
    return success(profile.model_dump(mode="json"))


@router.get("/insights")
async def get_memory_insights(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MemoryService(db)
    insights = await service.list_insights(user_id=user_id)
    if not insights:
        generated = await service.generate_insights(user_id=user_id)
        return success([item.model_dump(mode="json") for item in generated])
    return success([item.model_dump(mode="json") for item in insights])


@router.delete("/{key}")
async def delete_memory_key(
    key: str,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MemoryService(db)
    deleted = await service.delete_memory(user_id=user_id, key=key)
    return success({"deleted": deleted, "key": key})

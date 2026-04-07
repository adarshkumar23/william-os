"""WILLIAM OS - Activity Feed Routes."""

from __future__ import annotations

import uuid

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.feed.service import ActivityFeedService
from app.shared.types import success
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/feed", tags=["Activity Feed"])


@router.get("")
async def get_feed(
    limit: int = Query(default=50, ge=1, le=100),
    before_cursor: str | None = Query(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ActivityFeedService(db)
    page = await service.get_feed(user_id=user_id, limit=limit, before_cursor=before_cursor)
    return success(page.model_dump(mode="json"))

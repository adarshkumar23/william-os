"""
WILLIAM OS — Morning Briefing Routes
Unified daily briefing retrieval and delivery endpoints.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.briefing.service import MorningBriefingService
from app.shared.types import success

router = APIRouter(prefix="/briefing", tags=["Morning Briefing"])


@router.get("/today")
async def get_today_briefing(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MorningBriefingService(db)
    briefing = await service.assemble_briefing(user_id=user_id)
    return success(briefing.model_dump(mode="json"))


@router.post("/send-now")
async def send_now(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MorningBriefingService(db)
    sent = await service.send_briefing(user_id=user_id)
    return success(sent.model_dump(mode="json"))


@router.get("/weekly-review")
async def get_weekly_review(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MorningBriefingService(db)
    review = await service.get_weekly_review(user_id=user_id)
    return success(review.model_dump(mode="json"))

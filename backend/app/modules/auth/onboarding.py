"""WILLIAM OS - Auth Onboarding Routes"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.auth.service import AuthService
from app.shared.types import success

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.modules.auth.schemas import OnboardingCompleteRequest

router = APIRouter(prefix="/auth/onboarding", tags=["Authentication"])


@router.get("/status")
async def onboarding_status(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    status = await service.get_onboarding_status(user_id)
    return success(status.model_dump(mode="json"))


@router.post("/complete")
async def complete_onboarding(
    data: OnboardingCompleteRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    payload = await service.complete_onboarding(user_id=user_id, data=data)
    return success(payload)

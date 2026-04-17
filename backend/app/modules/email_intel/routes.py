"""
WILLIAM OS — Email Intelligence Routes
Account linking, sync, summary retrieval, and morning briefing endpoints.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.email_intel.schemas import EmailAccountCreate
from app.modules.email_intel.service import EmailIntelService
from app.shared.types import success

router = APIRouter(prefix="/email", tags=["Email Intelligence"])


@router.post("/connect", status_code=201)
async def connect_account(
    data: EmailAccountCreate,
    oauth_token: str = Query(min_length=1),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = EmailIntelService(db)
    account = await service.connect_account(
        user_id=user_id,
        provider=data.provider,
        email_address=data.email_address,
        oauth_token=oauth_token,
    )
    return success(account.model_dump(mode="json"))


@router.get("/accounts")
async def list_accounts(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = EmailIntelService(db)
    accounts = await service.list_accounts(user_id=user_id)
    return success([account.model_dump(mode="json") for account in accounts])


@router.delete("/accounts/{account_id}")
async def disconnect_account(
    account_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = EmailIntelService(db)
    await service.disconnect_account(user_id=user_id, account_id=account_id)
    return success({"deleted": True})


@router.post("/sync")
async def sync_emails(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = EmailIntelService(db)
    summary = await service.sync_emails(user_id=user_id)
    return success(summary.model_dump(mode="json"))


@router.get("/summary")
async def get_summary(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = EmailIntelService(db)
    summary = await service.get_latest_summary(user_id=user_id)
    return success(summary.model_dump(mode="json") if summary else None)


@router.get("/briefing")
async def get_briefing(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = EmailIntelService(db)
    briefing = await service.build_morning_briefing(user_id=user_id)
    return success(briefing.model_dump(mode="json"))

"""
WILLIAM OS — Messaging Routes
Telegram account management and notification operations.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.messaging.bot import telegram_bot_handler
from app.modules.messaging.schemas import NotificationPayload, TelegramLinkRequest
from app.modules.messaging.service import MessagingService
from app.shared.types import success

router = APIRouter(prefix="/messaging", tags=["Messaging"])


@router.post("/telegram/link", status_code=201)
async def link_telegram(
    data: TelegramLinkRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MessagingService(db)
    linked = await service.link_telegram(
        user_id=user_id,
        chat_id=data.telegram_chat_id,
        username=data.telegram_username,
    )
    return success(linked.model_dump(mode="json"))


@router.delete("/telegram/link")
async def unlink_telegram(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MessagingService(db)
    await service.unlink_telegram(user_id=user_id)
    return success({"unlinked": True})


@router.get("/telegram/status")
async def telegram_status(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MessagingService(db)
    linked = await service.get_telegram_user(user_id=user_id)
    return success(linked.model_dump(mode="json") if linked else None)


@router.post("/telegram/webhook")
async def telegram_webhook(
    payload: dict = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await telegram_bot_handler.handle_webhook_update(payload=payload, db=db)
    return success({"processed": True})


@router.post("/send")
async def send_notification(
    payload: NotificationPayload,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MessagingService(db)
    sent = await service.send_notification(user_id=user_id, payload=payload)
    return success(sent.model_dump(mode="json"))


@router.get("/history")
async def notification_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MessagingService(db)
    history = await service.get_notification_history(
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    return success([item.model_dump(mode="json") for item in history])

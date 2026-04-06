"""
WILLIAM OS — Messaging Schemas
Request/response models for Telegram linkage and outbound notifications.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TelegramLinkRequest(BaseModel):
    telegram_chat_id: int
    telegram_username: str = Field(min_length=1, max_length=100)


class TelegramLinkResponse(BaseModel):
    id: UUID
    user_id: UUID
    telegram_chat_id: int | None
    telegram_username: str | None
    is_verified: bool
    notification_preferences: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationPayload(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    notification_type: str = Field(min_length=1, max_length=50)
    data: dict = Field(default_factory=dict)


class NotificationLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    channel: str
    notification_type: str
    payload: dict
    sent_at: datetime
    delivered: bool
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
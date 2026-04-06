"""
WILLIAM OS — Messaging Service Tests
Unit tests for Telegram linking and notification logging behavior.
"""

from __future__ import annotations

import pytest
from app.modules.messaging.schemas import NotificationPayload
from app.modules.messaging.service import MessagingService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_link_and_unlink_telegram(db_session: AsyncSession, test_user):
    service = MessagingService(db_session)

    linked = await service.link_telegram(
        user_id=test_user.id,
        chat_id=123456789,
        username="william_user",
    )
    assert linked.is_verified is True
    assert linked.telegram_chat_id == 123456789

    active_link = await service.get_telegram_user(test_user.id)
    assert active_link is not None

    await service.unlink_telegram(test_user.id)
    inactive_link = await service.get_telegram_user(test_user.id)
    assert inactive_link is None


@pytest.mark.asyncio
async def test_send_notification_logs_delivery(db_session: AsyncSession, test_user, monkeypatch):
    service = MessagingService(db_session)

    await service.link_telegram(
        user_id=test_user.id,
        chat_id=999000111,
        username="notify_user",
    )

    async def _fake_send(chat_id: int, text: str):
        _ = (chat_id, text)
        return True, None

    monkeypatch.setattr(service, "_telegram_send_message", _fake_send)

    payload = NotificationPayload(
        title="Medicine reminder",
        body="Take Vitamin D at 09:00",
        notification_type="medicine_reminder",
        data={"medicine_name": "Vitamin D"},
    )

    sent = await service.send_notification(user_id=test_user.id, payload=payload)
    history = await service.get_notification_history(user_id=test_user.id, limit=10)

    assert sent.delivered is True
    assert sent.error is None
    assert sent.channel == "telegram"
    assert len(history) == 1
    assert history[0].notification_type == "medicine_reminder"


@pytest.mark.asyncio
async def test_send_notification_without_link_logs_failure(db_session: AsyncSession, test_user):
    service = MessagingService(db_session)
    payload = NotificationPayload(
        title="Briefing",
        body="Your morning briefing is ready",
        notification_type="briefing",
        data={},
    )

    sent = await service.send_notification(user_id=test_user.id, payload=payload)

    assert sent.delivered is False
    assert sent.error is not None
    assert "not linked" in sent.error.lower()
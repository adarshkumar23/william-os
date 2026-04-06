"""
WILLIAM OS — Messaging Service
Telegram linking and outbound notification delivery.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import structlog
from app.core.config import get_settings
from app.modules.messaging.models import NotificationLog, TelegramUser
from app.modules.messaging.schemas import (
    NotificationLogResponse,
    NotificationPayload,
    TelegramLinkResponse,
)
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class MessagingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def link_telegram(
        self,
        user_id: uuid.UUID,
        chat_id: int,
        username: str,
    ) -> TelegramLinkResponse:
        existing_for_chat = await self.db.execute(
            select(TelegramUser).where(TelegramUser.telegram_chat_id == chat_id)
        )
        chat_link = existing_for_chat.scalar_one_or_none()
        if chat_link and chat_link.user_id != user_id:
            chat_link.telegram_chat_id = None
            chat_link.telegram_username = None
            chat_link.is_verified = False

        existing_for_user = await self.db.execute(
            select(TelegramUser).where(TelegramUser.user_id == user_id)
        )
        user_link = existing_for_user.scalar_one_or_none()

        if user_link:
            user_link.telegram_chat_id = chat_id
            user_link.telegram_username = username
            user_link.is_verified = True
        else:
            user_link = TelegramUser(
                user_id=user_id,
                telegram_chat_id=chat_id,
                telegram_username=username,
                is_verified=True,
            )
            self.db.add(user_link)

        await self.db.flush()
        await self.db.refresh(user_link)

        logger.info(
            "telegram_linked",
            user_id=str(user_id),
            chat_id=chat_id,
            username=username,
        )
        return TelegramLinkResponse.model_validate(user_link)

    async def unlink_telegram(self, user_id: uuid.UUID) -> None:
        existing = await self.db.execute(
            select(TelegramUser).where(TelegramUser.user_id == user_id)
        )
        telegram_user = existing.scalar_one_or_none()
        if not telegram_user:
            return

        telegram_user.telegram_chat_id = None
        telegram_user.telegram_username = None
        telegram_user.is_verified = False
        await self.db.flush()

        logger.info("telegram_unlinked", user_id=str(user_id))

    async def get_telegram_user(self, user_id: uuid.UUID) -> TelegramLinkResponse | None:
        result = await self.db.execute(
            select(TelegramUser).where(
                and_(
                    TelegramUser.user_id == user_id,
                    TelegramUser.is_verified.is_(True),
                    TelegramUser.telegram_chat_id.is_not(None),
                )
            )
        )
        telegram_user = result.scalar_one_or_none()
        if telegram_user is None:
            return None
        return TelegramLinkResponse.model_validate(telegram_user)

    async def send_notification(
        self,
        user_id: uuid.UUID,
        payload: NotificationPayload,
    ) -> NotificationLogResponse:
        telegram_user = await self.get_telegram_user(user_id)

        delivered = False
        error_text: str | None = None
        if telegram_user is None or telegram_user.telegram_chat_id is None:
            error_text = "Telegram account not linked"
        else:
            delivered, error_text = await self._telegram_send_message(
                chat_id=telegram_user.telegram_chat_id,
                text=self._format_telegram_message(payload),
            )

        log = NotificationLog(
            user_id=user_id,
            channel="telegram",
            notification_type=payload.notification_type,
            payload=payload.model_dump(mode="json"),
            sent_at=datetime.now(UTC),
            delivered=delivered,
            error=error_text,
        )
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)

        logger.info(
            "notification_sent",
            user_id=str(user_id),
            notification_type=payload.notification_type,
            delivered=delivered,
            error=error_text,
        )
        return NotificationLogResponse.model_validate(log)

    async def send_morning_briefing(
        self,
        user_id: uuid.UUID,
        briefing_data: dict,
    ) -> NotificationLogResponse:
        top_priorities = briefing_data.get("top_priorities", [])
        schedule = briefing_data.get("schedule_summary", {})
        body = (
            f"Plan date: {schedule.get('plan_date', 'N/A')}\n"
            f"Blocks: {schedule.get('total_blocks', 0)}\n"
            f"Top priorities: {', '.join(top_priorities) if top_priorities else 'None'}"
        )
        payload = NotificationPayload(
            title="Morning briefing is ready",
            body=body,
            notification_type="briefing",
            data=briefing_data,
        )
        return await self.send_notification(user_id, payload)

    async def send_medicine_reminder(
        self,
        user_id: uuid.UUID,
        reminder_data: dict,
    ) -> NotificationLogResponse:
        payload = NotificationPayload(
            title="Medicine reminder",
            body=(
                f"{reminder_data.get('medicine_name', 'Medicine')} "
                f"{reminder_data.get('dosage', '')} "
                f"at {reminder_data.get('scheduled_time', 'soon')}"
            ).strip(),
            notification_type="medicine_reminder",
            data=reminder_data,
        )
        return await self.send_notification(user_id, payload)

    async def send_procrastination_alert(
        self,
        user_id: uuid.UUID,
        signal_data: dict,
    ) -> NotificationLogResponse:
        missed = signal_data.get("missed_habits", [])
        body = (
            f"Severity: {signal_data.get('severity', 'unknown')}\n"
            f"Missed habits: {', '.join(missed) if missed else 'None'}"
        )
        payload = NotificationPayload(
            title="Procrastination alert",
            body=body,
            notification_type="procrastination_alert",
            data=signal_data,
        )
        return await self.send_notification(user_id, payload)

    async def get_notification_history(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
    ) -> list[NotificationLogResponse]:
        bounded_limit = max(1, min(limit, 200))
        result = await self.db.execute(
            select(NotificationLog)
            .where(NotificationLog.user_id == user_id)
            .order_by(NotificationLog.sent_at.desc(), NotificationLog.created_at.desc())
            .limit(bounded_limit)
        )
        logs = result.scalars().all()
        return [NotificationLogResponse.model_validate(log) for log in logs]

    async def _telegram_send_message(self, chat_id: int, text: str) -> tuple[bool, str | None]:
        token = self.settings.telegram_bot_token.get_secret_value()
        if not token:
            return False, "telegram_bot_token is not configured"

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, json=payload)
            if response.status_code >= 400:
                return False, f"telegram_api_error:{response.status_code}"

            body = response.json()
            if not body.get("ok", False):
                return False, "telegram_api_not_ok"
            return True, None
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def _format_telegram_message(payload: NotificationPayload) -> str:
        if payload.title:
            return f"{payload.title}\n\n{payload.body}"
        return payload.body
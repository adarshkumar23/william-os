"""
WILLIAM OS — Telegram Bot Handler
Webhook command handling for messaging workflows.
"""

from __future__ import annotations

import uuid
from datetime import date

import httpx
import structlog
from app.core.config import get_settings
from app.core.security import create_access_token
from app.modules.habits.models import Habit
from app.modules.habits.schemas import HabitCheckInCreate
from app.modules.habits.service import HabitsService
from app.modules.journal.schemas import JournalCreate
from app.modules.journal.service import JournalService
from app.modules.messaging.models import TelegramUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import Application

logger = structlog.get_logger(__name__)


class TelegramBotHandler:
    def __init__(self) -> None:
        self.settings = get_settings()
        token = self.settings.telegram_bot_token.get_secret_value()
        self.application = Application.builder().token(token).build() if token else None

    async def handle_webhook_update(self, payload: dict, db: AsyncSession) -> None:
        if not self.application:
            logger.warning("telegram_bot_not_initialized")
            return

        update = Update.de_json(payload, self.application.bot)
        if update is None or update.effective_chat is None:
            return

        message = update.effective_message
        if message is None or not message.text:
            return

        command_line = message.text.strip()
        if not command_line.startswith("/"):
            return

        await self._dispatch_command(
            chat_id=update.effective_chat.id,
            command_line=command_line,
            db=db,
        )

    async def _dispatch_command(self, chat_id: int, command_line: str, db: AsyncSession) -> None:
        parts = command_line.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "/start":
            await self._send_telegram_message(
                chat_id,
                (
                    "Welcome to WILLIAM OS Bot.\n"
                    "Link your account from Settings or POST /api/v1/messaging/telegram/link "
                    "with this chat ID to enable notifications and commands."
                ),
            )
            return

        if command == "/help":
            await self._send_telegram_message(
                chat_id,
                "Available commands:\n"
                "/today\n"
                "/checkin {habit_name}\n"
                "/journal {passphrase}|{text}\n"
                "/help",
            )
            return

        user_id = await self._get_user_id_for_chat(chat_id, db)
        if user_id is None:
            await self._send_telegram_message(
                chat_id,
                "This Telegram chat is not linked. Link via /api/v1/messaging/telegram/link first.",
            )
            return

        if command == "/today":
            await self._handle_today(chat_id, user_id)
            return

        if command == "/checkin":
            await self._handle_checkin(chat_id, user_id, args, db)
            return

        if command == "/journal":
            await self._handle_journal(chat_id, user_id, args, db)
            return

        await self._send_telegram_message(chat_id, "Unknown command. Use /help.")

    async def _handle_today(self, chat_id: int, user_id: uuid.UUID) -> None:
        response = await self._call_internal_api(
            method="GET",
            path="/api/v1/schedule/today",
            user_id=user_id,
        )

        if not response.get("ok", False):
            await self._send_telegram_message(chat_id, "Could not fetch today's schedule yet.")
            return

        data = response.get("data") or {}
        blocks = data.get("blocks") or []
        lines = [f"Today's schedule ({data.get('plan_date', date.today().isoformat())})"]
        for block in blocks[:8]:
            lines.append(f"- {block.get('start_time', '--')} {block.get('title', 'Untitled')}")

        if not blocks:
            lines.append("No blocks scheduled yet.")

        await self._send_telegram_message(chat_id, "\n".join(lines))

    async def _handle_checkin(
        self,
        chat_id: int,
        user_id: uuid.UUID,
        habit_name: str,
        db: AsyncSession,
    ) -> None:
        normalized_name = habit_name.strip()
        if not normalized_name:
            await self._send_telegram_message(chat_id, "Usage: /checkin {habit_name}")
            return

        result = await db.execute(
            select(Habit).where(
                Habit.user_id == user_id,
                func.lower(Habit.name) == normalized_name.lower(),
                Habit.is_active.is_(True),
            )
        )
        habit = result.scalar_one_or_none()
        if habit is None:
            await self._send_telegram_message(chat_id, f"Habit not found: {normalized_name}")
            return

        service = HabitsService(db)
        check_in = await service.check_in_habit(
            user_id=user_id,
            habit_id=habit.id,
            data=HabitCheckInCreate(completed=True, skipped=False),
        )
        await self._send_telegram_message(
            chat_id,
            f"Checked in: {habit.name} for {check_in.check_date}",
        )

    async def _handle_journal(
        self,
        chat_id: int,
        user_id: uuid.UUID,
        content: str,
        db: AsyncSession,
    ) -> None:
        cleaned = content.strip()
        if not cleaned:
            await self._send_telegram_message(chat_id, "Usage: /journal {passphrase}|{text}")
            return

        if "|" not in cleaned:
            await self._send_telegram_message(
                chat_id,
                "Usage: /journal {passphrase}|{text}",
            )
            return

        passphrase, journal_text = (part.strip() for part in cleaned.split("|", maxsplit=1))
        if len(passphrase) < 8 or not journal_text:
            await self._send_telegram_message(
                chat_id,
                "Passphrase must be at least 8 chars. Usage: /journal {passphrase}|{text}",
            )
            return

        service = JournalService(db)
        entry = await service.create_entry(
            user_id=user_id,
            data=JournalCreate(
                content=journal_text,
                passphrase=passphrase,
                tags=["telegram"],
            ),
        )
        await self._send_telegram_message(chat_id, f"Journal entry saved ({entry.entry_date}).")

    async def _call_internal_api(
        self,
        method: str,
        path: str,
        user_id: uuid.UUID,
        json_body: dict | None = None,
    ) -> dict:
        token = create_access_token(user_id)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.request(
                    method,
                    f"{self.settings.base_url.rstrip('/')}{path}",
                    headers=headers,
                    json=json_body,
                )
            return response.json()
        except Exception as exc:
            logger.warning("telegram_internal_api_call_failed", error=str(exc), path=path)
            return {"ok": False, "error": str(exc), "data": None}

    async def _send_telegram_message(self, chat_id: int, text: str) -> None:
        token = self.settings.telegram_bot_token.get_secret_value()
        if not token:
            logger.warning("telegram_token_missing")
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                await client.post(url, json=payload)
        except Exception as exc:
            logger.warning("telegram_reply_send_failed", error=str(exc), chat_id=chat_id)

    async def _get_user_id_for_chat(self, chat_id: int, db: AsyncSession) -> uuid.UUID | None:
        result = await db.execute(
            select(TelegramUser).where(
                TelegramUser.telegram_chat_id == chat_id,
                TelegramUser.is_verified.is_(True),
            )
        )
        link = result.scalar_one_or_none()
        if link is None:
            return None
        return link.user_id


telegram_bot_handler = TelegramBotHandler()

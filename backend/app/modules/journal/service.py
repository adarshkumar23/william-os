"""
WILLIAM OS — Journal Vault Service
Encrypted journal entry creation, retrieval, listing, deletion, and AI summaries.
"""

from __future__ import annotations

import uuid
from datetime import date

import httpx
import structlog
from app.core.config import get_settings
from app.core.events import Event, EventType, event_bus
from app.core.security import decrypt_text, encrypt_text
from app.modules.journal.models import JournalEntry, JournalMood
from app.modules.journal.schemas import JournalCreate, JournalDecrypted, JournalMetadata
from app.shared.types import EncryptionError, NotFoundError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class JournalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def create_entry(self, user_id: uuid.UUID, data: JournalCreate) -> JournalMetadata:
        word_count = self._count_words(data.content)
        encrypted_content = encrypt_text(data.content, data.passphrase)

        entry = JournalEntry(
            user_id=user_id,
            entry_date=date.today(),
            encrypted_content=encrypted_content,
            mood=data.mood,
            tags=data.tags,
            word_count=word_count,
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)

        await event_bus.publish(
            Event(
                type=EventType.JOURNAL_ENTRY_CREATED,
                data={
                    "entry_id": str(entry.id),
                    "entry_date": str(entry.entry_date),
                    "word_count": word_count,
                },
                user_id=user_id,
            )
        )

        logger.info(
            "journal_entry_created",
            user_id=str(user_id),
            entry_id=str(entry.id),
            word_count=word_count,
        )
        return JournalMetadata.model_validate(entry)

    async def read_entry(
        self,
        user_id: uuid.UUID,
        entry_id: uuid.UUID,
        passphrase: str,
    ) -> JournalDecrypted:
        entry = await self._get_entry_for_user(user_id=user_id, entry_id=entry_id)

        try:
            content = decrypt_text(entry.encrypted_content, passphrase)
            summary = (
                decrypt_text(entry.encrypted_summary, passphrase)
                if entry.encrypted_summary is not None
                else None
            )
        except Exception as exc:
            raise EncryptionError() from exc

        metadata = JournalMetadata.model_validate(entry)
        return JournalDecrypted(**metadata.model_dump(), content=content, summary=summary)

    async def list_entries(
        self,
        user_id: uuid.UUID,
        date_from: date | None = None,
        date_to: date | None = None,
        mood_filter: JournalMood | None = None,
    ) -> list[JournalMetadata]:
        query = select(JournalEntry).where(JournalEntry.user_id == user_id)

        if date_from:
            query = query.where(JournalEntry.entry_date >= date_from)
        if date_to:
            query = query.where(JournalEntry.entry_date <= date_to)
        if mood_filter:
            query = query.where(JournalEntry.mood == mood_filter)

        query = query.order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
        result = await self.db.execute(query)
        entries = result.scalars().all()
        return [JournalMetadata.model_validate(entry) for entry in entries]

    async def delete_entry(self, entry_id: uuid.UUID, user_id: uuid.UUID) -> None:
        entry = await self._get_entry_for_user(user_id=user_id, entry_id=entry_id)
        await self.db.delete(entry)
        await self.db.flush()

        logger.info("journal_entry_deleted", user_id=str(user_id), entry_id=str(entry_id))

    async def generate_summary(
        self,
        user_id: uuid.UUID,
        entry_id: uuid.UUID,
        passphrase: str,
    ) -> JournalDecrypted:
        entry = await self._get_entry_for_user(user_id=user_id, entry_id=entry_id)

        try:
            content = decrypt_text(entry.encrypted_content, passphrase)
        except Exception as exc:
            raise EncryptionError() from exc

        summary = await self._summarize_content(content)
        entry.encrypted_summary = encrypt_text(summary, passphrase)
        await self.db.flush()
        await self.db.refresh(entry)

        metadata = JournalMetadata.model_validate(entry)
        return JournalDecrypted(**metadata.model_dump(), content=content, summary=summary)

    async def _get_entry_for_user(self, user_id: uuid.UUID, entry_id: uuid.UUID) -> JournalEntry:
        result = await self.db.execute(
            select(JournalEntry).where(
                and_(
                    JournalEntry.id == entry_id,
                    JournalEntry.user_id == user_id,
                )
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise NotFoundError("JournalEntry", str(entry_id))
        return entry

    async def _summarize_content(self, content: str) -> str:
        api_key = self.settings.openrouter_api_key.get_secret_value()
        if not api_key:
            return self._fallback_summary(content)

        payload = {
            "model": self.settings.openrouter_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are WILLIAM OS. Summarize a personal journal entry in 2-4 concise "
                        "sentences with neutral tone and include one actionable reflection prompt."
                    ),
                },
                {
                    "role": "user",
                    "content": content,
                },
            ],
            "temperature": 0.2,
            "max_tokens": 220,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.base_url,
            "X-Title": self.settings.app_name,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()

            data = response.json()
            summary = data["choices"][0]["message"]["content"].strip()
            if not summary:
                return self._fallback_summary(content)
            return summary
        except Exception as exc:
            logger.warning("journal_summary_generation_failed", error=str(exc))
            return self._fallback_summary(content)

    @staticmethod
    def _count_words(content: str) -> int:
        return len([word for word in content.split() if word.strip()])

    @staticmethod
    def _fallback_summary(content: str) -> str:
        words = [word for word in content.split() if word.strip()]
        if not words:
            return "No summary available."
        preview = " ".join(words[:60])
        if len(words) > 60:
            preview += "..."
        return f"Entry summary: {preview}"

"""
WILLIAM OS — Journal Vault Service
Encrypted journal entry creation, retrieval, listing, deletion, and AI summaries.
"""

from __future__ import annotations

import json
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from time import perf_counter
from typing import TYPE_CHECKING

import httpx
import redis.asyncio as redis
import structlog
from sqlalchemy import and_, select

from app.core.config import get_settings
from app.core.events import Event, EventType, event_bus
from app.core.metrics import observe_ai_call
from app.core.security import decrypt_api_secret, decrypt_text, encrypt_api_secret, encrypt_text
from app.modules.journal.models import JournalDraft, JournalEntry, JournalMood
from app.modules.journal.schemas import (
    JournalCreate,
    JournalDecrypted,
    JournalDraftResponse,
    JournalDraftUpsert,
    JournalMetadata,
)
from app.shared.types import EncryptionError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
logger = structlog.get_logger(__name__)

_JOURNAL_UNLOCK_TTL_MINUTES = 30
_journal_unlock_cache: dict[uuid.UUID, tuple[str, datetime, str]] = {}


class JournalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self._redis = redis.from_url(self.settings.redis_url, decode_responses=True)
        self._unlock_ttl_seconds = _JOURNAL_UNLOCK_TTL_MINUTES * 60

    async def create_entry(self, user_id: uuid.UUID, data: JournalCreate) -> JournalMetadata:
        word_count = self._count_words(data.content)
        passphrase = await self._resolve_passphrase(
            user_id=user_id,
            passphrase=data.passphrase,
            unlock_token=data.unlock_token,
        )
        encrypted_content = encrypt_text(data.content, passphrase)

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
        passphrase: str | None,
        unlock_token: str | None = None,
    ) -> JournalDecrypted:
        entry = await self._get_entry_for_user(user_id=user_id, entry_id=entry_id)
        resolved_passphrase = await self._resolve_passphrase(
            user_id=user_id,
            passphrase=passphrase,
            unlock_token=unlock_token,
        )

        try:
            content = decrypt_text(entry.encrypted_content, resolved_passphrase)
            summary = (
                decrypt_text(entry.encrypted_summary, resolved_passphrase)
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
        limit: int = 50,
        offset: int = 0,
    ) -> list[JournalMetadata]:
        query = select(JournalEntry).where(JournalEntry.user_id == user_id)

        if date_from:
            query = query.where(JournalEntry.entry_date >= date_from)
        if date_to:
            query = query.where(JournalEntry.entry_date <= date_to)
        if mood_filter:
            query = query.where(JournalEntry.mood == mood_filter)

        query = query.order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
        query = query.limit(limit).offset(offset)
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
        passphrase: str | None,
        unlock_token: str | None = None,
    ) -> JournalDecrypted:
        entry = await self._get_entry_for_user(user_id=user_id, entry_id=entry_id)
        resolved_passphrase = await self._resolve_passphrase(
            user_id=user_id,
            passphrase=passphrase,
            unlock_token=unlock_token,
        )

        try:
            content = decrypt_text(entry.encrypted_content, resolved_passphrase)
        except Exception as exc:
            raise EncryptionError() from exc

        summary = await self._summarize_content(content)
        entry.encrypted_summary = encrypt_text(summary, resolved_passphrase)
        await self.db.flush()
        await self.db.refresh(entry)

        metadata = JournalMetadata.model_validate(entry)
        return JournalDecrypted(**metadata.model_dump(), content=content, summary=summary)

    async def unlock(self, user_id: uuid.UUID, passphrase: str) -> tuple[datetime, str]:
        latest_result = await self.db.execute(
            select(JournalEntry.encrypted_content)
            .where(JournalEntry.user_id == user_id)
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
            .limit(1)
        )
        latest_encrypted = latest_result.scalar_one_or_none()

        try:
            if latest_encrypted is not None:
                decrypt_text(latest_encrypted, passphrase)
            else:
                probe = encrypt_text("unlock-probe", passphrase)
                decrypt_text(probe, passphrase)
        except Exception as exc:
            raise EncryptionError() from exc

        session_token = secrets.token_urlsafe(24)
        unlock_expires_at = datetime.now(UTC) + timedelta(minutes=_JOURNAL_UNLOCK_TTL_MINUTES)
        _journal_unlock_cache[user_id] = (passphrase, unlock_expires_at, session_token)
        await self._cache_unlock_session(
            user_id=user_id,
            session_token=session_token,
            passphrase=passphrase,
        )
        return unlock_expires_at, session_token

    async def upsert_draft(
        self,
        user_id: uuid.UUID,
        data: JournalDraftUpsert,
    ) -> JournalDraftResponse:
        resolved_passphrase = await self._resolve_passphrase(
            user_id=user_id,
            passphrase=data.passphrase,
            unlock_token=data.unlock_token,
        )
        encrypted_content = encrypt_text(data.content or "", resolved_passphrase)

        result = await self.db.execute(
            select(JournalDraft).where(JournalDraft.user_id == user_id).limit(1)
        )
        draft = result.scalar_one_or_none()
        if draft is None:
            draft = JournalDraft(
                user_id=user_id,
                encrypted_content=encrypted_content,
                mood=data.mood,
                tags=data.tags,
            )
            self.db.add(draft)
        else:
            draft.encrypted_content = encrypted_content
            draft.mood = data.mood
            draft.tags = data.tags

        await self.db.flush()
        await self.db.refresh(draft)
        return JournalDraftResponse(
            content=data.content or "",
            mood=draft.mood,
            tags=draft.tags or [],
            updated_at=draft.updated_at,
        )

    async def get_draft(
        self,
        user_id: uuid.UUID,
        passphrase: str | None,
        unlock_token: str | None = None,
    ) -> JournalDraftResponse | None:
        result = await self.db.execute(
            select(JournalDraft).where(JournalDraft.user_id == user_id).limit(1)
        )
        draft = result.scalar_one_or_none()
        if draft is None:
            return None

        resolved_passphrase = await self._resolve_passphrase(
            user_id=user_id,
            passphrase=passphrase,
            unlock_token=unlock_token,
        )
        try:
            content = decrypt_text(draft.encrypted_content, resolved_passphrase)
        except Exception as exc:
            raise EncryptionError() from exc

        return JournalDraftResponse(
            content=content,
            mood=draft.mood,
            tags=draft.tags or [],
            updated_at=draft.updated_at,
        )

    async def delete_draft(self, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(JournalDraft).where(JournalDraft.user_id == user_id).limit(1)
        )
        draft = result.scalar_one_or_none()
        if draft is None:
            return False

        await self.db.delete(draft)
        await self.db.flush()
        return True

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

    async def _resolve_passphrase(
        self,
        user_id: uuid.UUID,
        passphrase: str | None,
        unlock_token: str | None = None,
    ) -> str:
        provided = (passphrase or "").strip()
        if provided:
            return provided

        cached = await self._get_cached_passphrase(user_id=user_id, unlock_token=unlock_token)
        if cached:
            return cached

        raise EncryptionError("Journal is locked. Provide a passphrase or unlock first.")

    async def _get_cached_passphrase(
        self,
        user_id: uuid.UUID,
        unlock_token: str | None = None,
    ) -> str | None:
        requested_token = (unlock_token or "").strip()

        if requested_token:
            cached = await self._read_unlock_session(user_id=user_id, session_token=requested_token)
            if cached:
                return cached
        else:
            latest_token = await self._get_latest_unlock_token(user_id=user_id)
            if latest_token:
                cached = await self._read_unlock_session(
                    user_id=user_id, session_token=latest_token
                )
                if cached:
                    return cached

        local_cached = _journal_unlock_cache.get(user_id)
        if not local_cached:
            return None

        passphrase, expires_at, token = local_cached
        if expires_at <= datetime.now(UTC):
            _journal_unlock_cache.pop(user_id, None)
            return None

        if requested_token and requested_token != token:
            return None
        return passphrase

    async def _cache_unlock_session(
        self,
        user_id: uuid.UUID,
        session_token: str,
        passphrase: str,
    ) -> None:
        payload = json.dumps({"passphrase": encrypt_api_secret(passphrase)})
        try:
            await self._redis.setex(
                self._unlock_cache_key(user_id=user_id, session_token=session_token),
                self._unlock_ttl_seconds,
                payload,
            )
            await self._redis.setex(
                self._unlock_latest_key(user_id=user_id),
                self._unlock_ttl_seconds,
                session_token,
            )
        except Exception:
            return

    async def _read_unlock_session(self, user_id: uuid.UUID, session_token: str) -> str | None:
        try:
            raw = await self._redis.get(
                self._unlock_cache_key(user_id=user_id, session_token=session_token)
            )
            if not raw:
                return None
            parsed = json.loads(raw)
            encrypted = parsed.get("passphrase") if isinstance(parsed, dict) else None
            if not isinstance(encrypted, str) or not encrypted:
                return None
            return decrypt_api_secret(encrypted)
        except Exception:
            return None

    async def _get_latest_unlock_token(self, user_id: uuid.UUID) -> str | None:
        try:
            raw = await self._redis.get(self._unlock_latest_key(user_id=user_id))
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
            return None
        except Exception:
            return None

    @staticmethod
    def _unlock_cache_key(user_id: uuid.UUID, session_token: str) -> str:
        return f"journal:unlock:{user_id}:{session_token}"

    @staticmethod
    def _unlock_latest_key(user_id: uuid.UUID) -> str:
        return f"journal:unlock:latest:{user_id}"

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
                    # M15: wrap in delimiters so user prose cannot escape the content role
                    "content": f"<journal_entry>{content}</journal_entry>",
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

        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()

            data = response.json()
            observe_ai_call(provider="openrouter", duration_seconds=perf_counter() - started)
            summary = data["choices"][0]["message"]["content"].strip()
            if not summary:
                return self._fallback_summary(content)
            return summary
        except Exception as exc:
            observe_ai_call(provider="openrouter", duration_seconds=perf_counter() - started)
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

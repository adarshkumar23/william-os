"""
WILLIAM OS — Journal Vault Schemas
Request/response models for encrypted journal operations.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.journal.models import JournalMood


class JournalCreate(BaseModel):
    content: str = Field(min_length=1)
    passphrase: str | None = Field(default=None, min_length=4, max_length=256)
    unlock_token: str | None = Field(default=None, min_length=8, max_length=255)
    mood: JournalMood | None = None
    tags: list[str] = []


class JournalRead(BaseModel):
    passphrase: str | None = Field(default=None, min_length=4, max_length=256)
    unlock_token: str | None = Field(default=None, min_length=8, max_length=255)


class JournalUnlockRequest(BaseModel):
    passphrase: str = Field(min_length=4, max_length=256)


class JournalUnlockResponse(BaseModel):
    unlocked: bool
    unlock_expires_at: datetime
    session_token: str


class JournalDraftUpsert(BaseModel):
    content: str = Field(default="", max_length=20000)
    passphrase: str | None = Field(default=None, min_length=4, max_length=256)
    unlock_token: str | None = Field(default=None, min_length=8, max_length=255)
    mood: JournalMood | None = None
    tags: list[str] = []


class JournalDraftResponse(BaseModel):
    content: str
    mood: JournalMood | None
    tags: list[str]
    updated_at: datetime


class JournalMetadata(BaseModel):
    id: UUID
    entry_date: date
    mood: JournalMood | None
    tags: list[str]
    word_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class JournalDecrypted(JournalMetadata):
    content: str
    summary: str | None = None

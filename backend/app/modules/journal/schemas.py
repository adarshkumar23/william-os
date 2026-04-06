"""
WILLIAM OS — Journal Vault Schemas
Request/response models for encrypted journal operations.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from app.modules.journal.models import JournalMood
from pydantic import BaseModel, Field


class JournalCreate(BaseModel):
    content: str = Field(min_length=1)
    passphrase: str = Field(min_length=4, max_length=256)
    mood: JournalMood | None = None
    tags: list[str] = []


class JournalRead(BaseModel):
    passphrase: str = Field(min_length=4, max_length=256)


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

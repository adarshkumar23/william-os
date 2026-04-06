"""
WILLIAM OS — Email Intelligence Schemas
Request/response models for account linking, summaries, and morning briefing.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EmailAccountCreate(BaseModel):
    provider: str = Field(min_length=2, max_length=50)
    email_address: str = Field(min_length=5, max_length=255)


class EmailAccountResponse(BaseModel):
    id: UUID
    user_id: UUID
    provider: str
    email_address: str
    last_sync_at: datetime | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class EmailSummaryResponse(BaseModel):
    id: UUID
    user_id: UUID
    summary_date: date
    email_count: int
    summary_text: str
    priority_emails: list[dict]
    action_items: list[str]
    generated_by: str
    generation_latency_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MorningBriefing(BaseModel):
    schedule_summary: dict
    email_summary: dict | None
    weather: dict | None
    top_priorities: list[str]

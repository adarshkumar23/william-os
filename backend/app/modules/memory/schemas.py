"""WILLIAM OS - Personal memory graph schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.memory.models import MemoryType
from pydantic import BaseModel


class UserMemoryResponse(BaseModel):
    id: UUID
    user_id: UUID
    memory_type: MemoryType
    key: str
    value: dict
    confidence: float
    last_updated: datetime
    source_modules: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryInsightResponse(BaseModel):
    id: UUID
    user_id: UUID
    insight: str
    supporting_evidence: dict
    generated_at: datetime
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryProfileResponse(BaseModel):
    memories: list[UserMemoryResponse]
    insights: list[MemoryInsightResponse]

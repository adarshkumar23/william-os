"""
WILLIAM OS — Chat Schemas
Request/response models for chat sessions and messages.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.chat.models import AgentName, MessageRole
from pydantic import BaseModel, Field


# ── Request Schemas ──────────────────────────────────────────────

class ChatSessionCreate(BaseModel):
    agent_name: AgentName = AgentName.OS
    title: str = Field(default="New Chat", max_length=200)


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


# ── Response Schemas ─────────────────────────────────────────────

class ChatMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    user_id: UUID
    role: MessageRole
    content: str
    actions_taken: list | None = None
    extra_metadata: dict | None = Field(default=None)
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class ChatSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    agent_name: AgentName
    title: str
    created_at: datetime
    updated_at: datetime
    last_message: ChatMessageResponse | None = None

    model_config = {"from_attributes": True}


class ChatSessionListItem(BaseModel):
    id: UUID
    user_id: UUID
    agent_name: AgentName
    title: str
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None = None

    model_config = {"from_attributes": True}

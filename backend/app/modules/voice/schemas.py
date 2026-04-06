"""
WILLIAM OS — Voice Schemas
Request and response models for voice command processing.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class VoiceCommandRequest(BaseModel):
    text: str = Field(min_length=1)


class VoiceTranscribeRequest(BaseModel):
    audio: bytes


class VoiceCommandResponse(BaseModel):
    transcription: str
    intent: str
    response_text: str
    processing_time_ms: int


class VoiceCommandLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    transcription: str
    intent: str
    intent_confidence: float
    response_text: str
    processing_time_ms: int
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}
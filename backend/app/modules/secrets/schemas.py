"""WILLIAM OS - Encrypted API secret schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SecretRotateRequest(BaseModel):
    provider: str = Field(min_length=2, max_length=64)
    plaintext_key: str = Field(min_length=8, max_length=4096)


class SecretMetadataResponse(BaseModel):
    id: UUID
    provider: str
    key_hint: str
    version: int
    is_active: bool
    rotated_at: datetime

    model_config = {"from_attributes": True}

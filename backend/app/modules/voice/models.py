"""
WILLIAM OS — Voice Models
Voice command history and execution metadata.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VoiceCommand(Base):
    __tablename__ = "voice_commands"
    __table_args__ = {"schema": "voice"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audio_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transcription: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    intent_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(20), default="text")

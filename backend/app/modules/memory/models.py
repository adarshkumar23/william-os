"""WILLIAM OS - Personal memory graph models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from app.core.database import Base
from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class MemoryType(str, Enum):
    PREFERENCE = "preference"
    PATTERN = "pattern"
    CORRELATION = "correlation"
    INSIGHT = "insight"


class UserMemory(Base):
    __tablename__ = "user_memories"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_user_memories_user_key"),
        {"schema": "memory", "info": {"constraint_name": "uq_user_memories_user_key"}},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_type: Mapped[MemoryType] = mapped_column(
        SAEnum(MemoryType, schema="memory"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
        index=True,
    )
    source_modules: Mapped[list[str]] = mapped_column(JSONB, default=list)


class MemoryInsight(Base):
    __tablename__ = "memory_insights"
    __table_args__ = {"schema": "memory"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    insight: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(default=True, index=True)

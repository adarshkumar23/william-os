"""WILLIAM OS - Encrypted API secret models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApiSecret(Base):
    __tablename__ = "api_secrets"
    __table_args__ = {"schema": "security"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_hint: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

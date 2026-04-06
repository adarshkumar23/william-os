"""
WILLIAM OS — Messaging Models
Telegram account linkage and outbound notification delivery logs.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.database import Base
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


def _default_notification_preferences() -> dict[str, bool]:
    return {
        "schedule": True,
        "medicine": True,
        "habits": True,
        "briefing": True,
    }


class TelegramUser(Base):
    __tablename__ = "telegram_users"
    __table_args__ = {"schema": "messaging"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    telegram_chat_id: Mapped[int | None] = mapped_column(
        BigInteger,
        unique=True,
        nullable=True,
    )
    telegram_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    notification_preferences: Mapped[dict] = mapped_column(
        JSONB,
        default=_default_notification_preferences,
    )


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    __table_args__ = {"schema": "messaging"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
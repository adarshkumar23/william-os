"""
WILLIAM OS — Email Intelligence Models
Connected email accounts and generated daily summaries.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from app.core.database import Base
from sqlalchemy import Boolean, Date, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class EmailAccount(Base):
    __tablename__ = "email_accounts"
    __table_args__ = {"schema": "email_intel"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # gmail, outlook
    email_address: Mapped[str] = mapped_column(String(255), nullable=False)

    oauth_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    refresh_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    last_sync_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EmailSummary(Base):
    __tablename__ = "email_summaries"
    __table_args__ = {"schema": "email_intel"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    email_count: Mapped[int] = mapped_column(Integer, default=0)

    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    priority_emails: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    action_items: Mapped[list[str]] = mapped_column(JSONB, default=list)

    generated_by: Mapped[str] = mapped_column(String(100), nullable=False)
    generation_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

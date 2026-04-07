"""WILLIAM OS - User automation rules models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.database import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class UserRule(Base):
    __tablename__ = "user_rules"
    __table_args__ = {"schema": "rules"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    trigger_module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    trigger_condition: Mapped[dict] = mapped_column(JSONB, default=dict)
    action_module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    action_params: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_triggered: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RuleExecutionLog(Base):
    __tablename__ = "rule_execution_logs"
    __table_args__ = {"schema": "rules"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rules.user_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    matched: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    action_success: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    context_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    action_result: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

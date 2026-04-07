"""WILLIAM OS - Agent layer persistence models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.core.database import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class AgentStatus(Base):
    __tablename__ = "agent_status"
    __table_args__ = (
        UniqueConstraint("user_id", "agent_name", name="uq_agent_status_user_name"),
        {"schema": "agents", "info": {"constraint_name": "uq_agent_status_user_name"}},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="idle", index=True)
    last_recommendation: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_action: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )


class AgentRecommendationLog(Base):
    __tablename__ = "agent_recommendations"
    __table_args__ = {"schema": "agents"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="low", index=True)
    urgency: Mapped[int] = mapped_column(Integer, default=0, index=True)
    recommendation: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class AgentActionLog(Base):
    __tablename__ = "agent_actions"
    __table_args__ = {"schema": "agents"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

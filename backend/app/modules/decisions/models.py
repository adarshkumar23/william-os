"""
WILLIAM OS — Decisions Models
Decision tracking, AI analysis, and template support.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

import structlog
from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

logger = structlog.get_logger(__name__)


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = {"schema": "decisions"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open")
    decision_type: Mapped[str] = mapped_column(String(50), nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    options: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    criteria: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    ai_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    chosen_option: Mapped[str | None] = mapped_column(String(200), nullable=True)
    chosen_at: Mapped[datetime | None] = mapped_column(nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class DecisionTemplate(Base):
    __tablename__ = "decision_templates"
    __table_args__ = {"schema": "decisions"}

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    decision_type: Mapped[str] = mapped_column(String(50), nullable=False)
    default_criteria: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)

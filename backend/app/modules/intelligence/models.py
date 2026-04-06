"""
WILLIAM OS — Intelligence Models
Cross-module signals and rule definitions.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.core.database import Base
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class ModuleSignal(Base):
    __tablename__ = "module_signals"
    __table_args__ = {"schema": "intelligence"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


class CrossModuleRule(Base):
    __tablename__ = "cross_module_rules"
    __table_args__ = {"schema": "intelligence"}

    trigger_module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    trigger_condition: Mapped[dict] = mapped_column(JSONB, default=dict)
    affected_module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    adjustment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    adjustment_value: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class LifeScore(Base):
    __tablename__ = "life_scores"
    __table_args__ = {"schema": "intelligence"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    component_scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

"""
WILLIAM OS — Audit Models
Every significant action is logged for transparency and AI learning.
"""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditAction(str, Enum):
    # Auth
    USER_REGISTER = "user.register"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    TOKEN_REFRESH = "token.refresh"
    PASSWORD_CHANGE = "password.change"

    # Scheduler
    SCHEDULE_GENERATE = "schedule.generate"
    SCHEDULE_RESCHEDULE = "schedule.reschedule"
    BLOCK_CREATE = "block.create"
    BLOCK_UPDATE = "block.update"
    BLOCK_COMPLETE = "block.complete"

    # Habits
    HABIT_CREATE = "habit.create"
    HABIT_CHECK_IN = "habit.check_in"

    # Journal
    JOURNAL_CREATE = "journal.create"
    JOURNAL_READ = "journal.read"

    # Medicine
    MEDICINE_TAKEN = "medicine.taken"
    MEDICINE_MISSED = "medicine.missed"

    # AI
    AI_CALL = "ai.call"

    # System
    DATA_EXPORT = "data.export"
    DATA_DELETE = "data.delete"
    SETTINGS_CHANGE = "settings.change"


class AuditLog(Base):
    """Immutable audit trail. Append-only."""

    __tablename__ = "audit_logs"
    __table_args__ = {"schema": "audit"}

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True,
    )
    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, schema="audit"), nullable=False, index=True,
    )
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    module: Mapped[str] = mapped_column(String(50), default="system")

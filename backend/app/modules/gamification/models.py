"""
WILLIAM OS — Gamification Models
XP ledger, personal records, and weekly momentum snapshots.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserXP(Base):
    __tablename__ = "user_xp"
    __table_args__ = {"schema": "gamification"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    total_xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
        index=True,
    )


class XPEvent(Base):
    __tablename__ = "xp_events"
    __table_args__ = {"schema": "gamification"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False)
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
        index=True,
    )


class PersonalRecord(Base):
    __tablename__ = "personal_records"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "record_type",
            name="uq_personal_records_user_record_type",
        ),
        {
            "schema": "gamification",
            "info": {"constraint_name": "uq_personal_records_user_record_type"},
        },
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    record_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    achieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
        index=True,
    )


class WeeklyMomentum(Base):
    __tablename__ = "weekly_momentum"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start", name="uq_weekly_momentum_user_week"),
        {
            "schema": "gamification",
            "info": {"constraint_name": "uq_weekly_momentum_user_week"},
        },
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    momentum_score: Mapped[float] = mapped_column(Float, default=0.0)
    discipline_debt: Mapped[float] = mapped_column(Float, default=0.0)
    focus_rank: Mapped[int] = mapped_column(Integer, default=0)

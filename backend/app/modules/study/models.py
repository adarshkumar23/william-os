"""
WILLIAM OS — Study Models
IAS study tracking, spaced revision, and mock test analytics.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from app.core.database import Base
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = {"schema": "study"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    syllabus_topics: Mapped[list[str]] = mapped_column(JSONB, default=list)
    total_weight: Mapped[float] = mapped_column(Float, default=0.0)
    color: Mapped[str] = mapped_column(String(7), default="#3B82F6")


class StudySession(Base):
    __tablename__ = "study_sessions"
    __table_args__ = {"schema": "study"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study.subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    topics_covered: Mapped[list[str]] = mapped_column(JSONB, default=list)
    comprehension_score: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)


class RevisionCard(Base):
    __tablename__ = "revision_cards"
    __table_args__ = {"schema": "study"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study.subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    next_review_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed: Mapped[date | None] = mapped_column(Date, nullable=True)


class MockTest(Base):
    __tablename__ = "mock_tests"
    __table_args__ = {"schema": "study"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study.subjects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    test_name: Mapped[str] = mapped_column(String(200), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    percentage: Mapped[float] = mapped_column(Float, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class StudyFocusSession(Base):
    __tablename__ = "focus_sessions"
    __table_args__ = {"schema": "study"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("study.subjects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_minutes: Mapped[int] = mapped_column(Integer, default=25)
    actual_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distraction_count: Mapped[int] = mapped_column(Integer, default=0)
    focus_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)

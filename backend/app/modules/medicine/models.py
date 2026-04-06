"""
WILLIAM OS — Medicine / Supplement Reminder Models
User-configured reminders only. WILLIAM OS does NOT prescribe.
"""

from __future__ import annotations

import uuid
from datetime import date, time
from enum import Enum

from sqlalchemy import Boolean, Date, Enum as SAEnum, ForeignKey, Integer, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MedicineType(str, Enum):
    PRESCRIPTION = "prescription"
    SUPPLEMENT = "supplement"
    VITAMIN = "vitamin"
    OTHER = "other"


class Medicine(Base):
    __tablename__ = "medicines"
    __table_args__ = {"schema": "medicine"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    dosage: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "500mg"
    medicine_type: Mapped[MedicineType] = mapped_column(
        SAEnum(MedicineType, schema="medicine"), default=MedicineType.SUPPLEMENT,
    )
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Schedule
    times_per_day: Mapped[int] = mapped_column(Integer, default=1)
    reminder_times: Mapped[list[str]] = mapped_column(JSONB, default=list)  # ["08:00", "20:00"]
    with_food: Mapped[bool] = mapped_column(Boolean, default=False)

    # Tracking
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    refill_reminder_days: Mapped[int] = mapped_column(Integer, default=7)
    remaining_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    logs: Mapped[list["MedicineLog"]] = relationship(
        back_populates="medicine", cascade="all, delete-orphan", lazy="selectin",
    )


class MedicineLog(Base):
    __tablename__ = "medicine_logs"
    __table_args__ = {"schema": "medicine"}

    medicine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medicine.medicines.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    log_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_time: Mapped[time] = mapped_column(Time, nullable=False)
    taken: Mapped[bool] = mapped_column(Boolean, default=False)
    taken_at: Mapped[time | None] = mapped_column(Time, nullable=True)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    skip_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    medicine: Mapped[Medicine] = relationship(back_populates="logs")

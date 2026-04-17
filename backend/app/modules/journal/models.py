"""
WILLIAM OS — Journal Vault Models
Encrypted private journal. Content is AES-256-GCM encrypted per-user.
Only the user's passphrase can decrypt entries.
"""

from __future__ import annotations

import uuid
from datetime import date
from enum import Enum

from app.core.database import Base
from sqlalchemy import Date, ForeignKey, LargeBinary, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class JournalMood(str, Enum):
    GREAT = "great"
    GOOD = "good"
    OKAY = "okay"
    LOW = "low"
    BAD = "bad"


class JournalEntry(Base):
    """
    Journal entry with encrypted content.
    The `encrypted_content` column stores: salt(16) + nonce(12) + ciphertext.
    Decryption requires the user's journal passphrase (never stored in plaintext).
    """

    __tablename__ = "journal_entries"
    __table_args__ = {"schema": "journal"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Encrypted content — only decryptable with user passphrase
    encrypted_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # Unencrypted metadata (for queries without decryption)
    mood: Mapped[JournalMood | None] = mapped_column(
        SAEnum(JournalMood, schema="journal"),
        nullable=True,
    )
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    word_count: Mapped[int | None] = mapped_column(default=None)

    # AI-generated summary (encrypted separately)
    encrypted_summary: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)


class JournalDraft(Base):
    """Single encrypted draft per user for in-progress journaling."""

    __tablename__ = "journal_drafts"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_journal_drafts_user_id"),
        {"schema": "journal"},
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    encrypted_content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mood: Mapped[JournalMood | None] = mapped_column(
        SAEnum(JournalMood, schema="journal"),
        nullable=True,
    )
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)

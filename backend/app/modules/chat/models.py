"""
WILLIAM OS — Chat Models
Chat sessions and messages for conversational agent interactions.
"""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AgentName(str, Enum):
    OS = "os"
    HEALTH = "health"
    STUDY = "study"
    TRADING = "trading"
    EXECUTIVE = "executive"
    RECOVERY = "recovery"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = {"schema": "chat"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[AgentName] = mapped_column(
        SAEnum(AgentName, schema="chat"),
        default=AgentName.OS,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), default="New Chat")

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ChatMessage.created_at.asc()",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = {"schema": "chat"}

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat.chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        SAEnum(MessageRole, schema="chat"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    actions_taken: Mapped[list | None] = mapped_column(JSONB, default=list)
    extra_metadata: Mapped[dict | None] = mapped_column("extra_metadata", JSONB, default=None)

    session: Mapped[ChatSession] = relationship(back_populates="messages")

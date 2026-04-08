"""
WILLIAM OS — User Model
Multi-user support with family ecosystem roles.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Enum as SAEnum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(str, Enum):
    OWNER = "owner"        # Primary user — full access
    FAMILY = "family"      # Family member — scoped access
    GUEST = "guest"        # Limited view access


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, schema="auth"), default=UserRole.OWNER, nullable=False
    )

    # Family ecosystem
    family_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.families.id"), nullable=True
    )

    # Profile & Preferences
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata")
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    wake_time: Mapped[str | None] = mapped_column(
        String(5),
        default="06:00",
        nullable=True,
    )  # HH:MM
    sleep_time: Mapped[str] = mapped_column(String(5), default="22:30")
    sleep_goal: Mapped[float | None] = mapped_column(Float, nullable=True)  # target hours
    focus_areas: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Security
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secret: Mapped[str | None] = mapped_column(String(32), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(default=0)
    permission_scopes: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # Journal vault passphrase hash (separate from login password)
    journal_passphrase_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    devices: Mapped[list["UserDevice"]] = relationship(back_populates="user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role.value})>"


class Family(Base):
    __tablename__ = "families"
    __table_args__ = {"schema": "auth"}

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    members: Mapped[list[User]] = relationship(
        "User", foreign_keys=[User.family_id], lazy="selectin"
    )


class UserDevice(Base):
    __tablename__ = "user_devices"
    __table_args__ = {"schema": "auth"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    device_name: Mapped[str] = mapped_column(String(100), nullable=False)
    device_fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_type: Mapped[str] = mapped_column(String(20), nullable=False)  # ios, android, web, alexa
    refresh_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_active: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped[User] = relationship(back_populates="devices")


class RefreshTokenBlacklist(Base):
    __tablename__ = "refresh_token_blacklist"
    __table_args__ = {"schema": "auth"}

    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)


class LoginHistory(Base):
    __tablename__ = "login_history"
    __table_args__ = {"schema": "auth"}

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    device_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(nullable=False, index=True)

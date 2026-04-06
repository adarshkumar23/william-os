"""
WILLIAM OS — Auth Service
User registration, login, token management, device tracking.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from app.core.events import Event, EventType, event_bus
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_device_fingerprint,
    hash_password,
    verify_password,
)
from app.modules.auth.models import RefreshTokenBlacklist, User, UserDevice
from app.modules.auth.schemas import (
    TokenResponse,
    UserLogin,
    UserProfile,
    UserRegister,
)
from app.shared.types import AuthenticationError, NotFoundError, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: UserRegister) -> UserProfile:
        # Check uniqueness
        existing = await self.db.execute(
            select(User).where((User.email == data.email) | (User.username == data.username))
        )
        if existing.scalar_one_or_none():
            raise ValidationError("Email or username already registered")

        user = User(
            email=data.email,
            username=data.username,
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            timezone=data.timezone,
        )
        self.db.add(user)
        await self.db.flush()

        logger.info("user_registered", user_id=str(user.id), email=data.email)
        await event_bus.publish(
            Event(
                type=EventType.USER_REGISTERED,
                data={"email": data.email, "username": data.username},
                user_id=user.id,
            )
        )

        return UserProfile.model_validate(user)

    async def login(self, data: UserLogin, user_agent: str = "", ip: str = "") -> TokenResponse:
        user = await self._get_user_by_email(data.email)
        if not user or not verify_password(data.password, user.hashed_password):
            if user:
                user.failed_login_attempts += 1
                await self.db.flush()
                if user.failed_login_attempts >= 10:
                    raise AuthenticationError(
                        "Account locked after too many failed attempts. Contact support to unlock."
                    )
            raise AuthenticationError()

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        # Reset failed attempts on success
        user.failed_login_attempts = 0

        # Track device
        fingerprint = generate_device_fingerprint(user_agent, ip)
        await self._register_device(user.id, data.device_name, data.device_type, fingerprint)

        # Generate tokens
        access = create_access_token(user.id, {"role": user.role.value})
        refresh = create_refresh_token(user.id)
        await self.db.flush()

        logger.info("user_logged_in", user_id=str(user.id))
        await event_bus.publish(
            Event(
                type=EventType.USER_LOGGED_IN,
                data={"device": data.device_name, "device_type": data.device_type},
                user_id=user.id,
            )
        )

        from app.core.config import get_settings

        settings = get_settings()

        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    async def refresh_tokens(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except Exception as e:
            raise AuthenticationError(f"Invalid refresh token: {e}")

        if payload.get("type") != "refresh":
            raise AuthenticationError("Not a refresh token")

        jti = payload.get("jti", "")
        await self._revoke_refresh_token_jti(jti, payload["exp"])

        user_id = uuid.UUID(payload["sub"])
        user = await self._get_user_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        # Issue new tokens
        access = create_access_token(user.id, {"role": user.role.value})
        refresh = create_refresh_token(user.id)
        await self.db.flush()

        from app.core.config import get_settings

        settings = get_settings()

        return TokenResponse(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    async def revoke_refresh_token(self, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token)
        except Exception:
            return

        if payload.get("type") != "refresh":
            return

        jti = payload.get("jti", "")
        exp = payload.get("exp")
        if not jti or not exp:
            return

        await self._revoke_refresh_token_jti(jti, exp)

    async def _revoke_refresh_token_jti(self, jti: str, exp_timestamp: int) -> None:
        # Atomic insert prevents refresh-token replay races on concurrent requests.
        self.db.add(
            RefreshTokenBlacklist(
                jti=jti,
                expires_at=datetime.fromtimestamp(exp_timestamp, tz=UTC),
            )
        )
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            raise AuthenticationError("Token has already been used or revoked")

    async def get_profile(self, user_id: uuid.UUID) -> UserProfile:
        user = await self._get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))
        return UserProfile.model_validate(user)

    async def _get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def _get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def _register_device(
        self,
        user_id: uuid.UUID,
        name: str,
        device_type: str,
        fingerprint: str,
    ) -> None:
        existing = await self.db.execute(
            select(UserDevice).where(UserDevice.device_fingerprint == fingerprint)
        )
        device = existing.scalar_one_or_none()

        if device:
            device.last_active = datetime.now(UTC)
            device.device_name = name
        else:
            self.db.add(
                UserDevice(
                    user_id=user_id,
                    device_name=name,
                    device_type=device_type,
                    device_fingerprint=fingerprint,
                    last_active=datetime.now(UTC),
                )
            )

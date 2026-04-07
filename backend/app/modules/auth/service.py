"""
WILLIAM OS — Auth Service
User registration, login, token management, device tracking.
"""

from __future__ import annotations

import base64
import io
import uuid
from datetime import UTC, datetime

import httpx
import pyotp
import qrcode
import structlog
from app.core.events import Event, EventType, event_bus
from app.core.permissions import default_scopes_for_role
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_device_fingerprint,
    hash_token,
    hash_password,
    verify_password,
)
from app.modules.auth.models import LoginHistory, RefreshTokenBlacklist, User, UserDevice
from app.modules.messaging.schemas import NotificationPayload
from app.modules.messaging.service import MessagingService
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
            permission_scopes=default_scopes_for_role("owner"),
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
        fingerprint = generate_device_fingerprint(user_agent, ip)
        country = await self._resolve_country(ip)

        if not user or not verify_password(data.password, user.hashed_password):
            if user:
                user.failed_login_attempts += 1
                await self.db.flush()
                await self._record_login(
                    user_id=user.id,
                    ip=ip,
                    country=country,
                    device_fingerprint=fingerprint,
                    user_agent=user_agent,
                    success=False,
                )
                if user.failed_login_attempts >= 10:
                    raise AuthenticationError(
                        "Account locked after too many failed attempts. Contact support to unlock."
                    )
            else:
                await self._record_login(
                    user_id=None,
                    ip=ip,
                    country=country,
                    device_fingerprint=fingerprint,
                    user_agent=user_agent,
                    success=False,
                )
            raise AuthenticationError()

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        if user.totp_enabled:
            if not data.totp_code:
                raise AuthenticationError("Two-factor authentication code is required")
            if not user.totp_secret:
                raise AuthenticationError("Two-factor authentication is misconfigured")

            if not pyotp.TOTP(user.totp_secret).verify(data.totp_code, valid_window=1):
                await self._record_login(
                    user_id=user.id,
                    ip=ip,
                    country=country,
                    device_fingerprint=fingerprint,
                    user_agent=user_agent,
                    success=False,
                )
                raise AuthenticationError("Invalid two-factor authentication code")

        # Reset failed attempts on success
        user.failed_login_attempts = 0
        if not user.permission_scopes:
            user.permission_scopes = default_scopes_for_role(user.role.value)

        # Track device
        device = await self._register_device(
            user_id=user.id,
            name=data.device_name,
            device_type=data.device_type,
            fingerprint=fingerprint,
        )

        suspicious_reason = await self._detect_suspicious_login(
            user_id=user.id,
            ip=ip,
            country=country,
            fingerprint=fingerprint,
        )

        # Generate tokens
        access = create_access_token(
            user.id,
            {
                "role": user.role.value,
                "scopes": user.permission_scopes,
            },
        )
        refresh = create_refresh_token(user.id)
        device.refresh_token_hash = hash_token(refresh)
        device.is_active = True

        await self._record_login(
            user_id=user.id,
            ip=ip,
            country=country,
            device_fingerprint=fingerprint,
            user_agent=user_agent,
            success=True,
        )

        if suspicious_reason:
            await self._send_suspicious_login_alert(
                user_id=user.id,
                reason=suspicious_reason,
                ip=ip,
                country=country,
                user_agent=user_agent,
            )

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
        except Exception as exc:
            raise AuthenticationError(f"Invalid refresh token: {exc}") from exc

        if payload.get("type") != "refresh":
            raise AuthenticationError("Not a refresh token")

        user_id = uuid.UUID(payload["sub"])
        user = await self._get_user_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        hashed_refresh = hash_token(refresh_token)
        device_result = await self.db.execute(
            select(UserDevice).where(
                UserDevice.user_id == user_id,
                UserDevice.refresh_token_hash == hashed_refresh,
                UserDevice.is_active.is_(True),
            )
        )
        device = device_result.scalar_one_or_none()
        if device is None:
            raise AuthenticationError("Session is no longer active")

        jti = payload.get("jti", "")
        await self._revoke_refresh_token_jti(jti, payload["exp"])

        # Issue new tokens
        scopes = user.permission_scopes or default_scopes_for_role(user.role.value)
        access = create_access_token(user.id, {"role": user.role.value, "scopes": scopes})
        refresh = create_refresh_token(user.id)
        device.refresh_token_hash = hash_token(refresh)
        device.last_active = datetime.now(UTC).replace(tzinfo=None).replace(tzinfo=None)
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

        try:
            user_id = uuid.UUID(payload.get("sub", ""))
        except Exception:
            return

        hashed_refresh = hash_token(refresh_token)
        result = await self.db.execute(
            select(UserDevice).where(
                UserDevice.user_id == user_id,
                UserDevice.refresh_token_hash == hashed_refresh,
            )
        )
        device = result.scalar_one_or_none()
        if device:
            device.refresh_token_hash = None
            device.is_active = False
            await self.db.flush()

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
        except IntegrityError as exc:
            await self.db.rollback()
            raise AuthenticationError("Token has already been used or revoked") from exc

    async def get_profile(self, user_id: uuid.UUID) -> UserProfile:
        user = await self._get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))
        return UserProfile.model_validate(user)

    async def generate_totp_setup(self, user_id: uuid.UUID) -> dict[str, str]:
        user = await self._get_user_by_id(user_id)
        if user is None:
            raise NotFoundError("User", str(user_id))

        if not user.totp_secret:
            user.totp_secret = pyotp.random_base32()

        otp_auth_url = pyotp.TOTP(user.totp_secret).provisioning_uri(
            name=user.email,
            issuer_name="WILLIAM OS",
        )

        image = qrcode.make(otp_auth_url)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        qr_code_data_url = (
            "data:image/png;base64,"
            f"{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
        )

        await self.db.flush()
        return {
            "otp_auth_url": otp_auth_url,
            "qr_code_data_url": qr_code_data_url,
            "secret_preview": f"{user.totp_secret[:4]}...{user.totp_secret[-4:]}",
        }

    async def verify_totp(self, user_id: uuid.UUID, code: str) -> bool:
        user = await self._get_user_by_id(user_id)
        if user is None:
            raise NotFoundError("User", str(user_id))
        if not user.totp_secret:
            raise ValidationError("TOTP setup is not initialized")

        is_valid = pyotp.TOTP(user.totp_secret).verify(code, valid_window=1)
        if not is_valid:
            return False

        user.totp_enabled = True
        await self.db.flush()
        return True

    async def list_sessions(
        self,
        user_id: uuid.UUID,
        current_refresh_token: str | None = None,
    ) -> list[dict[str, object]]:
        result = await self.db.execute(
            select(UserDevice)
            .where(UserDevice.user_id == user_id)
            .order_by(UserDevice.last_active.desc(), UserDevice.created_at.desc())
        )
        rows = result.scalars().all()
        current_hash = hash_token(current_refresh_token) if current_refresh_token else None

        sessions: list[dict[str, object]] = []
        for row in rows:
            sessions.append(
                {
                    "id": row.id,
                    "device_name": row.device_name,
                    "device_type": row.device_type,
                    "device_fingerprint": row.device_fingerprint,
                    "last_active": row.last_active,
                    "is_active": row.is_active,
                    "created_at": row.created_at,
                    "is_current": bool(current_hash)
                    and bool(row.refresh_token_hash)
                    and row.refresh_token_hash == current_hash,
                }
            )
        return sessions

    async def revoke_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(UserDevice).where(
                UserDevice.id == session_id,
                UserDevice.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False

        row.is_active = False
        row.refresh_token_hash = None
        await self.db.flush()
        return True

    async def list_login_history(self, user_id: uuid.UUID, limit: int = 25) -> list[LoginHistory]:
        result = await self.db.execute(
            select(LoginHistory)
            .where(LoginHistory.user_id == user_id)
            .order_by(LoginHistory.timestamp.desc(), LoginHistory.created_at.desc())
            .limit(max(1, min(limit, 100)))
        )
        return list(result.scalars().all())

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
    ) -> UserDevice:
        existing = await self.db.execute(
            select(UserDevice).where(UserDevice.device_fingerprint == fingerprint)
        )
        device = existing.scalar_one_or_none()

        if device:
            device.last_active = datetime.now(UTC).replace(tzinfo=None).replace(tzinfo=None)
            device.device_name = name
            device.device_type = device_type
            device.user_id = user_id
        else:
            device = UserDevice(
                user_id=user_id,
                device_name=name,
                device_type=device_type,
                device_fingerprint=fingerprint,
                last_active=datetime.now(UTC).replace(tzinfo=None).replace(tzinfo=None),
            )
            self.db.add(device)

        return device

    async def _record_login(
        self,
        user_id: uuid.UUID | None,
        ip: str,
        country: str,
        device_fingerprint: str,
        user_agent: str,
        success: bool,
    ) -> None:
        self.db.add(
            LoginHistory(
                user_id=user_id,
                ip=ip or None,
                country=country or None,
                device_fingerprint=device_fingerprint,
                user_agent=user_agent or None,
                success=success,
                timestamp=datetime.now(UTC).replace(tzinfo=None).replace(tzinfo=None),
            )
        )
        await self.db.flush()

    async def _detect_suspicious_login(
        self,
        user_id: uuid.UUID,
        ip: str,
        country: str,
        fingerprint: str,
    ) -> str | None:
        result = await self.db.execute(
            select(LoginHistory)
            .where(LoginHistory.user_id == user_id, LoginHistory.success.is_(True))
            .order_by(LoginHistory.timestamp.desc(), LoginHistory.created_at.desc())
            .limit(1)
        )
        previous = result.scalar_one_or_none()
        if previous is None:
            return None

        reasons: list[str] = []
        if previous.ip and ip and previous.ip != ip:
            reasons.append("new_ip")
        if previous.country and country and previous.country != country:
            reasons.append("new_country")
        if previous.device_fingerprint and previous.device_fingerprint != fingerprint:
            reasons.append("new_device")

        return ",".join(reasons) if reasons else None

    async def _send_suspicious_login_alert(
        self,
        user_id: uuid.UUID,
        reason: str,
        ip: str,
        country: str,
        user_agent: str,
    ) -> None:
        try:
            service = MessagingService(self.db)
            payload = NotificationPayload(
                title="Suspicious login detected",
                body=(
                    f"Reason: {reason}. IP: {ip or 'unknown'}. "
                    f"Country: {country or 'unknown'}."
                ),
                notification_type="security_alert",
                data={"reason": reason, "ip": ip, "country": country, "user_agent": user_agent},
            )
            await service.send_notification(user_id=user_id, payload=payload)
        except Exception as exc:
            logger.warning("suspicious_login_alert_failed", user_id=str(user_id), error=str(exc))

    async def _resolve_country(self, ip: str) -> str:
        if not ip:
            return "unknown"
        if ip in {"127.0.0.1", "::1", "localhost"}:
            return "local"

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"https://ipapi.co/{ip}/country_name/")
                if response.status_code >= 400:
                    return "unknown"
                value = response.text.strip()
                return value or "unknown"
        except Exception:
            return "unknown"

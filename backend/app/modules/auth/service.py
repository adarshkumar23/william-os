"""
WILLIAM OS — Auth Service
User registration, login, token management, device tracking.
"""

from __future__ import annotations

import base64
import io
import uuid
from datetime import UTC, date, datetime, time, timedelta

import httpx
import pyotp
import qrcode
import structlog
from app.core.email import send_invite_email
from app.core.config import get_settings
from app.core.events import Event, EventType, event_bus
from app.core.permissions import default_scopes_for_role
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_device_fingerprint,
    hash_password,
    hash_token,
    verify_password,
)
from app.modules.auth.models import LoginHistory, RefreshTokenBlacklist, User, UserDevice
from app.modules.auth.models import UserRole
from app.modules.auth.schemas import (
    AdminStatsResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    FamilyInviteRequest,
    OnboardingCompleteRequest,
    OnboardingStatusResponse,
    ProfileUpdateRequest,
    TokenResponse,
    UserLogin,
    UserProfile,
    UserRegister,
)
from app.modules.messaging.schemas import NotificationPayload
from app.modules.messaging.service import MessagingService
from app.shared.types import AuthenticationError, NotFoundError, ValidationError
from sqlalchemy import func, select
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

    async def update_profile(
        self,
        user_id: uuid.UUID,
        data: ProfileUpdateRequest,
    ) -> UserProfile:
        user = await self._get_user_by_id(user_id)
        if user is None:
            raise NotFoundError("User", str(user_id))

        payload = data.model_dump(exclude_unset=True)
        for field_name, value in payload.items():
            setattr(user, field_name, value)

        await self.db.flush()
        await self.db.refresh(user)
        return UserProfile.model_validate(user)

    async def admin_list_users(self, owner_user_id: uuid.UUID) -> list[AdminUserResponse]:
        await self._assert_owner(owner_user_id)
        result = await self.db.execute(select(User).order_by(User.created_at.desc()))
        rows = result.scalars().all()
        return [AdminUserResponse.model_validate(row) for row in rows]

    async def admin_update_user(
        self,
        owner_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        data: AdminUserUpdateRequest,
    ) -> AdminUserResponse:
        await self._assert_owner(owner_user_id)
        target = await self._get_user_by_id(target_user_id)
        if target is None:
            raise NotFoundError("User", str(target_user_id))

        if data.role is not None:
            target.role = UserRole(data.role)
            target.permission_scopes = default_scopes_for_role(target.role.value)
        if data.is_active is not None:
            if target_user_id == owner_user_id and data.is_active is False:
                raise ValidationError("Owner cannot deactivate their own account")
            target.is_active = data.is_active

        await self.db.flush()
        await self.db.refresh(target)
        return AdminUserResponse.model_validate(target)

    async def admin_deactivate_user(
        self,
        owner_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
    ) -> AdminUserResponse:
        return await self.admin_update_user(
            owner_user_id=owner_user_id,
            target_user_id=target_user_id,
            data=AdminUserUpdateRequest(is_active=False),
        )

    async def admin_stats(self, owner_user_id: uuid.UUID) -> AdminStatsResponse:
        await self._assert_owner(owner_user_id)
        week_cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=7)

        total_result = await self.db.execute(select(func.count(User.id)))
        active_result = await self.db.execute(
            select(func.count(User.id)).where(User.is_active.is_(True))
        )
        new_result = await self.db.execute(
            select(func.count(User.id)).where(User.created_at >= week_cutoff)
        )
        return AdminStatsResponse(
            total_users=int(total_result.scalar() or 0),
            active_users=int(active_result.scalar() or 0),
            new_this_week=int(new_result.scalar() or 0),
        )

    async def invite_family(
        self,
        owner_user_id: uuid.UUID,
        data: FamilyInviteRequest,
    ) -> dict[str, str]:
        await self._assert_owner(owner_user_id)
        settings = get_settings()
        token = uuid.uuid4().hex
        invite_link = (
            f"{settings.base_url.rstrip('/')}/register?invite={token}"
            f"&email={data.email}&role={data.role}"
        )
        return {
            "status": "created",
            "invite_link": invite_link,
            "email": str(data.email),
            "role": data.role,
        }

    async def get_onboarding_status(self, user_id: uuid.UUID) -> OnboardingStatusResponse:
        user = await self._get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))
        return OnboardingStatusResponse(completed=bool(user.onboarding_completed))

    async def complete_onboarding(
        self,
        user_id: uuid.UUID,
        data: OnboardingCompleteRequest,
    ) -> dict[str, object]:
        user = await self._get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User", str(user_id))

        user.display_name = data.display_name.strip()
        user.wake_time = data.wake_time
        user.sleep_goal = data.sleep_goal
        user.focus_areas = data.focus_areas
        user.onboarding_completed = True
        preferences = user.preferences or {}
        preferences["onboarding_goals"] = data.goals
        user.preferences = preferences

        habits_created = await self._create_starter_habits(
            user_id=user.id,
            wake_time=data.wake_time,
            focus_areas=data.focus_areas,
        )
        await self._generate_initial_schedule(
            user_id=user.id,
            focus_areas=data.focus_areas,
            goals=data.goals,
        )
        await self.db.flush()

        logger.info("onboarding_completed", user_id=str(user.id), focus_areas=data.focus_areas)
        return {
            "status": "completed",
            "habits_created": habits_created,
            "message": "William is ready",
        }

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
            f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
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

    async def _assert_owner(self, user_id: uuid.UUID) -> User:
        user = await self._get_user_by_id(user_id)
        if user is None:
            raise NotFoundError("User", str(user_id))
        if user.role != UserRole.OWNER:
            from app.shared.types import AuthorizationError

            raise AuthorizationError("Owner role required")
        return user

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
                body=(f"Reason: {reason}. IP: {ip or 'unknown'}. Country: {country or 'unknown'}."),
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

    async def _create_starter_habits(
        self,
        user_id: uuid.UUID,
        wake_time: str,
        focus_areas: list[str],
    ) -> list[str]:
        from app.modules.habits.models import Habit
        from app.modules.habits.schemas import HabitCreate
        from app.modules.habits.service import HabitsService

        habit_service = HabitsService(self.db)
        existing_result = await self.db.execute(select(Habit.name).where(Habit.user_id == user_id))
        existing_names = {name.lower() for name in existing_result.scalars().all()}

        try:
            wake_clock = datetime.strptime(wake_time, "%H:%M").time()
        except ValueError:
            wake_clock = time(hour=6, minute=30)
        fitness_clock = (datetime.combine(date.today(), wake_clock) + timedelta(hours=1)).time()

        templates_by_focus: dict[str, HabitCreate] = {
            "habits": HabitCreate(
                name="Morning Routine",
                description="Start your day with intent.",
                category="routine",
                icon="MORNING",
                preferred_time=wake_clock,
                duration_minutes=30,
                schedule_category="routine",
            ),
            "fitness": HabitCreate(
                name="Daily Workout",
                description="Move your body every day.",
                category="fitness",
                icon="FIT",
                preferred_time=fitness_clock,
                duration_minutes=45,
                schedule_category="fitness",
            ),
            "study": HabitCreate(
                name="Study Session",
                description="Protected focused study block.",
                category="study",
                icon="BOOK",
                preferred_time=time(hour=9, minute=0),
                duration_minutes=60,
                schedule_category="study",
            ),
            "trading": HabitCreate(
                name="Market Review",
                description="Review markets and key setups.",
                category="trading",
                icon="TRADE",
                preferred_time=time(hour=8, minute=0),
                duration_minutes=30,
                schedule_category="work",
            ),
        }

        created: list[str] = []
        for focus in focus_areas:
            template = templates_by_focus.get(focus)
            if not template:
                continue
            if template.name.lower() in existing_names:
                continue
            await habit_service.create_habit(user_id=user_id, data=template)
            existing_names.add(template.name.lower())
            created.append(template.name)

        return created

    async def _generate_initial_schedule(
        self,
        user_id: uuid.UUID,
        focus_areas: list[str],
        goals: str,
    ) -> None:
        from app.modules.scheduler.schemas import ScheduleGenerateRequest
        from app.modules.scheduler.service import SchedulerService

        scheduler = SchedulerService(self.db)
        request = ScheduleGenerateRequest(
            target_date=date.today(),
            extra_context={"priorities": focus_areas, "goals": goals},
        )
        try:
            await scheduler.generate_daily_plan(user_id=user_id, request=request)
        except ValidationError:
            # Existing plan for today is acceptable during onboarding completion.
            pass
        except Exception as exc:
            logger.warning(
                "onboarding_schedule_generation_failed",
                user_id=str(user_id),
                error=str(exc),
            )

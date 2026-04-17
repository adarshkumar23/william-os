"""
WILLIAM OS — Auth Routes
Registration, login, token refresh, profile management.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_token
from app.modules.auth.schemas import (
    AdminUserUpdateRequest,
    FamilyInviteRequest,
    LoginHistoryResponse,
    ProfileUpdateRequest,
    SessionDeviceResponse,
    TokenRefresh,
    TotpSetupResponse,
    TotpVerifyRequest,
    UserLogin,
    UserRegister,
)
from app.modules.auth.service import AuthService
from app.shared.types import success

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])
REFRESH_COOKIE_NAME = "william_refresh_token"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    max_age_seconds = settings.jwt_refresh_token_expire_days * 24 * 60 * 60
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=max_age_seconds,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
    )


async def get_current_user_id(
    authorization: str = Header(..., description="Bearer <token>"),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    """Extract and validate user ID from JWT or permanent API key."""
    from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

    from app.core.security import hash_api_key
    from app.shared.types import AuthenticationError

    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Invalid authorization header")
    token = authorization[7:].strip()

    if token.startswith("wos-"):
        from sqlalchemy import text

        key_hash = hash_api_key(token)
        result = await db.execute(
            text("SELECT user_id FROM auth.api_keys WHERE key_hash=:kh AND is_active=true"),
            {"kh": key_hash},
        )
        row = result.fetchone()
        if not row:
            raise AuthenticationError("Invalid API key")
        await db.execute(
            text("UPDATE auth.api_keys SET last_used=NOW() WHERE key_hash=:kh"),
            {"kh": key_hash},
        )
        await db.commit()
        return uuid.UUID(str(row[0]))

    try:
        payload = decode_token(token)
    except ExpiredSignatureError as e:
        raise AuthenticationError("Token expired") from e
    except InvalidTokenError as e:
        raise AuthenticationError("Invalid token") from e

    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")
    return uuid.UUID(payload["sub"])


@router.post("/register", status_code=201)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)) -> dict:
    service = AuthService(db)
    profile = await service.register(data)
    return success(profile.model_dump(mode="json"))


@router.post("/login")
async def login(
    data: UserLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    user_agent = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    tokens = await service.login(data, user_agent, ip)
    _set_refresh_cookie(response, tokens.refresh_token)
    return success(
        {
            "access_token": tokens.access_token,
            "token_type": "bearer",
            "expires_in": 900,
        }
    )


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    data: TokenRefresh | None = None,
) -> dict:
    service = AuthService(db)
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME) or (
        data.refresh_token if data else None
    )
    if not refresh_token:
        from app.shared.types import AuthenticationError

        raise AuthenticationError("Refresh token is required")

    tokens = await service.refresh_tokens(refresh_token)
    _set_refresh_cookie(response, tokens.refresh_token)
    return success(tokens.model_dump())


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        await service.revoke_refresh_token(refresh_token)
    _clear_refresh_cookie(response)
    return success({"logged_out": True})


@router.get("/me")
async def get_me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    profile = await service.get_profile(user_id)
    return success(profile.model_dump(mode="json"))


@router.patch("/profile")
async def update_profile(
    payload: ProfileUpdateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    profile = await service.update_profile(user_id=user_id, data=payload)
    return success(profile.model_dump(mode="json"))


@router.get("/admin/users")
async def admin_list_users(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    users = await service.admin_list_users(owner_user_id=user_id)
    return success([item.model_dump(mode="json") for item in users])


@router.patch("/admin/users/{target_user_id}")
async def admin_update_user(
    target_user_id: uuid.UUID,
    payload: AdminUserUpdateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    updated = await service.admin_update_user(
        owner_user_id=user_id,
        target_user_id=target_user_id,
        data=payload,
    )
    return success(updated.model_dump(mode="json"))


@router.delete("/admin/users/{target_user_id}")
async def admin_deactivate_user(
    target_user_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    updated = await service.admin_deactivate_user(
        owner_user_id=user_id,
        target_user_id=target_user_id,
    )
    return success(updated.model_dump(mode="json"))


@router.get("/admin/stats")
async def admin_stats(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    stats = await service.admin_stats(owner_user_id=user_id)
    return success(stats.model_dump(mode="json"))


@router.post("/family/invite")
async def invite_family_member(
    payload: FamilyInviteRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    response = await service.invite_family(owner_user_id=user_id, data=payload)
    return success(response)


@router.get("/2fa/setup")
async def setup_2fa(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    payload: TotpSetupResponse = TotpSetupResponse.model_validate(
        await service.generate_totp_setup(user_id)
    )
    return success(payload.model_dump(mode="json"))


@router.post("/2fa/verify")
async def verify_2fa(
    request: TotpVerifyRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    ok = await service.verify_totp(user_id=user_id, code=request.code)
    return success({"enabled": ok})


@router.get("/sessions")
async def list_sessions(
    request: Request,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    sessions = await service.list_sessions(user_id=user_id, current_refresh_token=refresh_token)
    payload = [
        SessionDeviceResponse.model_validate(item).model_dump(mode="json") for item in sessions
    ]
    return success(payload)


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    revoked = await service.revoke_session(user_id=user_id, session_id=session_id)
    return success({"revoked": revoked})


@router.get("/login-history")
async def login_history(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    limit: int = 25,
) -> dict:
    service = AuthService(db)
    rows = await service.list_login_history(user_id=user_id, limit=limit)
    payload = [LoginHistoryResponse.model_validate(row).model_dump(mode="json") for row in rows]
    return success(payload)


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


@router.post("/api-keys")
async def create_api_key(
    payload: ApiKeyCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    import secrets

    from sqlalchemy import text

    from app.core.security import hash_api_key

    raw_key = f"wos-{secrets.token_hex(24)}"
    key_hash = hash_api_key(raw_key)

    await db.execute(
        text("INSERT INTO auth.api_keys (user_id, key_hash, name) VALUES (:uid, :kh, :name)"),
        {"uid": str(user_id), "kh": key_hash, "name": payload.name},
    )
    await db.commit()
    return success(
        {
            "key": raw_key,
            "name": payload.name,
            "note": "Save this key — it won't be shown again",
        }
    )


@router.get("/api-keys")
async def list_api_keys(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy import text

    result = await db.execute(
        text(
            "SELECT id, name, LEFT(key_hash, 10) || '...' AS fingerprint, created_at, last_used "
            "FROM auth.api_keys WHERE user_id=:uid ORDER BY created_at DESC"
        ),
        {"uid": str(user_id)},
    )
    return success([dict(r._mapping) for r in result.fetchall()])

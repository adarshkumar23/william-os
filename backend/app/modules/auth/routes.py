"""
WILLIAM OS — Auth Routes
Registration, login, token refresh, profile management.
"""

from __future__ import annotations

import uuid
import structlog
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_token
from app.modules.auth.schemas import (
    LoginHistoryResponse,
    OnboardingCompleteRequest,
    SessionDeviceResponse,
    TokenRefresh,
    TotpSetupResponse,
    TotpVerifyRequest,
    UserLogin,
    UserRegister,
)
from app.modules.auth.service import AuthService
from app.shared.types import success
from fastapi import APIRouter, Depends, Header, Request, Response
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
) -> uuid.UUID:
    """Extract and validate user ID from JWT."""
    if not authorization.startswith("Bearer "):
        from app.shared.types import AuthenticationError

        raise AuthenticationError("Invalid authorization header")
    token = authorization[7:]
    payload = decode_token(token)
    if payload.get("type") != "access":
        from app.shared.types import AuthenticationError

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
    return success(tokens.model_dump())


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


@router.get("/onboarding/status")
async def get_onboarding_status(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    status = await service.get_onboarding_status(user_id)
    return success(status.model_dump(mode="json"))


@router.post("/onboarding/complete")
async def complete_onboarding(
    data: OnboardingCompleteRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    status = await service.complete_onboarding(user_id=user_id, data=data)
    return success(status.model_dump(mode="json"))


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
        SessionDeviceResponse.model_validate(item).model_dump(mode="json")
        for item in sessions
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
    payload = [
        LoginHistoryResponse.model_validate(row).model_dump(mode="json")
        for row in rows
    ]
    return success(payload)

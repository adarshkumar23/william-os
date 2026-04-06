"""
WILLIAM OS — Auth Routes
Registration, login, token refresh, profile management.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.modules.auth.schemas import (
    TokenRefresh,
    TokenResponse,
    UserLogin,
    UserProfile,
    UserRegister,
)
from app.modules.auth.service import AuthService
from app.shared.types import success

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


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
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    user_agent = request.headers.get("user-agent", "")
    ip = request.client.host if request.client else ""
    tokens = await service.login(data, user_agent, ip)
    return success(tokens.model_dump())


@router.post("/refresh")
async def refresh(data: TokenRefresh, db: AsyncSession = Depends(get_db)) -> dict:
    service = AuthService(db)
    tokens = await service.refresh_tokens(data.refresh_token)
    return success(tokens.model_dump())


@router.get("/me")
async def get_me(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = AuthService(db)
    profile = await service.get_profile(user_id)
    return success(profile.model_dump(mode="json"))

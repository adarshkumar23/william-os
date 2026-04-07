"""WILLIAM OS - API secret rotation endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.secrets.schemas import SecretMetadataResponse, SecretRotateRequest
from app.modules.secrets.service import SecretsService
from app.shared.types import success

router = APIRouter(prefix="/security/secrets", tags=["Security"])


@router.get("")
async def list_secrets(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SecretsService(db)
    rows = await service.list_secrets(user_id=user_id)
    payload = [SecretMetadataResponse.model_validate(row).model_dump(mode="json") for row in rows]
    return success(payload)


@router.post("/rotate")
async def rotate_secret(
    request: SecretRotateRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SecretsService(db)
    row = await service.rotate_secret(user_id=user_id, request=request)
    return success(SecretMetadataResponse.model_validate(row).model_dump(mode="json"))


@router.delete("/{secret_id}")
async def revoke_secret(
    secret_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SecretsService(db)
    revoked = await service.revoke_secret(user_id=user_id, secret_id=secret_id)
    return success({"revoked": revoked})

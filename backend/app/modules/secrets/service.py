"""WILLIAM OS - API secret rotation and retrieval service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_api_secret, encrypt_api_secret
from app.modules.secrets.models import ApiSecret
from app.modules.secrets.schemas import SecretRotateRequest
from app.shared.types import NotFoundError


class SecretsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_secrets(self, user_id: uuid.UUID) -> list[ApiSecret]:
        result = await self.db.execute(
            select(ApiSecret)
            .where(ApiSecret.user_id == user_id)
            .order_by(ApiSecret.provider.asc(), ApiSecret.version.desc())
        )
        return list(result.scalars().all())

    async def rotate_secret(self, user_id: uuid.UUID, request: SecretRotateRequest) -> ApiSecret:
        result = await self.db.execute(
            select(ApiSecret)
            .where(ApiSecret.user_id == user_id, ApiSecret.provider == request.provider)
            .order_by(ApiSecret.version.desc())
            .limit(1)
        )
        previous = result.scalar_one_or_none()

        if previous is not None:
            previous.is_active = False

        key_hint = self._secret_hint(request.plaintext_key)
        row = ApiSecret(
            user_id=user_id,
            provider=request.provider,
            key_ciphertext=encrypt_api_secret(request.plaintext_key),
            key_hint=key_hint,
            version=1 if previous is None else previous.version + 1,
            is_active=True,
            rotated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def revoke_secret(self, user_id: uuid.UUID, secret_id: uuid.UUID) -> bool:
        row = await self.db.get(ApiSecret, secret_id)
        if row is None or row.user_id != user_id:
            return False

        row.is_active = False
        await self.db.flush()
        return True

    async def get_active_secret_plaintext(self, user_id: uuid.UUID, provider: str) -> str:
        result = await self.db.execute(
            select(ApiSecret)
            .where(
                ApiSecret.user_id == user_id,
                ApiSecret.provider == provider,
                ApiSecret.is_active.is_(True),
            )
            .order_by(ApiSecret.version.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("ApiSecret", provider)

        return decrypt_api_secret(row.key_ciphertext)

    @staticmethod
    def _secret_hint(plaintext: str) -> str:
        clean = plaintext.strip()
        if len(clean) <= 6:
            return "***"
        return f"{clean[:3]}...{clean[-3:]}"

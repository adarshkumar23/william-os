"""
WILLIAM OS — Rate Limiting Tests
Unit tests for Redis-backed sliding-window middleware behavior.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app.core.config import get_settings
from app.core.rate_limit import RateLimitMiddleware
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class _FakePipeline:
    def __init__(self, client: _FakeRedis) -> None:
        self.client = client
        self.ops: list[tuple[str, tuple]] = []

    def incr(self, key: str) -> _FakePipeline:
        self.ops.append(("incr", (key,)))
        return self

    def expire(self, key: str, ttl: int) -> _FakePipeline:
        self.ops.append(("expire", (key, ttl)))
        return self

    async def execute(self) -> list:
        results = []
        for op, args in self.ops:
            if op == "incr":
                results.append(await self.client.incr(*args))
            elif op == "expire":
                results.append(await self.client.expire(*args))
        self.ops.clear()
        return results


class _FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, int] = {}
        self.expires_at: dict[str, int] = {}

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        _ = transaction
        return _FakePipeline(self)

    async def incr(self, key: str) -> int:
        self._cleanup()
        value = self.data.get(key, 0) + 1
        self.data[key] = value
        return value

    async def expire(self, key: str, ttl: int) -> bool:
        self.expires_at[key] = self._now() + ttl
        return True

    async def mget(self, keys: list[str]) -> list[str | None]:
        self._cleanup()
        return [str(self.data[key]) if key in self.data else None for key in keys]

    def _cleanup(self) -> None:
        now = self._now()
        expired_keys = [key for key, until in self.expires_at.items() if until <= now]
        for key in expired_keys:
            self.data.pop(key, None)
            self.expires_at.pop(key, None)

    @staticmethod
    def _now() -> int:
        return int(datetime.now(UTC).timestamp())


def _build_test_app(
    *,
    redis_client: _FakeRedis,
    unauthenticated_limit: int = 60,
    authenticated_limit: int = 120,
    burst_allowance: int = 10,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        redis_client=redis_client,
        unauthenticated_limit=unauthenticated_limit,
        authenticated_limit=authenticated_limit,
        burst_allowance=burst_allowance,
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/v1/ping")
    async def ping() -> dict:
        return {"ok": True}

    return app


def _access_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "type": "access",
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


@pytest.mark.asyncio
async def test_rate_limit_under_limit_passes() -> None:
    app = _build_test_app(
        redis_client=_FakeRedis(),
        unauthenticated_limit=2,
        burst_allowance=1,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/api/v1/ping")
        r2 = await client.get("/api/v1/ping")
        r3 = await client.get("/api/v1/ping")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_over_limit_returns_429() -> None:
    app = _build_test_app(
        redis_client=_FakeRedis(),
        unauthenticated_limit=2,
        burst_allowance=1,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/v1/ping")
        await client.get("/api/v1/ping")
        await client.get("/api/v1/ping")
        blocked = await client.get("/api/v1/ping")

    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "60"


@pytest.mark.asyncio
async def test_rate_limit_different_users_independent() -> None:
    app = _build_test_app(
        redis_client=_FakeRedis(),
        authenticated_limit=2,
        burst_allowance=0,
    )
    transport = ASGITransport(app=app)
    token_a = _access_token(uuid.uuid4())
    token_b = _access_token(uuid.uuid4())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ok_a1 = await client.get("/api/v1/ping", headers={"Authorization": f"Bearer {token_a}"})
        ok_a2 = await client.get("/api/v1/ping", headers={"Authorization": f"Bearer {token_a}"})
        ok_b1 = await client.get("/api/v1/ping", headers={"Authorization": f"Bearer {token_b}"})
        ok_b2 = await client.get("/api/v1/ping", headers={"Authorization": f"Bearer {token_b}"})
        blocked_a = await client.get(
            "/api/v1/ping",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    assert ok_a1.status_code == 200
    assert ok_a2.status_code == 200
    assert ok_b1.status_code == 200
    assert ok_b2.status_code == 200
    assert blocked_a.status_code == 429


@pytest.mark.asyncio
async def test_health_endpoint_is_exempt() -> None:
    app = _build_test_app(
        redis_client=_FakeRedis(),
        unauthenticated_limit=0,
        burst_allowance=0,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        blocked = await client.get("/api/v1/ping")
        health_1 = await client.get("/health")
        health_2 = await client.get("/health")

    assert blocked.status_code == 429
    assert health_1.status_code == 200
    assert health_2.status_code == 200

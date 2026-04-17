"""WILLIAM OS — Rate Limiting Middleware.
H4 fix: single Redis sorted set per identifier instead of N independent keys.
H5 fix: uses decode_token_safe (non-raising).
"""

from __future__ import annotations

import time

import redis.asyncio as redis
import structlog
from fastapi.responses import ORJSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.security import decode_token_safe

logger = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limit via Redis sorted set."""

    def __init__(
        self,
        app,
        *,
        redis_url: str | None = None,
        redis_client=None,
        unauthenticated_limit: int = 60,
        authenticated_limit: int = 120,
        burst_allowance: int = 10,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        s = get_settings()
        self.window_seconds = window_seconds
        self.unauthenticated_limit = unauthenticated_limit
        self.authenticated_limit = authenticated_limit
        self.burst_allowance = burst_allowance
        self.redis = redis_client or redis.from_url(redis_url or s.redis_url, decode_responses=True)

    async def dispatch(self, request, call_next) -> Response:
        if request.url.path in {"/health", "/metrics"}:
            return await call_next(request)

        identifier, limit = self._resolve_identifier_and_limit(request)
        allowed, retry_after = await self._check_rate_limit(identifier=identifier, limit=limit)

        if not allowed:
            return ORJSONResponse(
                status_code=429,
                content={
                    "ok": False,
                    "data": None,
                    "error": "Rate limit exceeded",
                    "meta": {"identifier": identifier, "retry_after_seconds": retry_after},
                },
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)

    def _resolve_identifier_and_limit(self, request) -> tuple[str, int]:
        ip = request.client.host if request.client else "unknown"
        auth = request.headers.get("authorization")
        if not auth or not auth.startswith("Bearer "):
            return f"ip:{ip}", self.unauthenticated_limit

        token = auth[7:]
        if token.startswith("wos-"):
            # API keys — rate-limit by key fingerprint
            return f"apikey:{token[:16]}", self.authenticated_limit

        payload = decode_token_safe(token)
        if payload and payload.get("type") == "access" and payload.get("sub"):
            return f"user:{payload['sub']}", self.authenticated_limit
        return f"ip:{ip}", self.unauthenticated_limit

    async def _check_rate_limit(self, identifier: str, limit: int) -> tuple[bool, int]:
        """Sliding window via sorted set — O(log N) per op instead of 61 MGETs."""
        now_ms = int(time.time() * 1000)
        window_ms = self.window_seconds * 1000
        cutoff = now_ms - window_ms
        key = f"ratelimit:{identifier}"
        hard_limit = limit + self.burst_allowance

        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                # Drop entries older than window
                pipe.zremrangebyscore(key, 0, cutoff)
                # Record this request
                pipe.zadd(key, {f"{now_ms}:{id(pipe)}": now_ms})
                # Count current window
                pipe.zcard(key)
                # Expire the key so it self-cleans if user stops sending
                pipe.expire(key, self.window_seconds + 5)
                results = await pipe.execute()
            count = int(results[2])
        except Exception as exc:
            # Redis unavailable = fail open (log but do not block users)
            logger.warning("rate_limit_redis_unavailable", identifier=identifier, error=str(exc))
            return True, 0

        if count > hard_limit:
            return False, self.window_seconds
        return True, 0

"""
WILLIAM OS — Rate Limiting Middleware
Redis-backed sliding window limits for unauthenticated IP and authenticated users.
"""

from __future__ import annotations

import time

import redis.asyncio as redis
import structlog
from fastapi.responses import ORJSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.security import decode_token

logger = structlog.get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply per-IP and per-user request limits using a sliding 60-second window."""

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
        settings = get_settings()
        self.window_seconds = window_seconds
        self.unauthenticated_limit = unauthenticated_limit
        self.authenticated_limit = authenticated_limit
        self.burst_allowance = burst_allowance
        self.redis = redis_client or redis.from_url(
            redis_url or settings.redis_url,
            decode_responses=True,
        )

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
                    "meta": {
                        "identifier": identifier,
                        "retry_after_seconds": retry_after,
                    },
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    def _resolve_identifier_and_limit(self, request) -> tuple[str, int]:
        ip = request.client.host if request.client else "unknown"
        authorization = request.headers.get("authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return f"ip:{ip}", self.unauthenticated_limit

        token = authorization[7:]
        try:
            payload = decode_token(token)
            if payload.get("type") == "access" and payload.get("sub"):
                return f"user:{payload['sub']}", self.authenticated_limit
        except Exception:
            return f"ip:{ip}", self.unauthenticated_limit

        return f"ip:{ip}", self.unauthenticated_limit

    async def _check_rate_limit(self, identifier: str, limit: int) -> tuple[bool, int]:
        now = int(time.time())
        current_key = f"ratelimit:{identifier}:{now}"

        try:
            pipeline = self.redis.pipeline(transaction=True)
            pipeline.incr(current_key)
            pipeline.expire(current_key, self.window_seconds)
            await pipeline.execute()

            keys = [
                f"ratelimit:{identifier}:{window}"
                for window in range(now - self.window_seconds + 1, now + 1)
            ]
            values = await self.redis.mget(keys)
            total_requests = sum(int(value or 0) for value in values)
        except Exception as exc:
            logger.warning(
                "rate_limit_redis_unavailable",
                identifier=identifier,
                error=str(exc),
            )
            return True, 0

        hard_limit = limit + self.burst_allowance
        if total_requests > hard_limit:
            return False, self.window_seconds

        return True, 0
"""
WILLIAM OS — Offline Fallback Middleware
Graceful degraded mode with cached GET responses and queued mutation replay.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import redis.asyncio as redis
import structlog
from fastapi.responses import ORJSONResponse, Response
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.security import decode_token

logger = structlog.get_logger(__name__)


class ReplayQueue:
    """Append-only JSONL queue for deferred mutation requests."""

    def __init__(self, queue_path: Path | None = None) -> None:
        if queue_path is not None:
            self.queue_path = queue_path
            return

        settings = get_settings()
        self.queue_path = Path(settings.offline_queue_path).expanduser()

    async def enqueue(self, item: dict) -> bool:
        try:
            self.queue_path.parent.mkdir(parents=True, exist_ok=True)
            with self.queue_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(item) + "\n")
            return True
        except Exception:
            return False

    async def read_all(self) -> list[dict]:
        if not self.queue_path.exists():
            return []
        items: list[dict] = []
        with self.queue_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                    if isinstance(parsed, dict):
                        items.append(parsed)
                except json.JSONDecodeError:
                    continue
        return items

    async def rewrite(self, items: list[dict]) -> None:
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        with self.queue_path.open("w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item) + "\n")

    async def replay(self, replay_func) -> dict:
        entries = await self.read_all()
        if not entries:
            return {"replayed": 0, "pending": 0}

        pending: list[dict] = []
        replayed = 0
        for entry in entries:
            try:
                ok = await replay_func(entry)
            except Exception:
                ok = False
            if ok:
                replayed += 1
            else:
                pending.append(entry)

        await self.rewrite(pending)
        return {"replayed": replayed, "pending": len(pending)}


class OfflineFallbackMiddleware:
    """Serve cached GET responses and queue mutations during degraded mode."""

    def __init__(
        self,
        app,
        *,
        redis_client=None,
        replay_queue: ReplayQueue | None = None,
        cache_ttl_seconds: int = 120,
        health_check_interval_seconds: int = 5,
        strict_connectivity: bool | None = None,
        redis_health_check=None,
        postgres_health_check=None,
    ) -> None:
        self.app = app
        settings = get_settings()
        self.redis = redis_client or redis.from_url(settings.redis_url, decode_responses=True)
        self.replay_queue = replay_queue or ReplayQueue()
        self.cache_ttl_seconds = cache_ttl_seconds
        self.health_check_interval_seconds = health_check_interval_seconds
        self.strict_connectivity = (
            settings.is_production if strict_connectivity is None else strict_connectivity
        )
        self.redis_health_check = redis_health_check
        self.postgres_health_check = postgres_health_check

        self.degraded_mode = False
        self.degraded_reason: str | None = None
        self._last_health_check = 0.0
        self._cache: dict[str, tuple[float, int, dict[str, str], bytes]] = {}

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        from starlette.requests import Request

        request = Request(scope, receive=receive)
        await self._refresh_connectivity_if_due()
        self._sync_app_state(request.app)

        if not self.degraded_mode:
            replay_summary = await self.replay_queue.replay(self._replay_entry)
            if replay_summary.get("replayed", 0) > 0:
                logger.info("offline_queue_replayed", **replay_summary)

        if request.url.path in {"/health", "/metrics"}:
            await self.app(scope, receive, send)
            return

        if self.degraded_mode:
            response = await self._handle_degraded_request(request)
            await response(scope, receive, send)
            return

        if request.method.upper() == "GET":
            response = await self._call_downstream(request)
            await self._cache_response(request, response)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    async def _handle_degraded_request(self, request):
        method = request.method.upper()
        if method == "GET":
            cached = self._cache_lookup(request)
            if cached is not None:
                status_code, headers, body = cached
                merged_headers = {**headers, "X-Offline-Cache": "HIT"}
                return Response(
                    content=body,
                    status_code=status_code,
                    headers=merged_headers,
                    media_type=headers.get("content-type"),
                )

            return ORJSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "data": None,
                    "error": "Service in degraded mode and no cached response available",
                    "meta": {"degraded": True, "reason": self.degraded_reason},
                },
            )

        if method in {"POST", "PATCH", "PUT", "DELETE"}:
            body = await request.body()
            queued = await self.replay_queue.enqueue(
                {
                    "method": method,
                    "path": request.url.path,
                    "query": request.url.query,
                    "headers": {
                        "authorization": request.headers.get("authorization"),
                        "content-type": request.headers.get("content-type", "application/json"),
                    },
                    "body": body.decode("utf-8", errors="ignore"),
                    "queued_at": int(time.time()),
                }
            )
            if not queued:
                return ORJSONResponse(
                    status_code=503,
                    content={
                        "ok": False,
                        "data": None,
                        "error": "Service in degraded mode and mutation queue is unavailable",
                        "meta": {"degraded": True, "reason": self.degraded_reason},
                    },
                )
            return ORJSONResponse(
                status_code=202,
                content={
                    "ok": True,
                    "data": {"queued": True},
                    "error": None,
                    "meta": {"degraded": True, "reason": self.degraded_reason},
                },
            )

        return ORJSONResponse(
            status_code=503,
            content={
                "ok": False,
                "data": None,
                "error": "Service unavailable in degraded mode",
                "meta": {"degraded": True, "reason": self.degraded_reason},
            },
        )

    async def _refresh_connectivity_if_due(self) -> None:
        now = time.time()
        if now - self._last_health_check < self.health_check_interval_seconds:
            return

        self._last_health_check = now
        redis_ok = await self._check_redis()
        postgres_ok = await self._check_postgres()

        if not self.strict_connectivity:
            self.degraded_mode = False
            self.degraded_reason = None
            return

        if redis_ok and postgres_ok:
            self.degraded_mode = False
            self.degraded_reason = None
        else:
            self.degraded_mode = True
            if not redis_ok and not postgres_ok:
                self.degraded_reason = "redis_unreachable+postgres_unreachable"
            elif not redis_ok:
                self.degraded_reason = "redis_unreachable"
            else:
                self.degraded_reason = "postgres_unreachable"

        # State sync happens per-request using request.app.

    async def _check_redis(self) -> bool:
        if self.redis_health_check is not None:
            return bool(await self.redis_health_check())
        try:
            pong = await self.redis.ping()
            return bool(pong)
        except Exception as exc:
            logger.warning("offline_redis_check_failed", error=str(exc))
            return False

    async def _check_postgres(self) -> bool:
        if self.postgres_health_check is not None:
            return bool(await self.postgres_health_check())
        try:
            async with async_session_factory() as db:
                await db.execute(text("SELECT 1"))
            return True
        except Exception as exc:
            logger.warning("offline_postgres_check_failed", error=str(exc))
            return False

    async def _call_downstream(self, request) -> Response:
        body = await request.body()
        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://offline-local") as client:
            response = await client.request(
                method=request.method,
                url=request.url.path,
                params=request.query_params,
                content=body,
                headers=dict(request.headers),
            )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type"),
        )

    async def _cache_response(self, request, response: Response) -> None:
        if request.method.upper() != "GET":
            return
        if response.status_code >= 400:
            return

        cache_key = self._cache_key(request)
        headers = {"content-type": response.headers.get("content-type", "application/json")}
        self._cache[cache_key] = (
            time.time() + self.cache_ttl_seconds,
            response.status_code,
            headers,
            bytes(response.body),
        )

    def _cache_lookup(self, request):
        cache_key = self._cache_key(request)
        row = self._cache.get(cache_key)
        if row is None:
            return None

        expires_at, status_code, headers, body = row
        if time.time() > expires_at:
            self._cache.pop(cache_key, None)
            return None

        return status_code, headers, body

    def _cache_key(self, request) -> str:
        identifier = self._request_identifier(request)
        query = request.url.query
        if query:
            return f"{identifier}:{request.url.path}?{query}"
        return f"{identifier}:{request.url.path}"

    def _request_identifier(self, request) -> str:
        authorization = request.headers.get("authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:]
            try:
                payload = decode_token(token)
                if payload.get("sub"):
                    return f"user:{payload['sub']}"
            except Exception:
                pass

        ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    async def _replay_entry(self, entry: dict) -> bool:
        method = str(entry.get("method") or "").upper()
        path = str(entry.get("path") or "")
        if method not in {"POST", "PATCH", "PUT", "DELETE"} or not path:
            return True

        params = {}
        query = str(entry.get("query") or "")
        if query:
            for pair in query.split("&"):
                if "=" not in pair:
                    continue
                key, value = pair.split("=", 1)
                params[key] = value

        headers = entry.get("headers") or {}
        body = str(entry.get("body") or "")

        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://offline-replay") as client:
            response = await client.request(
                method=method,
                url=path,
                params=params,
                content=body.encode("utf-8"),
                headers={
                    "authorization": headers.get("authorization") or "",
                    "content-type": headers.get("content-type") or "application/json",
                },
            )
        return response.status_code < 500

    def _sync_app_state(self, app) -> None:
        app_state = app.state
        app_state.degraded_mode = self.degraded_mode
        app_state.degraded_reason = self.degraded_reason

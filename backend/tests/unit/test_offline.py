"""
WILLIAM OS — Offline Middleware Tests
Unit tests for degraded mode, mutation replay queue, and cached GET fallback.
"""

from __future__ import annotations

import pytest
from app.core.offline import OfflineFallbackMiddleware, ReplayQueue
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def _build_app(
    *,
    queue_path,
    redis_check,
    postgres_check,
    counter: dict[str, int],
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        OfflineFallbackMiddleware,
        replay_queue=ReplayQueue(queue_path),
        cache_ttl_seconds=300,
        health_check_interval_seconds=0,
        strict_connectivity=True,
        redis_health_check=redis_check,
        postgres_health_check=postgres_check,
    )

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "degraded_mode": bool(getattr(app.state, "degraded_mode", False)),
            "degraded_reason": getattr(app.state, "degraded_reason", None),
        }

    @app.get("/api/v1/value")
    async def value() -> dict:
        counter["value_reads"] = counter.get("value_reads", 0) + 1
        return {"value": counter["value_reads"]}

    @app.get("/api/v1/uncached")
    async def uncached() -> dict:
        return {"ok": True}

    @app.post("/api/v1/mutate")
    async def mutate() -> dict:
        counter["mutations"] = counter.get("mutations", 0) + 1
        return {"mutations": counter["mutations"]}

    return app


@pytest.mark.asyncio
async def test_degraded_mode_detected_and_reported(tmp_path) -> None:
    async def redis_check() -> bool:
        return False

    async def postgres_check() -> bool:
        return True

    app = _build_app(
        queue_path=tmp_path / "offline_queue.jsonl",
        redis_check=redis_check,
        postgres_check=postgres_check,
        counter={},
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["degraded_mode"] is True
    assert payload["degraded_reason"] == "redis_unreachable"


@pytest.mark.asyncio
async def test_mutation_queued_then_replayed_when_healthy(tmp_path) -> None:
    state = {"healthy": False}
    counter: dict[str, int] = {}

    async def redis_check() -> bool:
        return state["healthy"]

    async def postgres_check() -> bool:
        return state["healthy"]

    queue_path = tmp_path / "offline_queue.jsonl"
    app = _build_app(
        queue_path=queue_path,
        redis_check=redis_check,
        postgres_check=postgres_check,
        counter=counter,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        queued = await client.post("/api/v1/mutate", json={"x": 1})
        assert queued.status_code == 202
        assert counter.get("mutations", 0) == 0

        state["healthy"] = True
        health = await client.get("/health")
        assert health.status_code == 200

    lines = queue_path.read_text(encoding="utf-8").strip()
    assert lines == ""
    assert counter.get("mutations", 0) == 1


@pytest.mark.asyncio
async def test_cache_hit_and_miss_in_degraded_mode(tmp_path) -> None:
    state = {"healthy": True}
    counter: dict[str, int] = {}

    async def redis_check() -> bool:
        return state["healthy"]

    async def postgres_check() -> bool:
        return state["healthy"]

    app = _build_app(
        queue_path=tmp_path / "offline_queue.jsonl",
        redis_check=redis_check,
        postgres_check=postgres_check,
        counter=counter,
    )
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        warm = await client.get("/api/v1/value")
        assert warm.status_code == 200
        assert warm.json()["value"] == 1

        state["healthy"] = False
        cached = await client.get("/api/v1/value")
        uncached = await client.get("/api/v1/uncached")

    assert cached.status_code == 200
    assert cached.json()["value"] == 1
    assert cached.headers.get("X-Offline-Cache") == "HIT"

    assert uncached.status_code == 503
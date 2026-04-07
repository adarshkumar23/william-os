"""
WILLIAM OS — Gamification API Integration Tests
Validates profile, xp history, and records endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _auth_headers(client: AsyncClient, email: str, username: str) -> dict[str, str]:
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "StrongPass1",
            "full_name": "Gamification Tester",
        },
    )
    assert register_resp.status_code == 201

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "StrongPass1",
        },
    )
    assert login_resp.status_code == 200

    token = login_resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestGamificationEndpoints:
    @pytest.mark.asyncio
    async def test_profile_returns_level_and_momentum(self, client: AsyncClient):
        headers = await _auth_headers(
            client,
            email="gamification-profile@william.os",
            username="gamificationprofile",
        )

        resp = await client.get("/api/v1/gamification/profile", headers=headers)
        assert resp.status_code == 200
        body = resp.json()

        assert body["ok"] is True
        assert body["error"] is None

        profile = body["data"]
        assert "level_progress" in profile
        assert "weekly_momentum" in profile
        assert "records" in profile
        assert "recent_xp_events" in profile

        assert profile["level_progress"]["level"] >= 1
        assert profile["level_progress"]["total_xp"] >= 0

    @pytest.mark.asyncio
    async def test_xp_history_and_records_endpoints_return_lists(self, client: AsyncClient):
        headers = await _auth_headers(
            client,
            email="gamification-history@william.os",
            username="gamificationhistory",
        )

        history_resp = await client.get("/api/v1/gamification/xp-history", headers=headers)
        assert history_resp.status_code == 200
        history_body = history_resp.json()

        assert history_body["ok"] is True
        history = history_body["data"]
        assert isinstance(history, list)

        records_resp = await client.get("/api/v1/gamification/records", headers=headers)
        assert records_resp.status_code == 200
        records_body = records_resp.json()

        assert records_body["ok"] is True
        records = records_body["data"]
        assert isinstance(records, list)

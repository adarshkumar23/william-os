"""
WILLIAM OS — Morning Briefing API Integration Tests
Validates daily briefing retrieval and manual send flow.
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
            "full_name": "Briefing Tester",
            "timezone": "Asia/Kolkata",
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


class TestMorningBriefingEndpoints:
    @pytest.mark.asyncio
    async def test_get_today_briefing_returns_expected_sections(self, client: AsyncClient):
        headers = await _auth_headers(
            client,
            email="briefing-today@william.os",
            username="briefingtoday",
        )

        resp = await client.get("/api/v1/briefing/today", headers=headers)
        assert resp.status_code == 200

        body = resp.json()
        assert body["ok"] is True
        assert body["error"] is None

        data = body["data"]
        expected_keys = {
            "generated_at",
            "sleep_quality",
            "today_schedule",
            "priority_habits",
            "missed_medicines",
            "upcoming_deadlines",
            "market_watchlist_movement",
            "energy_prediction",
            "life_score",
            "ai_recommendation_of_day",
        }
        assert expected_keys.issubset(set(data.keys()))

        assert isinstance(data["today_schedule"], list)
        assert isinstance(data["priority_habits"], list)
        assert isinstance(data["missed_medicines"], list)
        assert isinstance(data["upcoming_deadlines"], list)
        assert isinstance(data["market_watchlist_movement"], dict)
        assert isinstance(data["life_score"], dict)
        assert isinstance(data["ai_recommendation_of_day"], str)
        assert data["ai_recommendation_of_day"]

    @pytest.mark.asyncio
    async def test_send_now_briefing_logs_telegram_and_in_app(self, client: AsyncClient):
        headers = await _auth_headers(
            client,
            email="briefing-send@william.os",
            username="briefingsend",
        )

        resp = await client.post("/api/v1/briefing/send-now", headers=headers)
        assert resp.status_code == 200

        body = resp.json()
        assert body["ok"] is True
        assert body["error"] is None

        data = body["data"]
        assert "briefing" in data
        assert "telegram" in data
        assert "in_app" in data

        telegram = data["telegram"]
        in_app = data["in_app"]

        assert telegram["channel"] == "telegram"
        assert telegram["notification_type"] == "morning_briefing"
        assert in_app["channel"] == "in_app"
        assert in_app["notification_type"] == "morning_briefing"
        assert in_app["delivered"] is True

"""
WILLIAM OS — Intelligence API Integration Tests
Exercises intelligence endpoints with authenticated requests.
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
            "full_name": "Intelligence Tester",
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


class TestIntelligenceEndpoints:
    @pytest.mark.asyncio
    async def test_get_signals_returns_envelope(self, client: AsyncClient):
        headers = await _auth_headers(
            client,
            email="intel-signals@william.os",
            username="intelsignals",
        )

        # Force a signal collection cycle before listing stored signals.
        adjustments_resp = await client.get("/api/v1/intelligence/adjustments", headers=headers)
        assert adjustments_resp.status_code == 200

        resp = await client.get("/api/v1/intelligence/signals", headers=headers)
        assert resp.status_code == 200

        body = resp.json()
        assert body["ok"] is True
        assert body["error"] is None
        assert isinstance(body["data"], list)
        assert len(body["data"]) > 0

    @pytest.mark.asyncio
    async def test_get_adjustments_returns_envelope(self, client: AsyncClient):
        headers = await _auth_headers(
            client,
            email="intel-adjustments@william.os",
            username="inteladjustments",
        )

        resp = await client.get("/api/v1/intelligence/adjustments", headers=headers)
        assert resp.status_code == 200

        body = resp.json()
        assert body["ok"] is True
        assert body["error"] is None
        assert isinstance(body["data"], dict)
        assert isinstance(body["data"]["count"], int)
        assert isinstance(body["data"]["adjustments"], dict)

    @pytest.mark.asyncio
    async def test_post_rule_creates_rule(self, client: AsyncClient):
        headers = await _auth_headers(
            client,
            email="intel-rules@william.os",
            username="intelrules",
        )

        payload = {
            "trigger_module": "sleep",
            "trigger_condition": {
                "signal_type": "energy",
                "operator": "lt",
                "threshold": 40,
                "target_field": "pace_modifier",
            },
            "affected_module": "study",
            "adjustment_type": "multiply",
            "adjustment_value": 0.8,
            "is_active": True,
        }

        resp = await client.post("/api/v1/intelligence/rules", json=payload, headers=headers)
        assert resp.status_code == 201

        body = resp.json()
        assert body["ok"] is True
        assert body["error"] is None
        assert body["data"]["trigger_module"] == "sleep"
        assert body["data"]["affected_module"] == "study"
        assert body["data"]["adjustment_type"] == "multiply"
        assert body["data"]["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_life_score_returns_envelope(self, client: AsyncClient):
        headers = await _auth_headers(
            client,
            email="intel-life-score@william.os",
            username="intellifescore",
        )

        resp = await client.get("/api/v1/intelligence/life-score", headers=headers)
        assert resp.status_code == 200

        body = resp.json()
        assert body["ok"] is True
        assert body["error"] is None
        assert isinstance(body["data"]["score"], (int, float))
        assert isinstance(body["data"]["component_scores"], dict)
        assert isinstance(body["data"]["explanation"], str)
        assert body["data"]["explanation"]

    @pytest.mark.asyncio
    async def test_get_life_score_history_returns_list(self, client: AsyncClient):
        headers = await _auth_headers(
            client,
            email="intel-life-history@william.os",
            username="intellifehistory",
        )

        compute_resp = await client.get("/api/v1/intelligence/life-score", headers=headers)
        assert compute_resp.status_code == 200

        resp = await client.get("/api/v1/intelligence/life-score/history?days=30", headers=headers)
        assert resp.status_code == 200

        body = resp.json()
        assert body["ok"] is True
        assert body["error"] is None
        assert isinstance(body["data"], list)
        assert len(body["data"]) >= 1
        assert "score" in body["data"][0]
        assert "computed_at" in body["data"][0]

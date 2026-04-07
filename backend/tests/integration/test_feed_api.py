"""WILLIAM OS - Activity Feed API Integration Tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from app.modules.auth.models import User
from app.modules.decisions.models import Decision
from app.modules.gamification.models import XPEvent
from app.modules.intelligence.models import LifeScore
from sqlalchemy import select

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def _auth_context(
    client: AsyncClient,
    db_session: AsyncSession,
    email: str,
    username: str,
) -> tuple[dict[str, str], str]:
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "StrongPass1",
            "full_name": "Feed Tester",
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
    user_result = await db_session.execute(select(User).where(User.email == email).limit(1))
    user = user_result.scalar_one()
    return {"Authorization": f"Bearer {token}"}, str(user.id)


class TestActivityFeedEndpoints:
    @pytest.mark.asyncio
    async def test_feed_returns_cursor_page_and_orders_latest_first(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        headers, user_id_raw = await _auth_context(
            client,
            db_session,
            email="feed-page@william.os",
            username="feedpage",
        )

        user_uuid = uuid.UUID(user_id_raw)
        now = datetime.now(UTC).replace(microsecond=0)

        db_session.add(
            Decision(
                user_id=user_uuid,
                title="Select backend queue",
                description="Pick worker queue strategy for feed rollouts",
                decision_type="architecture",
                status="decided",
                chosen_option="redis-celery",
                chosen_at=now - timedelta(hours=3),
            )
        )
        db_session.add(
            LifeScore(
                user_id=user_uuid,
                score=78.0,
                component_scores={"sleep": 72.0, "habits": 80.0},
                explanation="Stable rhythm with moderate recovery debt.",
                computed_at=now - timedelta(hours=2),
            )
        )
        db_session.add(
            XPEvent(
                user_id=user_uuid,
                source_module="habits",
                action="habit_checkin",
                xp_earned=15,
                earned_at=now - timedelta(hours=1),
            )
        )
        await db_session.flush()

        first_page_resp = await client.get("/api/v1/feed", params={"limit": 2}, headers=headers)
        assert first_page_resp.status_code == 200

        first_page_body = first_page_resp.json()
        assert first_page_body["ok"] is True

        first_page = first_page_body["data"]
        assert isinstance(first_page["items"], list)
        assert len(first_page["items"]) == 2
        assert first_page["has_more"] is True
        assert isinstance(first_page["next_cursor"], str)

        first_items = first_page["items"]
        assert first_items[0]["action"] == "xp_earned"
        assert first_items[1]["action"] == "life_score_changed"

        required = {"event_id", "timestamp", "module", "action", "summary", "icon_key", "xp_earned"}
        assert required.issubset(set(first_items[0].keys()))

        second_page_resp = await client.get(
            "/api/v1/feed",
            params={"limit": 2, "before_cursor": first_page["next_cursor"]},
            headers=headers,
        )
        assert second_page_resp.status_code == 200

        second_page = second_page_resp.json()["data"]
        second_items = second_page["items"]
        assert len(second_items) >= 1
        assert second_items[0]["action"] == "decision_made"

        first_ids = {item["event_id"] for item in first_items}
        second_ids = {item["event_id"] for item in second_items}
        assert first_ids.isdisjoint(second_ids)

    @pytest.mark.asyncio
    async def test_feed_rejects_invalid_cursor(self, client: AsyncClient, db_session: AsyncSession):
        headers, _ = await _auth_context(
            client,
            db_session,
            email="feed-cursor@william.os",
            username="feedcursor",
        )

        resp = await client.get(
            "/api/v1/feed",
            params={"before_cursor": "not-a-valid-cursor"},
            headers=headers,
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["ok"] is False
        assert body["error"] == "Invalid feed cursor"

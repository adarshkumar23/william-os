"""
WILLIAM OS - Experiment assignment tests.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.core.experiments import assign_variant
from app.core.security import create_access_token

if TYPE_CHECKING:
    from httpx import AsyncClient

    from app.modules.auth.models import User


def test_assign_variant_is_deterministic() -> None:
    user_id = uuid.uuid4()
    first = assign_variant(
        user_id=user_id,
        experiment_key="dashboard_layout",
        variants=["control", "focus"],
    )
    second = assign_variant(
        user_id=user_id,
        experiment_key="dashboard_layout",
        variants=["control", "focus"],
    )
    assert first == second


@pytest.mark.asyncio
async def test_experiment_assignments_endpoint_returns_variants(
    client: AsyncClient,
    test_user: User,
) -> None:
    token = create_access_token(test_user.id)
    response = await client.get(
        "/api/v1/experiments/assignments",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assignments = payload["data"]["assignments"]
    assert assignments["dashboard_layout"] in {"control", "focus"}
    assert assignments["habit_prompt_style"] in {"compact", "coaching"}
    assert assignments["journal_summary_cta"] in {"off", "inline"}

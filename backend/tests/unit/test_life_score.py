"""
WILLIAM OS — Life Score Unit Tests
Validates weighted life-score computation and history retrieval.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.intelligence.service import IntelligenceService, LifeScoreService


@pytest.mark.asyncio
async def test_compute_life_score_uses_weighted_components(db_session):
    service = LifeScoreService(db_session)
    user_id = uuid.uuid4()

    latest_signals = {
        ("sleep", "energy"): 80.0,
        ("sleep", "risk"): 1.0,
        ("habits", "focus"): 90.0,
        ("habits", "risk"): 0.0,
        ("fitness", "energy"): 70.0,
        ("study", "focus"): 60.0,
        ("medicine", "energy"): 80.0,
        ("medicine", "risk"): 0.0,
        ("journal", "mood"): 50.0,
        ("decisions", "focus"): 40.0,
    }

    with (
        patch.object(IntelligenceService, "collect_signals", AsyncMock(return_value=[])),
        patch.object(
            IntelligenceService,
            "_latest_signal_lookup",
            AsyncMock(return_value=latest_signals),
        ),
        patch.object(
            LifeScoreService,
            "generate_explanation",
            AsyncMock(
                return_value=(
                    "Sleep pressure lowered your score. "
                    "Consistent habits kept it stable."
                )
            ),
        ),
    ):
        result = await service.compute_score(user_id=user_id)

    assert result.score == 68.5
    assert result.component_scores["sleep"] == 70.0
    assert result.component_scores["habits"] == 90.0
    assert result.component_scores["fitness"] == 70.0
    assert result.component_scores["study"] == 60.0
    assert result.component_scores["medicine"] == 80.0
    assert result.component_scores["journal"] == 50.0
    assert result.component_scores["decisions"] == 40.0


@pytest.mark.asyncio
async def test_life_score_history_returns_recent_points(db_session):
    service = LifeScoreService(db_session)
    user_id = uuid.uuid4()

    signal_sets = [
        {
            ("sleep", "energy"): 60.0,
            ("sleep", "risk"): 2.0,
            ("habits", "focus"): 70.0,
            ("habits", "risk"): 0.0,
            ("fitness", "energy"): 65.0,
            ("study", "focus"): 72.0,
            ("medicine", "energy"): 90.0,
            ("medicine", "risk"): 0.0,
            ("journal", "mood"): 55.0,
            ("decisions", "focus"): 58.0,
        },
        {
            ("sleep", "energy"): 85.0,
            ("sleep", "risk"): 0.0,
            ("habits", "focus"): 88.0,
            ("habits", "risk"): 0.0,
            ("fitness", "energy"): 80.0,
            ("study", "focus"): 84.0,
            ("medicine", "energy"): 95.0,
            ("medicine", "risk"): 0.0,
            ("journal", "mood"): 82.0,
            ("decisions", "focus"): 78.0,
        },
    ]

    with (
        patch.object(IntelligenceService, "collect_signals", AsyncMock(return_value=[])),
        patch.object(
            IntelligenceService,
            "_latest_signal_lookup",
            AsyncMock(side_effect=signal_sets),
        ),
        patch.object(
            LifeScoreService,
            "generate_explanation",
            AsyncMock(side_effect=["One. Two.", "Three. Four."]),
        ),
    ):
        await service.compute_score(user_id=user_id)
        await service.compute_score(user_id=user_id)

    history = await service.get_score_history(user_id=user_id, days=30)

    assert len(history) == 2
    assert history[0].computed_at <= history[1].computed_at
    assert history[0].score < history[1].score

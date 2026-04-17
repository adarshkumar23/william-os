"""
WILLIAM OS — Decisions Service Tests
Unit tests for create, analyze, choose, outcome, and quality stats.
"""

from __future__ import annotations

from datetime import date

import pytest
from app.modules.decisions.schemas import DecisionChoose, DecisionCreate, DecisionOutcome
from app.modules.decisions.service import DecisionService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_decision(db_session: AsyncSession, test_user):
    service = DecisionService(db_session)

    decision = await service.create_decision(
        user_id=test_user.id,
        data=DecisionCreate(
            title="Choose tech stack",
            description="Need stack for internal tooling",
            decision_type="engineering",
            deadline=date.today(),
            options=[{"name": "A"}, {"name": "B"}],
            criteria=[{"name": "speed", "weight": 0.6}, {"name": "cost", "weight": 0.4}],
        ),
    )

    assert decision.title == "Choose tech stack"
    assert decision.status == "open"


@pytest.mark.asyncio
async def test_analyze_decision_mock(db_session: AsyncSession, test_user, monkeypatch):
    service = DecisionService(db_session)

    created = await service.create_decision(
        user_id=test_user.id,
        data=DecisionCreate(
            title="City move",
            description="Decide where to relocate",
            decision_type="personal",
            options=[{"name": "Delhi"}, {"name": "Bangalore"}],
            criteria=[{"name": "cost", "weight": 0.5}, {"name": "growth", "weight": 0.5}],
        ),
    )

    async def _fake_ai(*args, **kwargs):
        from app.modules.decisions.schemas import DecisionAnalysis

        return DecisionAnalysis(
            scores={"Delhi": 0.58, "Bangalore": 0.72},
            recommendation="Bangalore",
            reasoning="Higher growth potential.",
            confidence=0.86,
            risk_factors=["Higher rent"],
        )

    monkeypatch.setattr(service, "_call_ai_analysis", _fake_ai)

    analysis = await service.analyze_decision(user_id=test_user.id, decision_id=created.id)

    assert analysis.recommendation == "Bangalore"
    assert analysis.confidence == pytest.approx(0.86)


@pytest.mark.asyncio
async def test_choose_and_outcome(db_session: AsyncSession, test_user):
    service = DecisionService(db_session)

    created = await service.create_decision(
        user_id=test_user.id,
        data=DecisionCreate(
            title="Course selection",
            description="Pick one specialization",
            decision_type="career",
            options=[{"name": "ML"}, {"name": "Systems"}],
            criteria=[{"name": "interest", "weight": 0.7}, {"name": "scope", "weight": 0.3}],
        ),
    )

    decided = await service.choose_option(
        user_id=test_user.id,
        decision_id=created.id,
        payload=DecisionChoose(chosen_option="ML", reasoning="Best fit"),
    )
    assert decided.status == "decided"
    assert decided.chosen_option == "ML"

    reviewed = await service.log_outcome(
        user_id=test_user.id,
        decision_id=created.id,
        payload=DecisionOutcome(outcome="Great long-term fit", outcome_rating=5),
    )
    assert reviewed.status == "reviewed"
    assert reviewed.outcome_rating == 5


@pytest.mark.asyncio
async def test_decision_quality_stats(db_session: AsyncSession, test_user):
    service = DecisionService(db_session)

    created = await service.create_decision(
        user_id=test_user.id,
        data=DecisionCreate(
            title="Buy laptop",
            description="Need a reliable machine",
            decision_type="purchase",
            options=[{"name": "Model A"}, {"name": "Model B"}],
            criteria=[{"name": "battery", "weight": 0.5}, {"name": "price", "weight": 0.5}],
        ),
    )

    await service.analyze_decision(user_id=test_user.id, decision_id=created.id)
    await service.choose_option(
        user_id=test_user.id,
        decision_id=created.id,
        payload=DecisionChoose(chosen_option="Model B"),
    )
    await service.log_outcome(
        user_id=test_user.id,
        decision_id=created.id,
        payload=DecisionOutcome(outcome="Good outcome", outcome_rating=4),
    )

    stats = await service.get_decision_quality(user_id=test_user.id)

    assert stats.total == 1
    assert stats.avg_outcome_rating == pytest.approx(4.0)
    assert "purchase" in stats.by_type

"""
WILLIAM OS — Intelligence Rule Unit Tests
Validates each hardcoded cross-module intelligence rule.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from app.modules.intelligence.service import IntelligenceService


BASELINE_SIGNALS = {
    ("sleep", "energy"): 90.0,
    ("sleep", "risk"): 0.0,
    ("medicine", "risk"): 0.0,
    ("trading", "stress"): 20.0,
    ("habits", "risk"): 0.0,
    ("journal", "mood"): 80.0,
}

class TestHardcodedCrossModuleRules:
    @pytest.mark.asyncio
    async def test_sleep_quality_reduces_study_workload(self, db_session):
        service = IntelligenceService(db_session)
        user_id = uuid.uuid4()

        with (
            patch.object(
                service,
                "_latest_signal_lookup",
                AsyncMock(return_value={**BASELINE_SIGNALS, ("sleep", "energy"): 55.0}),
            ),
            patch.object(service, "_list_active_rules", AsyncMock(return_value=[])),
        ):
            adjustments = await service.apply_cross_rules(user_id)

        assert len(adjustments) == 1
        assert adjustments[0].rule_name == "sleep_quality_reduces_study_workload"

    @pytest.mark.asyncio
    async def test_medicine_missed_reduces_energy(self, db_session):
        service = IntelligenceService(db_session)
        user_id = uuid.uuid4()

        with (
            patch.object(
                service,
                "_latest_signal_lookup",
                AsyncMock(return_value={**BASELINE_SIGNALS, ("medicine", "risk"): 100.0}),
            ),
            patch.object(service, "_list_active_rules", AsyncMock(return_value=[])),
        ):
            adjustments = await service.apply_cross_rules(user_id)

        assert len(adjustments) == 1
        assert adjustments[0].rule_name == "medicine_missed_reduces_energy"

    @pytest.mark.asyncio
    async def test_trading_stress_lowers_fitness_intensity(self, db_session):
        service = IntelligenceService(db_session)
        user_id = uuid.uuid4()

        with (
            patch.object(
                service,
                "_latest_signal_lookup",
                AsyncMock(return_value={**BASELINE_SIGNALS, ("trading", "stress"): 85.0}),
            ),
            patch.object(service, "_list_active_rules", AsyncMock(return_value=[])),
        ):
            adjustments = await service.apply_cross_rules(user_id)

        assert len(adjustments) == 1
        assert adjustments[0].rule_name == "trading_stress_lowers_fitness_intensity"
        assert adjustments[0].target_label == "light"

    @pytest.mark.asyncio
    async def test_habit_streak_drop_increases_scheduler_risk(self, db_session):
        service = IntelligenceService(db_session)
        user_id = uuid.uuid4()

        with (
            patch.object(
                service,
                "_latest_signal_lookup",
                AsyncMock(return_value={**BASELINE_SIGNALS, ("habits", "risk"): 100.0}),
            ),
            patch.object(service, "_list_active_rules", AsyncMock(return_value=[])),
        ):
            adjustments = await service.apply_cross_rules(user_id)

        assert len(adjustments) == 1
        assert adjustments[0].rule_name == "habit_streak_drop_increases_scheduler_risk"

    @pytest.mark.asyncio
    async def test_low_mood_reduces_decision_confidence(self, db_session):
        service = IntelligenceService(db_session)
        user_id = uuid.uuid4()

        with (
            patch.object(
                service,
                "_latest_signal_lookup",
                AsyncMock(return_value={**BASELINE_SIGNALS, ("journal", "mood"): 30.0}),
            ),
            patch.object(service, "_list_active_rules", AsyncMock(return_value=[])),
        ):
            adjustments = await service.apply_cross_rules(user_id)

        assert len(adjustments) == 1
        assert adjustments[0].rule_name == "low_mood_reduces_decision_confidence"

    @pytest.mark.asyncio
    async def test_sleep_debt_reduces_study_focus(self, db_session):
        service = IntelligenceService(db_session)
        user_id = uuid.uuid4()

        with (
            patch.object(
                service,
                "_latest_signal_lookup",
                AsyncMock(return_value={**BASELINE_SIGNALS, ("sleep", "risk"): 3.0}),
            ),
            patch.object(service, "_list_active_rules", AsyncMock(return_value=[])),
        ):
            adjustments = await service.apply_cross_rules(user_id)

        assert len(adjustments) == 1
        assert adjustments[0].rule_name == "sleep_debt_reduces_study_focus"

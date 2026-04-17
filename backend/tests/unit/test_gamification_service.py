"""
WILLIAM OS — Gamification Service Unit Tests
Covers XP awards, level updates, and weekly momentum calculations.
"""

from __future__ import annotations

import uuid

import pytest

from app.modules.gamification.service import GamificationService


class TestGamificationService:
    @pytest.mark.asyncio
    async def test_award_xp_habit_with_milestone_updates_profile(self, db_session):
        service = GamificationService(db_session)
        user_id = uuid.uuid4()

        event = await service.award_xp(
            user_id=user_id,
            source_module="habits",
            action="habit_checkin",
            metadata={"current_streak": 7},
        )
        assert event is not None
        assert event.xp_earned == 10

        profile = await service.get_profile(user_id=user_id)
        assert profile.level_progress.total_xp == 60
        assert profile.level_progress.level >= 1

        history = await service.list_xp_history(user_id=user_id)
        assert len(history) == 2
        assert sorted(item.xp_earned for item in history) == [10, 50]

    @pytest.mark.asyncio
    async def test_study_award_and_momentum(self, db_session):
        service = GamificationService(db_session)
        user_id = uuid.uuid4()

        event = await service.award_xp(
            user_id=user_id,
            source_module="study",
            action="study_session_completed",
            metadata={"duration_minutes": 120},
        )
        assert event is not None
        assert event.xp_earned == 40

        momentum = await service.compute_weekly_momentum(user_id=user_id)
        assert momentum.momentum_score >= 0
        assert momentum.focus_rank >= 1

"""
WILLIAM OS — Gamification Schemas
API response contracts for XP, records, and momentum profile.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class XPEventResponse(BaseModel):
    id: UUID
    user_id: UUID
    source_module: str
    action: str
    xp_earned: int
    earned_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class PersonalRecordResponse(BaseModel):
    id: UUID
    user_id: UUID
    record_type: str
    value: float
    achieved_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class WeeklyMomentumResponse(BaseModel):
    id: UUID
    user_id: UUID
    week_start: date
    momentum_score: float
    discipline_debt: float
    focus_rank: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LevelProgress(BaseModel):
    level: int
    total_xp: int
    current_level_xp_floor: int
    next_level_xp_target: int
    xp_to_next_level: int
    progress_pct: float


class GamificationProfileResponse(BaseModel):
    level_progress: LevelProgress
    weekly_momentum: WeeklyMomentumResponse
    records: list[PersonalRecordResponse]
    recent_xp_events: list[XPEventResponse]

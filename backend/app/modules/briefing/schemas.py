"""
WILLIAM OS — Morning Briefing Schemas
Response contracts for daily unified briefing APIs.
"""

from datetime import date, datetime

from app.modules.messaging.schemas import NotificationLogResponse
from pydantic import BaseModel, Field


class BriefingScheduleItem(BaseModel):
    id: str
    title: str
    category: str
    start_time: str
    end_time: str
    priority: int
    status: str


class BriefingHabitItem(BaseModel):
    id: str
    name: str
    preferred_time: str | None = None
    current_streak: int


class BriefingMedicineMissItem(BaseModel):
    medicine_name: str
    log_date: date
    scheduled_time: str
    skip_reason: str | None = None


class BriefingDeadlineItem(BaseModel):
    source: str
    title: str
    due_date: date
    detail: str | None = None


class BriefingEnergyPrediction(BaseModel):
    peak_hours: list[str] = Field(default_factory=list)
    low_hours: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    generated_by: str | None = None


class BriefingLifeScore(BaseModel):
    score: float
    component_scores: dict[str, float]
    explanation: str
    computed_at: datetime


class MorningBriefingResponse(BaseModel):
    generated_at: datetime
    sleep_quality: dict
    today_schedule: list[BriefingScheduleItem]
    priority_habits: list[BriefingHabitItem]
    missed_medicines: list[BriefingMedicineMissItem]
    upcoming_deadlines: list[BriefingDeadlineItem]
    market_watchlist_movement: dict
    energy_prediction: BriefingEnergyPrediction | None
    life_score: BriefingLifeScore
    ai_recommendation_of_day: str


class MorningBriefingSendResult(BaseModel):
    briefing: MorningBriefingResponse
    telegram: NotificationLogResponse
    in_app: NotificationLogResponse


class WeeklyReview(BaseModel):
    week_start: date
    week_end: date
    avg_score: float
    best_day: str
    worst_day: str
    trend: str
    william_summary: str
    highlights: list[str] = Field(default_factory=list)

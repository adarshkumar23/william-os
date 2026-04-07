"""
WILLIAM OS — Sleep Service
Sleep recording, debt tracking, recommendations, and pattern analysis.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from time import perf_counter

import httpx
import structlog
from app.core.config import get_settings
from app.core.events import Event, EventType, event_bus
from app.core.metrics import observe_ai_call
from app.modules.memory.service import MemoryService
from app.modules.scheduler.service import SchedulerService
from app.modules.sleep.models import SleepDebt, SleepRecommendation, SleepRecord
from app.modules.sleep.schemas import (
    SleepAnalysis,
    SleepDebtResponse,
    SleepRecommendationResponse,
    SleepRecordCreate,
    SleepRecordResponse,
    SleepStats,
)
from app.shared.types import NotFoundError
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class SleepService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def log_sleep(self, user_id: uuid.UUID, data: SleepRecordCreate) -> SleepRecordResponse:
        duration = self._duration_minutes(data.bedtime, data.wake_time)
        record = SleepRecord(
            user_id=user_id,
            sleep_date=data.sleep_date,
            bedtime=data.bedtime,
            wake_time=data.wake_time,
            sleep_duration_minutes=duration,
            time_to_fall_asleep_minutes=data.time_to_fall_asleep_minutes,
            interruptions=data.interruptions,
            sleep_quality=data.sleep_quality,
            deep_sleep_minutes=data.deep_sleep_minutes,
            light_sleep_minutes=data.light_sleep_minutes,
            rem_sleep_minutes=data.rem_sleep_minutes,
            notes=data.notes,
            source=data.source,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)

        await event_bus.publish(
            Event(
                type=EventType.SLEEP_DATA_RECORDED,
                data={
                    "sleep_date": str(data.sleep_date),
                    "duration_minutes": duration,
                    "sleep_quality": data.sleep_quality,
                },
                user_id=user_id,
            )
        )

        return SleepRecordResponse.model_validate(record)

    async def get_sleep_history(
        self,
        user_id: uuid.UUID,
        days: int = 30,
        limit: int = 50,
        offset: int = 0,
    ) -> list[SleepRecordResponse]:
        cutoff = date.today() - timedelta(days=max(1, days) - 1)
        query = (
            select(SleepRecord)
            .where(SleepRecord.user_id == user_id)
            .where(SleepRecord.sleep_date >= cutoff)
            .order_by(SleepRecord.sleep_date.desc())
        )
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return [SleepRecordResponse.model_validate(item) for item in result.scalars().all()]

    async def get_sleep_stats(self, user_id: uuid.UUID) -> SleepStats:
        records = await self.get_sleep_history(user_id=user_id, days=30)
        if not records:
            return SleepStats(
                avg_quality_30d=0.0,
                avg_duration=0.0,
                avg_bedtime="00:00",
                consistency_score=0.0,
            )

        avg_quality = round(
            sum(float(item.sleep_quality) for item in records) / len(records),
            2,
        )
        avg_duration = round(
            sum(float(item.sleep_duration_minutes) for item in records) / len(records),
            2,
        )

        bedtime_minutes = [item.bedtime.hour * 60 + item.bedtime.minute for item in records]
        avg_bedtime_minutes = int(sum(bedtime_minutes) / len(bedtime_minutes))
        avg_bedtime = f"{avg_bedtime_minutes // 60:02d}:{avg_bedtime_minutes % 60:02d}"

        spread = max(bedtime_minutes) - min(bedtime_minutes) if len(bedtime_minutes) > 1 else 0
        consistency_score = round(max(0.0, 100.0 - (spread / 3.0)), 2)

        return SleepStats(
            avg_quality_30d=avg_quality,
            avg_duration=avg_duration,
            avg_bedtime=avg_bedtime,
            consistency_score=consistency_score,
        )

    async def calculate_sleep_debt(self, user_id: uuid.UUID) -> SleepDebtResponse:
        optimal_hours = 7.5
        today = date.today()

        avg_7d = await self._avg_sleep_hours(user_id=user_id, start=today - timedelta(days=6))
        avg_prev_7d = await self._avg_sleep_hours(
            user_id=user_id,
            start=today - timedelta(days=13),
            end=today - timedelta(days=7),
        )

        debt_hours = round(max(0.0, optimal_hours - avg_7d), 2)
        if abs(avg_7d - avg_prev_7d) < 0.1:
            trend = "stable"
        elif avg_7d > avg_prev_7d:
            trend = "improving"
        else:
            trend = "worsening"

        entry = SleepDebt(
            user_id=user_id,
            calculated_date=today,
            optimal_hours=optimal_hours,
            actual_hours_7d_avg=avg_7d,
            debt_hours=debt_hours,
            trend=trend,
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)

        days_to_recover = int((debt_hours / 1.0) + 0.999) if debt_hours > 0 else 0
        return SleepDebtResponse(
            id=entry.id,
            user_id=entry.user_id,
            calculated_date=entry.calculated_date,
            optimal_hours=entry.optimal_hours,
            actual_hours_7d_avg=entry.actual_hours_7d_avg,
            debt_hours=entry.debt_hours,
            trend=entry.trend,
            days_to_recover=days_to_recover,
            created_at=entry.created_at,
        )

    async def generate_recommendation(
        self,
        user_id: uuid.UUID,
        for_date: date,
    ) -> SleepRecommendationResponse:
        from app.modules.fitness.service import FitnessService

        debt = await self.calculate_sleep_debt(user_id=user_id)
        stats = await self.get_sleep_stats(user_id=user_id)

        tomorrow = for_date + timedelta(days=1)
        schedule_blocks = 0
        try:
            scheduler = SchedulerService(self.db)
            plan = await scheduler.get_plan(user_id=user_id, plan_date=tomorrow)
            schedule_blocks = len(plan.blocks)
        except Exception:
            schedule_blocks = 0

        fitness = FitnessService(self.db)
        workouts = await fitness.list_workouts(user_id=user_id, days=7)
        workout_minutes = sum(item.duration_minutes for item in workouts)

        factors = {
            "sleep_debt": debt.debt_hours,
            "avg_quality": stats.avg_quality_30d,
            "avg_duration_minutes": stats.avg_duration,
            "tomorrow_schedule_blocks": schedule_blocks,
            "recent_workout_minutes": workout_minutes,
        }

        ai_plan = await self._generate_ai_recommendation(user_id=user_id, factors=factors)
        if ai_plan is None:
            ai_plan = self._fallback_recommendation(factors=factors)

        entry = SleepRecommendation(
            user_id=user_id,
            recommendation_date=for_date,
            recommended_bedtime=ai_plan["recommended_bedtime"],
            recommended_wake_time=ai_plan["recommended_wake_time"],
            recommended_duration_minutes=ai_plan["recommended_duration_minutes"],
            reasoning=ai_plan["reasoning"],
            factors=factors,
            confidence=float(ai_plan.get("confidence", 0.7)),
            followed=None,
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)

        return SleepRecommendationResponse.model_validate(entry)

    async def get_recommendation(
        self,
        user_id: uuid.UUID,
        recommendation_date: date,
    ) -> SleepRecommendationResponse:
        result = await self.db.execute(
            select(SleepRecommendation)
            .where(SleepRecommendation.user_id == user_id)
            .where(SleepRecommendation.recommendation_date == recommendation_date)
            .order_by(desc(SleepRecommendation.created_at))
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("SleepRecommendation", str(recommendation_date))
        return SleepRecommendationResponse.model_validate(row)

    async def mark_recommendation_followed(
        self,
        user_id: uuid.UUID,
        recommendation_id: uuid.UUID,
        followed: bool,
    ) -> SleepRecommendationResponse:
        result = await self.db.execute(
            select(SleepRecommendation)
            .where(SleepRecommendation.id == recommendation_id)
            .where(SleepRecommendation.user_id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError("SleepRecommendation", str(recommendation_id))

        row.followed = followed
        await self.db.flush()
        await self.db.refresh(row)
        return SleepRecommendationResponse.model_validate(row)

    async def analyze_sleep_patterns(self, user_id: uuid.UUID, days: int = 90) -> SleepAnalysis:
        history = await self.get_sleep_history(user_id=user_id, days=days)
        if not history:
            return SleepAnalysis(
                patterns=["No sleep records yet."],
                recommendations=["Log sleep daily to unlock analysis."],
                optimal_window={"bedtime": "22:30", "wake_time": "06:00"},
                ai_insights="Insufficient data.",
            )

        avg_quality = round(sum(item.sleep_quality for item in history) / len(history), 2)
        avg_duration = round(sum(item.sleep_duration_minutes for item in history) / len(history), 2)
        bedtime_minutes = [item.bedtime.hour * 60 + item.bedtime.minute for item in history]
        avg_bedtime_minutes = int(sum(bedtime_minutes) / len(bedtime_minutes))

        patterns = [
            f"Average sleep quality over {days}d: {avg_quality}/10.",
            f"Average duration: {avg_duration:.0f} minutes.",
        ]

        recommendations = [
            "Aim for consistent bedtime within a 30-minute window.",
            "Avoid late heavy meals before bedtime.",
        ]

        ai_insights = await self._generate_ai_pattern_analysis(
            {
                "days": days,
                "avg_quality": avg_quality,
                "avg_duration": avg_duration,
                "records": [
                    {
                        "sleep_date": str(item.sleep_date),
                        "bedtime": item.bedtime.isoformat(),
                        "wake_time": item.wake_time.isoformat(),
                        "sleep_duration_minutes": item.sleep_duration_minutes,
                        "sleep_quality": item.sleep_quality,
                    }
                    for item in history
                ],
            }
        )

        return SleepAnalysis(
            patterns=patterns,
            recommendations=recommendations,
            optimal_window={
                "bedtime": f"{avg_bedtime_minutes // 60:02d}:{avg_bedtime_minutes % 60:02d}",
                "wake_time": "06:00",
            },
            ai_insights=ai_insights,
        )

    async def _avg_sleep_hours(
        self,
        user_id: uuid.UUID,
        start: date,
        end: date | None = None,
    ) -> float:
        end_date = end or date.today()
        result = await self.db.execute(
            select(func.avg(SleepRecord.sleep_duration_minutes))
            .where(SleepRecord.user_id == user_id)
            .where(SleepRecord.sleep_date >= start)
            .where(SleepRecord.sleep_date <= end_date)
        )
        avg_minutes = float(result.scalar() or 0.0)
        return round(avg_minutes / 60.0, 2)

    async def _generate_ai_recommendation(self, user_id: uuid.UUID, factors: dict) -> dict | None:
        api_key = self.settings.openrouter_api_key.get_secret_value()
        if not api_key:
            return None

        memory_context = await MemoryService(self.db).get_relevant_memory_context(
            user_id=user_id,
            modules=["sleep", "fitness", "study"],
            limit=6,
        )

        prompt = (
            "Given these sleep and lifestyle factors, return JSON with keys: "
            "recommended_bedtime, recommended_wake_time, recommended_duration_minutes, "
            "reasoning, confidence. Factors: "
            f"{json.dumps(factors)}. Memory context: {memory_context}"
        )
        payload = {
            "model": self.settings.openrouter_model,
            "messages": [
                {"role": "system", "content": "You are a sleep optimization coach."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 350,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.base_url,
            "X-Title": self.settings.app_name,
        }

        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()

            observe_ai_call(provider="openrouter", duration_seconds=perf_counter() - started)
            content = response.json()["choices"][0]["message"]["content"].strip()
            cleaned = content.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except Exception as exc:
            observe_ai_call(provider="openrouter", duration_seconds=perf_counter() - started)
            logger.warning("sleep_recommendation_ai_failed", error=str(exc))
        return None

    @staticmethod
    def _fallback_recommendation(factors: dict) -> dict:
        debt = float(factors.get("sleep_debt") or 0)
        schedule_blocks = int(factors.get("tomorrow_schedule_blocks") or 0)

        bedtime = "22:30"
        if debt >= 1.0:
            bedtime = "22:00"
        if schedule_blocks >= 10:
            bedtime = "21:45"

        duration_minutes = 480 if debt >= 1.0 else 450
        return {
            "recommended_bedtime": bedtime,
            "recommended_wake_time": "06:00",
            "recommended_duration_minutes": duration_minutes,
            "reasoning": "Fallback recommendation based on debt and schedule load.",
            "confidence": 0.72,
        }

    async def _generate_ai_pattern_analysis(self, payload: dict) -> str:
        api_key = self.settings.openrouter_api_key.get_secret_value()
        if not api_key:
            return "AI analysis unavailable (missing OpenRouter key)."

        prompt = (
            "Analyze long-term sleep patterns from this JSON and provide concise insights, "
            "risk factors, and three practical recommendations:\n"
            f"{json.dumps(payload)}"
        )
        body = {
            "model": self.settings.openrouter_model,
            "messages": [
                {"role": "system", "content": "You are a sleep data analyst."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 450,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.base_url,
            "X-Title": self.settings.app_name,
        }

        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=body,
                    headers=headers,
                )
                response.raise_for_status()
            observe_ai_call(provider="openrouter", duration_seconds=perf_counter() - started)
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            observe_ai_call(provider="openrouter", duration_seconds=perf_counter() - started)
            logger.warning("sleep_pattern_analysis_ai_failed", error=str(exc))
            return "AI analysis temporarily unavailable."

    @staticmethod
    def _duration_minutes(bedtime: datetime, wake_time: datetime) -> int:
        delta = wake_time - bedtime
        minutes = int(delta.total_seconds() / 60)
        if minutes <= 0:
            # Defensive fallback for malformed cross-day payloads.
            minutes += 24 * 60
        return minutes

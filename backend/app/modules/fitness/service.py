"""
WILLIAM OS — Fitness Service
Health telemetry ingestion, summaries, and energy forecasting.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, time, timedelta

import httpx
import structlog
from app.core.config import get_settings
from app.core.events import Event, EventType, event_bus
from app.modules.fitness.models import EnergyForecast, FitnessDevice, HealthMetric, WorkoutLog
from app.modules.fitness.schemas import (
    DailyHealthSummary,
    EnergyForecastResponse,
    FitnessDeviceCreate,
    FitnessDeviceResponse,
    HealthMetricCreate,
    HealthMetricResponse,
    WorkoutLogCreate,
    WorkoutLogResponse,
)
from app.modules.scheduler.service import SchedulerService
from app.shared.types import NotFoundError
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class FitnessService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def register_device(
        self,
        user_id: uuid.UUID,
        data: FitnessDeviceCreate,
    ) -> FitnessDeviceResponse:
        device = FitnessDevice(user_id=user_id, **data.model_dump())
        self.db.add(device)
        await self.db.flush()
        await self.db.refresh(device)
        return FitnessDeviceResponse.model_validate(device)

    async def list_devices(self, user_id: uuid.UUID) -> list[FitnessDeviceResponse]:
        result = await self.db.execute(
            select(FitnessDevice)
            .where(FitnessDevice.user_id == user_id)
            .where(FitnessDevice.is_active.is_(True))
            .order_by(FitnessDevice.created_at.desc())
        )
        return [FitnessDeviceResponse.model_validate(item) for item in result.scalars().all()]

    async def remove_device(self, user_id: uuid.UUID, device_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(FitnessDevice).where(
                and_(FitnessDevice.id == device_id, FitnessDevice.user_id == user_id)
            )
        )
        device = result.scalar_one_or_none()
        if not device:
            raise NotFoundError("FitnessDevice", str(device_id))
        device.is_active = False
        await self.db.flush()

    async def log_metrics(
        self,
        user_id: uuid.UUID,
        metrics: list[HealthMetricCreate],
    ) -> list[HealthMetricResponse]:
        created: list[HealthMetric] = []
        for item in metrics:
            metric = HealthMetric(user_id=user_id, **item.model_dump())
            self.db.add(metric)
            created.append(metric)

        await self.db.flush()

        await event_bus.publish(
            Event(
                type=EventType.FITNESS_DATA_SYNCED,
                data={"count": len(created)},
                user_id=user_id,
            )
        )

        return [HealthMetricResponse.model_validate(metric) for metric in created]

    async def log_workout(self, user_id: uuid.UUID, data: WorkoutLogCreate) -> WorkoutLogResponse:
        workout = WorkoutLog(user_id=user_id, **data.model_dump())
        self.db.add(workout)
        await self.db.flush()
        await self.db.refresh(workout)
        return WorkoutLogResponse.model_validate(workout)

    async def list_workouts(
        self,
        user_id: uuid.UUID,
        days: int = 30,
    ) -> list[WorkoutLogResponse]:
        cutoff = date.today() - timedelta(days=max(1, days) - 1)
        result = await self.db.execute(
            select(WorkoutLog)
            .where(WorkoutLog.user_id == user_id)
            .where(WorkoutLog.workout_date >= cutoff)
            .order_by(WorkoutLog.workout_date.desc(), WorkoutLog.created_at.desc())
        )
        return [WorkoutLogResponse.model_validate(item) for item in result.scalars().all()]

    async def get_daily_summary(self, user_id: uuid.UUID, target_date: date) -> DailyHealthSummary:
        start_dt = datetime.combine(target_date, time.min).replace(tzinfo=UTC)
        end_dt = datetime.combine(target_date, time.max).replace(tzinfo=UTC)

        metrics_result = await self.db.execute(
            select(HealthMetric)
            .where(HealthMetric.user_id == user_id)
            .where(HealthMetric.recorded_at >= start_dt)
            .where(HealthMetric.recorded_at <= end_dt)
        )
        metrics = metrics_result.scalars().all()

        workouts_result = await self.db.execute(
            select(WorkoutLog)
            .where(WorkoutLog.user_id == user_id)
            .where(WorkoutLog.workout_date == target_date)
        )
        workouts = workouts_result.scalars().all()

        values = self._metric_values(metrics)
        return DailyHealthSummary(
            steps=self._latest_metric(values, "steps"),
            avg_heart_rate=self._avg_metric(values, "heart_rate"),
            calories=self._sum_metric(values, "calories_burned"),
            sleep_hours=self._latest_metric(values, "sleep_hours"),
            spo2=self._avg_metric(values, "spo2"),
            stress=self._avg_metric(values, "stress_level"),
            workout_count=len(workouts),
            workout_minutes=sum(item.duration_minutes for item in workouts),
        )

    async def get_metric_history(
        self,
        user_id: uuid.UUID,
        metric_type: str,
        days: int = 30,
    ) -> list[HealthMetricResponse]:
        cutoff = datetime.now(UTC) - timedelta(days=max(1, days))
        result = await self.db.execute(
            select(HealthMetric)
            .where(HealthMetric.user_id == user_id)
            .where(HealthMetric.metric_type == metric_type)
            .where(HealthMetric.recorded_at >= cutoff)
            .order_by(HealthMetric.recorded_at.asc())
        )
        return [HealthMetricResponse.model_validate(item) for item in result.scalars().all()]

    async def generate_energy_forecast(
        self,
        user_id: uuid.UUID,
        forecast_date: date,
    ) -> EnergyForecastResponse:
        factors = await self._build_forecast_factors(user_id, forecast_date)
        ai_forecast = await self._generate_ai_forecast(factors)
        if ai_forecast is None:
            ai_forecast = self._fallback_curve(factors)

        hourly_scores = ai_forecast.get("hourly_scores") or {}
        peak_hours = ai_forecast.get("peak_hours") or []
        low_hours = ai_forecast.get("low_hours") or []

        existing = await self.db.execute(
            select(EnergyForecast)
            .where(EnergyForecast.user_id == user_id)
            .where(EnergyForecast.forecast_date == forecast_date)
            .order_by(EnergyForecast.created_at.desc())
        )
        current = existing.scalar_one_or_none()
        if current:
            current.hourly_scores = hourly_scores
            current.peak_hours = peak_hours
            current.low_hours = low_hours
            current.factors = factors
            current.generated_by = ai_forecast.get("generated_by", "rule_based")
            forecast = current
        else:
            forecast = EnergyForecast(
                user_id=user_id,
                forecast_date=forecast_date,
                hourly_scores=hourly_scores,
                peak_hours=peak_hours,
                low_hours=low_hours,
                factors=factors,
                generated_by=ai_forecast.get("generated_by", "rule_based"),
            )
            self.db.add(forecast)

        await self.db.flush()
        await self.db.refresh(forecast)

        suggestions = self._build_energy_suggestions(hourly_scores, peak_hours, low_hours)
        try:
            schedule_service = SchedulerService(self.db)
            plan = await schedule_service.get_plan(user_id=user_id, plan_date=forecast_date)
            suggestions.extend(
                self._compute_schedule_swap_suggestions(
                    blocks=plan.blocks,
                    peak_hours=peak_hours,
                    low_hours=low_hours,
                )
            )
        except Exception:
            pass

        return EnergyForecastResponse(
            id=forecast.id,
            forecast_date=forecast.forecast_date,
            hourly_scores=forecast.hourly_scores,
            peak_hours=forecast.peak_hours,
            low_hours=forecast.low_hours,
            suggestions=suggestions,
            generated_by=forecast.generated_by,
        )

    async def get_energy_forecast(
        self,
        user_id: uuid.UUID,
        forecast_date: date,
    ) -> EnergyForecastResponse | None:
        result = await self.db.execute(
            select(EnergyForecast)
            .where(EnergyForecast.user_id == user_id)
            .where(EnergyForecast.forecast_date == forecast_date)
            .order_by(desc(EnergyForecast.created_at))
            .limit(1)
        )
        forecast = result.scalar_one_or_none()
        if forecast is None:
            return None
        suggestions = self._build_energy_suggestions(
            forecast.hourly_scores,
            forecast.peak_hours,
            forecast.low_hours,
        )
        return EnergyForecastResponse(
            id=forecast.id,
            forecast_date=forecast.forecast_date,
            hourly_scores=forecast.hourly_scores,
            peak_hours=forecast.peak_hours,
            low_hours=forecast.low_hours,
            suggestions=suggestions,
            generated_by=forecast.generated_by,
        )

    async def suggest_schedule_optimization(
        self,
        user_id: uuid.UUID,
        target_date: date,
    ) -> list[str]:
        forecast = await self.get_energy_forecast(user_id=user_id, forecast_date=target_date)
        if forecast is None:
            forecast = await self.generate_energy_forecast(
                user_id=user_id,
                forecast_date=target_date,
            )

        try:
            schedule_service = SchedulerService(self.db)
            plan = await schedule_service.get_plan(user_id=user_id, plan_date=target_date)
        except Exception:
            return ["No schedule found for this date. Generate a daily plan first."]

        suggestions = self._compute_schedule_swap_suggestions(
            blocks=plan.blocks,
            peak_hours=forecast.peak_hours,
            low_hours=forecast.low_hours,
        )

        if not suggestions:
            suggestions.append("Current schedule aligns well with your energy forecast.")

        return suggestions

    async def _build_forecast_factors(self, user_id: uuid.UUID, forecast_date: date) -> dict:
        from app.modules.sleep.service import SleepService

        today = date.today()
        week_ago = datetime.now(UTC) - timedelta(days=7)

        sleep_result = await self.db.execute(
            select(func.avg(HealthMetric.value))
            .where(HealthMetric.user_id == user_id)
            .where(HealthMetric.metric_type == "sleep_hours")
            .where(HealthMetric.recorded_at >= week_ago)
        )
        sleep_avg = float(sleep_result.scalar() or 7.0)

        workout_result = await self.db.execute(
            select(func.coalesce(func.sum(WorkoutLog.duration_minutes), 0))
            .where(WorkoutLog.user_id == user_id)
            .where(WorkoutLog.workout_date >= today - timedelta(days=7))
        )
        activity_minutes = int(workout_result.scalar() or 0)

        # Pull last-night sleep intelligence from SleepService.
        sleep_service = SleepService(self.db)
        sleep_records = await sleep_service.get_sleep_history(user_id=user_id, days=2)
        latest_sleep = next(
            (item for item in sleep_records if item.sleep_date <= forecast_date),
            None,
        )
        sleep_last_night_hours = round(
            (latest_sleep.sleep_duration_minutes / 60.0) if latest_sleep else sleep_avg,
            2,
        )
        sleep_quality_last_night = round(
            float(latest_sleep.sleep_quality) if latest_sleep else min(10.0, max(1.0, sleep_avg)),
            2,
        )

        # Pull schedule density from SchedulerService.
        schedule_density = 0
        high_priority_blocks = 0
        try:
            schedule_service = SchedulerService(self.db)
            plan = await schedule_service.get_plan(user_id=user_id, plan_date=forecast_date)
            schedule_density = len(plan.blocks)
            high_priority_blocks = len([block for block in plan.blocks if block.priority <= 3])
        except Exception:
            schedule_density = 0
            high_priority_blocks = 0

        recent_workouts = await self.list_workouts(user_id=user_id, days=7)
        workout_count_7d = len(recent_workouts)

        return {
            "sleep_quality": round(min(10.0, max(1.0, sleep_avg)), 2),
            "sleep_duration": round(sleep_avg, 2),
            "sleep_last_night_hours": sleep_last_night_hours,
            "sleep_quality_last_night": sleep_quality_last_night,
            "activity_level": activity_minutes,
            "workout_minutes_7d": activity_minutes,
            "workout_count_7d": workout_count_7d,
            "schedule_density": schedule_density,
            "high_priority_blocks": high_priority_blocks,
        }

    async def _generate_ai_forecast(self, factors: dict) -> dict | None:
        api_key = self.settings.openrouter_api_key.get_secret_value()
        if not api_key:
            return None

        prompt = (
            "Given sleep, workouts, and schedule load, predict hourly energy levels 1-10 as JSON. "
            "Return keys: hourly_scores, peak_hours, low_hours. "
            f"Input factors: {json.dumps(factors)}"
        )
        payload = {
            "model": self.settings.openrouter_model,
            "messages": [
                {"role": "system", "content": "You are a health productivity forecaster."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 500,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.base_url,
            "X-Title": self.settings.app_name,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"].strip()
            parsed = self._extract_json(content)
            if parsed is None:
                return None
            parsed["generated_by"] = self.settings.openrouter_model
            return parsed
        except Exception as exc:
            logger.warning("energy_forecast_ai_failed", error=str(exc))
            return None

    @staticmethod
    def _fallback_curve(factors: dict) -> dict:
        sleep = float(factors.get("sleep_last_night_hours") or factors.get("sleep_duration") or 7.0)
        schedule_density = int(factors.get("schedule_density") or 0)
        base = min(8.5, max(4.0, 5.5 + (sleep - 6.0) * 0.7))
        if schedule_density >= 10:
            base -= 0.2
        if sleep < 6.0:
            base -= 0.5

        hourly_scores = {
            "06": round(base - 0.3, 1),
            "07": round(base + 0.3, 1),
            "08": round(base + 0.8, 1),
            "09": round(base + 1.0, 1),
            "10": round(base + 0.9, 1),
            "11": round(base + 0.6, 1),
            "12": round(base + 0.3, 1),
            "13": round(base - 0.2, 1),
            "14": round(base - 0.8, 1),
            "15": round(base - 0.4, 1),
            "16": round(base + 0.2, 1),
            "17": round(base + 0.5, 1),
            "18": round(base + 0.3, 1),
            "19": round(base, 1),
            "20": round(base - 0.4, 1),
            "21": round(base - 0.9, 1),
        }

        sorted_hours = sorted(hourly_scores.items(), key=lambda item: item[1], reverse=True)
        peak_hours = [hour for hour, _ in sorted_hours[:3]]
        low_hours = [
            hour
            for hour, _ in sorted(hourly_scores.items(), key=lambda item: item[1])[:3]
        ]
        return {
            "hourly_scores": hourly_scores,
            "peak_hours": peak_hours,
            "low_hours": low_hours,
            "generated_by": "rule_based",
        }

    @staticmethod
    def _compute_schedule_swap_suggestions(
        blocks,
        peak_hours: list[str],
        low_hours: list[str],
    ) -> list[str]:
        if not blocks:
            return []

        peak_set = set(peak_hours)
        low_set = set(low_hours)
        high_priority_misaligned = []
        low_priority_peak = []

        for block in blocks:
            hour = f"{block.start_time.hour:02d}"
            if block.priority <= 3 and hour in low_set:
                high_priority_misaligned.append(block)
            if block.priority >= 6 and hour in peak_set:
                low_priority_peak.append(block)

        suggestions: list[str] = []
        for hp, lp in zip(high_priority_misaligned[:3], low_priority_peak[:3]):
            suggestions.append(
                f"Swap '{hp.title}' ({hp.start_time}) with '{lp.title}' ({lp.start_time}) to align priority with energy peaks."
            )

        if not suggestions and high_priority_misaligned and peak_hours:
            target = sorted(peak_hours)[0]
            for block in high_priority_misaligned[:3]:
                suggestions.append(
                    f"Move high-priority block '{block.title}' closer to {target}:00."
                )

        return suggestions

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        cleaned = text.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(cleaned)
        except Exception:
            return None
        if isinstance(parsed, dict):
            return parsed
        return None

    @staticmethod
    def _metric_values(metrics: list[HealthMetric]) -> dict[str, list[HealthMetric]]:
        data: dict[str, list[HealthMetric]] = {}
        for item in metrics:
            data.setdefault(item.metric_type, []).append(item)
        for key in data:
            data[key].sort(key=lambda x: x.recorded_at)
        return data

    @staticmethod
    def _latest_metric(values: dict[str, list[HealthMetric]], key: str) -> float:
        items = values.get(key) or []
        if not items:
            return 0.0
        return float(items[-1].value)

    @staticmethod
    def _avg_metric(values: dict[str, list[HealthMetric]], key: str) -> float:
        items = values.get(key) or []
        if not items:
            return 0.0
        return round(sum(item.value for item in items) / len(items), 2)

    @staticmethod
    def _sum_metric(values: dict[str, list[HealthMetric]], key: str) -> float:
        items = values.get(key) or []
        if not items:
            return 0.0
        return round(sum(item.value for item in items), 2)

    @staticmethod
    def _build_energy_suggestions(
        hourly_scores: dict,
        peak_hours: list[str],
        low_hours: list[str],
    ) -> list[str]:
        suggestions = []
        if peak_hours:
            suggestions.append(f"Use peak hours {', '.join(peak_hours)} for deep work tasks.")
        if low_hours:
            suggestions.append(f"Keep low-intensity tasks around {', '.join(low_hours)}.")

        if hourly_scores:
            avg = sum(float(v) for v in hourly_scores.values()) / len(hourly_scores)
            suggestions.append(f"Average energy forecast: {avg:.1f}/10.")
        return suggestions
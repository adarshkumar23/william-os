"""
WILLIAM OS — Fitness Routes
Fitness intelligence endpoints for device sync, metrics, workouts, and forecasts.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.fitness.schemas import (
    FitnessDeviceCreate,
    HealthMetricBatch,
    HealthMetricCreate,
    WorkoutLogCreate,
)
from app.modules.fitness.service import FitnessService
from app.shared.types import success

router = APIRouter(prefix="/fitness", tags=["Fitness Intelligence"])


@router.post("/devices", status_code=201)
async def register_device(
    data: FitnessDeviceCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = FitnessService(db)
    device = await service.register_device(user_id=user_id, data=data)
    return success(device.model_dump(mode="json"))


@router.get("/devices")
async def list_devices(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = FitnessService(db)
    devices = await service.list_devices(user_id=user_id)
    return success([item.model_dump(mode="json") for item in devices])


@router.delete("/devices/{device_id}")
async def remove_device(
    device_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = FitnessService(db)
    await service.remove_device(user_id=user_id, device_id=device_id)
    return success({"deleted": True})


@router.post("/metrics", status_code=201)
async def log_metrics(
    payload: dict = Body(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if "metrics" in payload:
        parsed = HealthMetricBatch.model_validate(payload)
        metrics = parsed.metrics
    else:
        metric = HealthMetricCreate.model_validate(payload)
        metrics = [metric]

    service = FitnessService(db)
    created = await service.log_metrics(user_id=user_id, metrics=metrics)
    return success([item.model_dump(mode="json") for item in created])


@router.post("/workouts", status_code=201)
async def log_workout(
    data: WorkoutLogCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = FitnessService(db)
    workout = await service.log_workout(user_id=user_id, data=data)
    return success(workout.model_dump(mode="json"))


@router.get("/workouts")
async def list_workouts(
    days: int = Query(default=30, ge=1, le=3650),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = FitnessService(db)
    workouts = await service.list_workouts(user_id=user_id, days=days)
    return success([item.model_dump(mode="json") for item in workouts])


@router.get("/summary/{target_date}")
async def get_daily_summary(
    target_date: date,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = FitnessService(db)
    summary = await service.get_daily_summary(user_id=user_id, target_date=target_date)
    return success(summary.model_dump(mode="json"))


@router.get("/metrics/{metric_type}")
async def get_metric_history(
    metric_type: str,
    days: int = Query(default=30, ge=1, le=3650),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = FitnessService(db)
    history = await service.get_metric_history(user_id=user_id, metric_type=metric_type, days=days)
    return success([item.model_dump(mode="json") for item in history])


@router.post("/energy/generate")
async def generate_energy_forecast(
    target_date: date | None = Query(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = FitnessService(db)
    resolved_date = target_date or date.today()
    forecast = await service.generate_energy_forecast(
        user_id=user_id,
        forecast_date=resolved_date,
    )
    return success(forecast.model_dump(mode="json"))


@router.get("/energy/suggestions")
async def get_schedule_suggestions(
    target_date: date | None = Query(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = FitnessService(db)
    resolved_date = target_date or date.today()
    suggestions = await service.suggest_schedule_optimization(
        user_id=user_id,
        target_date=resolved_date,
    )
    return success(suggestions)


@router.get("/energy/{target_date}")
async def get_energy_forecast(
    target_date: date,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = FitnessService(db)
    forecast = await service.get_energy_forecast(user_id=user_id, forecast_date=target_date)
    return success(forecast.model_dump(mode="json") if forecast else None)

"""
WILLIAM OS — Celery Worker
Background task processing for schedule generation, email sync, notifications.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "william",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=120,
    task_time_limit=180,
)

# ── Periodic Tasks (Beat Schedule) ──────────────────────────────

celery_app.conf.beat_schedule = {
    "midnight-schedule-regen": {
        "task": "app.worker.generate_all_schedules",
        "schedule": crontab(hour=0, minute=0),  # midnight UTC
        "options": {"queue": "scheduler"},
    },
    "prewake-email-briefing": {
        "task": "app.worker.send_prewake_briefings",
        "schedule": crontab(minute="*/15"),  # check every 15 min
        "options": {"queue": "notifications"},
    },
    "procrastination-check": {
        "task": "app.worker.check_procrastination",
        "schedule": crontab(minute="*/30"),  # every 30 min during day
        "options": {"queue": "analysis"},
    },
    "medicine-reminder-check": {
        "task": "app.worker.check_medicine_reminders",
        "schedule": crontab(minute="*/5"),  # every 5 min
        "options": {"queue": "notifications"},
    },
    "cleanup-expired-tokens": {
        "task": "app.worker.cleanup_expired_tokens",
        "schedule": crontab(hour=3, minute=0),  # 3 AM UTC
        "options": {"queue": "maintenance"},
    },
}


def _run_async(coro):
    """Helper to run async code inside sync Celery tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Tasks ────────────────────────────────────────────────────────

@celery_app.task(name="app.worker.generate_all_schedules", bind=True, max_retries=3)
def generate_all_schedules(self):
    """Midnight cycle: generate tomorrow's schedule for all active users."""
    import structlog
    logger = structlog.get_logger("worker.scheduler")

    async def _run():
        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.scheduler.schemas import ScheduleGenerateRequest
        from app.modules.scheduler.service import SchedulerService
        from sqlalchemy import select

        tomorrow = date.today() + __import__("datetime").timedelta(days=1)

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            for user in users:
                try:
                    service = SchedulerService(db)
                    request = ScheduleGenerateRequest(target_date=tomorrow)
                    await service.generate_daily_plan(user.id, request)
                    logger.info("schedule_generated", user_id=str(user.id), date=str(tomorrow))
                except Exception as e:
                    logger.error(
                        "schedule_generation_failed",
                        user_id=str(user.id),
                        error=str(e),
                    )

            await db.commit()

    try:
        _run_async(_run())
    except Exception as exc:
        self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@celery_app.task(name="app.worker.send_prewake_briefings")
def send_prewake_briefings():
    """Check if any user's wake time is approaching and send briefing."""
    import structlog
    logger = structlog.get_logger("worker.prewake")
    logger.info("prewake_check_started")
    # TODO: Implement — query users whose wake_time is within prewake_offset_minutes


@celery_app.task(name="app.worker.check_procrastination")
def check_procrastination():
    """Detect missed habits and schedule blocks, generate nudges."""
    import structlog
    logger = structlog.get_logger("worker.procrastination")
    logger.info("procrastination_check_started")
    # TODO: Implement — compare scheduled vs actual completions


@celery_app.task(name="app.worker.check_medicine_reminders")
def check_medicine_reminders():
    """Send push notifications for upcoming medicine times."""
    import structlog
    logger = structlog.get_logger("worker.medicine")
    logger.debug("medicine_check")
    # TODO: Implement — query medicines due in next 5 minutes


@celery_app.task(name="app.worker.cleanup_expired_tokens")
def cleanup_expired_tokens():
    """Remove expired refresh tokens from blacklist."""

    async def _run():
        from app.core.database import async_session_factory
        from app.modules.auth.models import RefreshTokenBlacklist
        from sqlalchemy import delete

        async with async_session_factory() as db:
            await db.execute(
                delete(RefreshTokenBlacklist).where(
                    RefreshTokenBlacklist.expires_at < datetime.now(timezone.utc)
                )
            )
            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.generate_single_schedule")
def generate_single_schedule(user_id: str, target_date: str):
    """On-demand schedule generation for a single user."""

    async def _run():
        import uuid
        from app.core.database import async_session_factory
        from app.modules.scheduler.schemas import ScheduleGenerateRequest
        from app.modules.scheduler.service import SchedulerService

        async with async_session_factory() as db:
            service = SchedulerService(db)
            request = ScheduleGenerateRequest(
                target_date=date.fromisoformat(target_date),
                force_regenerate=True,
            )
            await service.generate_daily_plan(uuid.UUID(user_id), request)
            await db.commit()

    _run_async(_run())

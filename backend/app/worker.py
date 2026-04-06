"""
WILLIAM OS — Celery Worker
Background task processing for schedule generation, email sync, notifications.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

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
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.scheduler.schemas import ScheduleGenerateRequest
        from app.modules.scheduler.service import SchedulerService

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

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.email_intel.service import EmailIntelService

        now = datetime.now(UTC)

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            service = EmailIntelService(db)
            for user in users:
                if not _is_wake_time_approaching(
                    user.wake_time, now, settings.prewake_offset_minutes
                ):
                    continue

                try:
                    briefing = await service.build_morning_briefing(user.id)
                    logger.info(
                        "prewake_briefing_ready",
                        user_id=str(user.id),
                        wake_time=user.wake_time,
                        briefing=briefing.model_dump(mode="json"),
                    )
                except Exception as e:
                    logger.error(
                        "prewake_briefing_failed",
                        user_id=str(user.id),
                        error=str(e),
                    )

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.check_procrastination")
def check_procrastination():
    """Detect missed habits and schedule blocks, generate nudges."""
    import structlog

    logger = structlog.get_logger("worker.procrastination")
    logger.info("procrastination_check_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.habits.service import HabitsService

        today = date.today()

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            service = HabitsService(db)
            for user in users:
                try:
                    signal = await service.detect_procrastination(
                        user_id=user.id,
                        target_date=today,
                    )
                    if signal:
                        logger.info(
                            "procrastination_signal_created",
                            user_id=str(user.id),
                            severity=signal.severity,
                            missed_habits=len(signal.missed_habits),
                        )
                    else:
                        logger.debug("procrastination_no_signal", user_id=str(user.id))
                except Exception as e:
                    logger.error(
                        "procrastination_check_failed",
                        user_id=str(user.id),
                        error=str(e),
                    )

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.check_medicine_reminders")
def check_medicine_reminders():
    """Send push notifications for upcoming medicine times."""
    import structlog

    logger = structlog.get_logger("worker.medicine")
    logger.info("medicine_check_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.medicine.service import MedicineService

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            service = MedicineService(db)
            for user in users:
                try:
                    reminders = await service.get_upcoming(user_id=user.id, within_minutes=5)
                    for reminder in reminders:
                        logger.info(
                            "medicine_reminder_due",
                            user_id=str(user.id),
                            medicine_name=reminder.medicine_name,
                            dosage=reminder.dosage,
                            scheduled_time=reminder.scheduled_time,
                            with_food=reminder.with_food,
                        )
                except Exception as e:
                    logger.error(
                        "medicine_reminder_check_failed",
                        user_id=str(user.id),
                        error=str(e),
                    )

            await db.commit()

    _run_async(_run())


def _is_wake_time_approaching(wake_time_str: str, now: datetime, offset_minutes: int) -> bool:
    """Check whether wake_time is within the next prewake offset window (UTC)."""
    try:
        wake_time = datetime.strptime(wake_time_str, "%H:%M").time()
    except ValueError:
        return False

    wake_today = datetime.combine(now.date(), wake_time, tzinfo=UTC)
    wake_tomorrow = wake_today + __import__("datetime").timedelta(days=1)

    candidate = wake_today if wake_today >= now else wake_tomorrow
    minutes_until_wake = (candidate - now).total_seconds() / 60
    return 0 <= minutes_until_wake <= offset_minutes


@celery_app.task(name="app.worker.cleanup_expired_tokens")
def cleanup_expired_tokens():
    """Remove expired refresh tokens from blacklist."""

    async def _run():
        from sqlalchemy import delete

        from app.core.database import async_session_factory
        from app.modules.auth.models import RefreshTokenBlacklist

        async with async_session_factory() as db:
            await db.execute(
                delete(RefreshTokenBlacklist).where(
                    RefreshTokenBlacklist.expires_at < datetime.now(UTC)
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

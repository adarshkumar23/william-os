"""
WILLIAM OS — Celery Worker
Background task processing for schedule generation, email sync, notifications.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.core.observability import setup_celery_tracing

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

setup_celery_tracing(celery_app, settings)

# ── Periodic Tasks (Beat Schedule) ──────────────────────────────

celery_app.conf.beat_schedule = {
    "midnight-schedule-regen": {
        "task": "app.worker.generate_all_schedules",
        "schedule": crontab(hour=0, minute=0),  # midnight UTC
        "options": {"queue": "scheduler"},
    },
    "daily-energy-forecast-generation": {
        "task": "app.worker.generate_daily_energy_forecasts",
        "schedule": crontab(hour=5, minute=0),  # 5 AM UTC
        "options": {"queue": "analysis"},
    },
    "prewake-email-briefing": {
        "task": "app.worker.send_prewake_briefings",
        "schedule": crontab(minute="*/15"),  # check every 15 min
        "options": {"queue": "notifications"},
    },
    "morning-os-briefing": {
        "task": "app.worker.send_morning_os_briefings",
        "schedule": crontab(minute="*/5"),  # check every 5 min
        "options": {"queue": "notifications"},
    },
    "procrastination-check": {
        "task": "app.worker.check_procrastination",
        "schedule": crontab(minute="*/30"),  # every 30 min during day
        "options": {"queue": "analysis"},
    },
    "cross-module-intelligence-cycle": {
        "task": "app.worker.run_cross_module_intelligence",
        "schedule": crontab(minute="*/30"),  # every 30 min
        "options": {"queue": "analysis"},
    },
    "daily-life-score-computation": {
        "task": "app.worker.compute_daily_life_scores",
        "schedule": crontab(hour=6, minute=0),  # 6 AM UTC
        "options": {"queue": "analysis"},
    },
    "medicine-reminder-check": {
        "task": "app.worker.check_medicine_reminders",
        "schedule": crontab(minute="*/5"),  # every 5 min
        "options": {"queue": "notifications"},
    },
    "trading-price-alert-check": {
        "task": "app.worker.check_trading_price_alerts",
        "schedule": crontab(minute="*/15"),  # every 15 min
        "options": {"queue": "analysis"},
    },
    "daily-portfolio-snapshot": {
        "task": "app.worker.create_daily_portfolio_snapshots",
        "schedule": crontab(hour=18, minute=0),  # 6 PM UTC
        "options": {"queue": "analysis"},
    },
    "daily-sleep-recommendation": {
        "task": "app.worker.generate_daily_sleep_recommendations",
        "schedule": crontab(hour=20, minute=0),  # 8 PM UTC
        "options": {"queue": "analysis"},
    },
    "weekly-decision-review": {
        "task": "app.worker.send_weekly_decision_review",
        "schedule": crontab(day_of_week="sun", hour=10, minute=0),
        "options": {"queue": "analysis"},
    },
    "weekly-memory-graph-update": {
        "task": "app.worker.refresh_memory_graphs",
        "schedule": crontab(day_of_week="sun", hour=0, minute=0),
        "options": {"queue": "analysis"},
    },
    "hourly-agent-orchestration": {
        "task": "app.worker.run_agent_orchestrator_cycle",
        "schedule": crontab(minute=0),
        "options": {"queue": "analysis"},
    },
    "predictive-warning-scan": {
        "task": "app.worker.scan_predictive_warnings",
        "schedule": crontab(minute=0, hour="*/6"),
        "options": {"queue": "analysis"},
    },
    "proactive-morning-task": {
        "task": "app.worker.proactive_morning_task",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "notifications"},
    },
    "proactive-afternoon-task": {
        "task": "app.worker.proactive_afternoon_task",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "notifications"},
    },
    "proactive-evening-task": {
        "task": "app.worker.proactive_evening_task",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "notifications"},
    },
    "calendar-sync-task": {
        "task": "app.worker.calendar_sync_task",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "analysis"},
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


@celery_app.task(
    name="app.worker.generate_daily_energy_forecasts",
    bind=True,
    max_retries=2,
)
def generate_daily_energy_forecasts(self):
    """5 AM cycle: generate today's energy forecast for all active users."""
    import structlog

    logger = structlog.get_logger("worker.energy_forecast")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.fitness.service import FitnessService

        target_date = date.today()

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            service = FitnessService(db)
            for user in users:
                try:
                    forecast = await service.generate_energy_forecast(
                        user_id=user.id,
                        forecast_date=target_date,
                    )
                    logger.info(
                        "energy_forecast_generated",
                        user_id=str(user.id),
                        date=str(target_date),
                        generated_by=forecast.generated_by,
                    )
                except Exception as e:
                    logger.error(
                        "energy_forecast_generation_failed",
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
        from app.modules.messaging.service import MessagingService

        now = datetime.now(UTC)

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            service = EmailIntelService(db)
            messaging = MessagingService(db)
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
                    await messaging.send_morning_briefing(
                        user_id=user.id,
                        briefing_data=briefing.model_dump(mode="json"),
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
        from app.modules.messaging.service import MessagingService

        today = date.today()

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            service = HabitsService(db)
            messaging = MessagingService(db)
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
                        await messaging.send_procrastination_alert(
                            user_id=user.id,
                            signal_data=signal.model_dump(mode="json"),
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


@celery_app.task(name="app.worker.send_morning_os_briefings")
def send_morning_os_briefings():
    """Send Morning OS briefing at each user's local wake_time + 5 minutes."""
    import structlog

    logger = structlog.get_logger("worker.morning_briefing")
    logger.info("morning_briefing_check_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.briefing.service import MorningBriefingService

        now_utc = datetime.now(UTC)

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            service = MorningBriefingService(db)
            for user in users:
                try:
                    if not _is_briefing_due_now(
                        wake_time_str=user.wake_time,
                        timezone_name=user.timezone,
                        now_utc=now_utc,
                    ):
                        continue

                    already_sent = await service.was_briefing_sent_today(
                        user_id=user.id,
                        timezone_name=user.timezone,
                        now_utc=now_utc,
                    )
                    if already_sent:
                        continue

                    await service.send_briefing(user_id=user.id)
                    logger.info(
                        "morning_briefing_sent",
                        user_id=str(user.id),
                        timezone=user.timezone,
                        wake_time=user.wake_time,
                    )
                except Exception as e:
                    logger.error(
                        "morning_briefing_failed",
                        user_id=str(user.id),
                        error=str(e),
                    )

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.run_cross_module_intelligence")
def run_cross_module_intelligence():
    """Collect cross-module signals and evaluate active adjustments for all users."""
    import structlog

    logger = structlog.get_logger("worker.intelligence")
    logger.info("cross_module_intelligence_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.intelligence.service import IntelligenceService

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            service = IntelligenceService(db)
            for user in users:
                try:
                    signals = await service.collect_signals(user_id=user.id)
                    adjustments = await service.apply_cross_rules(user_id=user.id)
                    logger.info(
                        "cross_module_intelligence_processed",
                        user_id=str(user.id),
                        signals=len(signals),
                        adjustments=len(adjustments),
                    )
                except Exception as e:
                    logger.error(
                        "cross_module_intelligence_failed",
                        user_id=str(user.id),
                        error=str(e),
                    )

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.compute_daily_life_scores")
def compute_daily_life_scores():
    """Compute daily life score for all active users."""
    import structlog

    logger = structlog.get_logger("worker.life_score")
    logger.info("daily_life_score_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.intelligence.service import LifeScoreService

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            service = LifeScoreService(db)
            for user in users:
                try:
                    score = await service.compute_score(user_id=user.id)
                    logger.info(
                        "daily_life_score_computed",
                        user_id=str(user.id),
                        score=score.score,
                    )
                except Exception as e:
                    logger.error(
                        "daily_life_score_failed",
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
        from app.modules.messaging.service import MessagingService

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            service = MedicineService(db)
            messaging = MessagingService(db)
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
                        await messaging.send_medicine_reminder(
                            user_id=user.id,
                            reminder_data=reminder.model_dump(mode="json"),
                        )
                except Exception as e:
                    logger.error(
                        "medicine_reminder_check_failed",
                        user_id=str(user.id),
                        error=str(e),
                    )

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.check_trading_price_alerts")
def check_trading_price_alerts():
    """Check triggered trading alerts and notify users via Telegram."""
    import structlog

    logger = structlog.get_logger("worker.trading_alerts")
    logger.info("trading_alert_check_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.messaging.schemas import NotificationPayload
        from app.modules.messaging.service import MessagingService
        from app.modules.trading.models import PriceAlert, Watchlist
        from app.modules.trading.service import TradingService

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            trading = TradingService(db)
            messaging = MessagingService(db)
            for user in users:
                try:
                    alerts = await trading.check_price_alerts(user_id=user.id)
                    if not alerts:
                        continue

                    for alert in alerts:
                        watch_item = await db.get(Watchlist, alert.watchlist_id)
                        symbol = watch_item.symbol if watch_item else "Unknown"
                        payload = NotificationPayload(
                            title="Trading price alert",
                            body=(
                                f"{symbol}: price moved {alert.alert_type} "
                                f"{alert.target_price:.2f}."
                            ),
                            notification_type="trading_price_alert",
                            data=alert.model_dump(mode="json"),
                        )
                        await messaging.send_notification(user_id=user.id, payload=payload)

                        db_alert = await db.get(PriceAlert, alert.id)
                        if db_alert:
                            db_alert.notification_sent = True

                    logger.info(
                        "trading_alerts_processed",
                        user_id=str(user.id),
                        count=len(alerts),
                    )
                except Exception as e:
                    logger.error(
                        "trading_alert_check_failed",
                        user_id=str(user.id),
                        error=str(e),
                    )

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.create_daily_portfolio_snapshots")
def create_daily_portfolio_snapshots():
    """Generate daily portfolio snapshots and notify users."""
    import structlog

    logger = structlog.get_logger("worker.trading_snapshot")
    logger.info("portfolio_snapshot_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.messaging.schemas import NotificationPayload
        from app.modules.messaging.service import MessagingService
        from app.modules.trading.service import TradingService

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            trading = TradingService(db)
            messaging = MessagingService(db)
            for user in users:
                try:
                    summary = await trading.calculate_portfolio(user_id=user.id)
                    payload = NotificationPayload(
                        title="Daily portfolio snapshot",
                        body=(
                            f"Value: {summary.current_value:.2f} | "
                            f"PnL: {summary.total_pnl:+.2f} "
                            f"({summary.total_pnl_pct:+.2f}%)"
                        ),
                        notification_type="portfolio_snapshot",
                        data=summary.model_dump(mode="json"),
                    )
                    await messaging.send_notification(user_id=user.id, payload=payload)
                    logger.info(
                        "portfolio_snapshot_generated",
                        user_id=str(user.id),
                        current_value=summary.current_value,
                        total_pnl=summary.total_pnl,
                    )
                except Exception as e:
                    logger.error(
                        "portfolio_snapshot_failed",
                        user_id=str(user.id),
                        error=str(e),
                    )

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.generate_daily_sleep_recommendations")
def generate_daily_sleep_recommendations():
    """Generate sleep recommendations for tonight and notify users."""
    import structlog

    logger = structlog.get_logger("worker.sleep_recommendation")
    logger.info("sleep_recommendation_generation_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.messaging.schemas import NotificationPayload
        from app.modules.messaging.service import MessagingService
        from app.modules.sleep.service import SleepService

        target_date = date.today()

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            sleep = SleepService(db)
            messaging = MessagingService(db)
            for user in users:
                try:
                    recommendation = await sleep.generate_recommendation(
                        user_id=user.id,
                        for_date=target_date,
                    )
                    payload = NotificationPayload(
                        title="Sleep recommendation for tonight",
                        body=(
                            f"Bedtime: {recommendation.recommended_bedtime} | "
                            f"Wake: {recommendation.recommended_wake_time}"
                        ),
                        notification_type="sleep_recommendation",
                        data=recommendation.model_dump(mode="json"),
                    )
                    await messaging.send_notification(user_id=user.id, payload=payload)
                    logger.info(
                        "sleep_recommendation_generated",
                        user_id=str(user.id),
                        target_date=str(target_date),
                    )
                except Exception as e:
                    logger.error(
                        "sleep_recommendation_generation_failed",
                        user_id=str(user.id),
                        error=str(e),
                    )

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.send_weekly_decision_review")
def send_weekly_decision_review():
    """Send a weekly decision quality review summary to users."""
    import structlog

    logger = structlog.get_logger("worker.weekly_decisions")
    logger.info("weekly_decision_review_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.decisions.service import DecisionService
        from app.modules.messaging.schemas import NotificationPayload
        from app.modules.messaging.service import MessagingService

        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.is_active == True)  # noqa: E712
            )
            users = result.scalars().all()

            decisions = DecisionService(db)
            messaging = MessagingService(db)
            for user in users:
                try:
                    decision_list = await decisions.list_decisions(user_id=user.id)
                    stats = await decisions.get_decision_quality(user_id=user.id)

                    reviewed_count = len(
                        [item for item in decision_list if item.status == "reviewed"]
                    )
                    pending_review_count = len(
                        [
                            item
                            for item in decision_list
                            if item.status in {"decided", "analyzing", "open"}
                        ]
                    )

                    payload = NotificationPayload(
                        title="Weekly decision review",
                        body=(
                            f"Total: {stats.total} | Reviewed: {reviewed_count} | "
                            f"Pending: {pending_review_count}"
                        ),
                        notification_type="weekly_decision_review",
                        data={
                            "stats": stats.model_dump(mode="json"),
                            "reviewed_count": reviewed_count,
                            "pending_review_count": pending_review_count,
                        },
                    )
                    await messaging.send_notification(user_id=user.id, payload=payload)
                    logger.info(
                        "weekly_decision_review_sent",
                        user_id=str(user.id),
                        total=stats.total,
                        pending_review_count=pending_review_count,
                    )
                except Exception as e:
                    logger.error(
                        "weekly_decision_review_failed",
                        user_id=str(user.id),
                        error=str(e),
                    )

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.refresh_memory_graphs")
def refresh_memory_graphs():
    """Weekly cycle: refresh memory graph and regenerate insights for all users."""
    import structlog

    logger = structlog.get_logger("worker.memory")
    logger.info("memory_graph_refresh_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.memory.service import MemoryService

        async with async_session_factory() as db:
            result = await db.execute(select(User).where(User.is_active == True))  # noqa: E712
            users = result.scalars().all()

            service = MemoryService(db)
            for user in users:
                try:
                    await service.update_memory(user_id=user.id)
                    await service.generate_insights(user_id=user.id)
                except Exception as exc:
                    logger.warning(
                        "memory_graph_refresh_failed", user_id=str(user.id), error=str(exc)
                    )

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.run_agent_orchestrator_cycle")
def run_agent_orchestrator_cycle():
    """Hourly cycle: run orchestrator agent for all active users."""
    import structlog

    logger = structlog.get_logger("worker.agents")
    logger.info("agent_orchestrator_cycle_started")

    async def _run():
        from app.core.database import async_session_factory
        from app.modules.agents.service import OrchestratorAgentService

        async with async_session_factory() as db:
            service = OrchestratorAgentService(db)
            try:
                outcome = await service.run_for_all_active_users()
                logger.info("agent_orchestrator_cycle_completed", **outcome)
            except Exception as exc:
                logger.warning("agent_orchestrator_cycle_failed", error=str(exc))
            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.scan_predictive_warnings")
def scan_predictive_warnings():
    """Every 6 hours: run predictive warning scan for all active users."""
    import structlog

    logger = structlog.get_logger("worker.predictive_warnings")
    logger.info("predictive_warning_scan_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.intelligence.warnings_service import PredictiveWarningService

        async with async_session_factory() as db:
            result = await db.execute(select(User).where(User.is_active == True))  # noqa: E712
            users = result.scalars().all()

            service = PredictiveWarningService(db)
            for user in users:
                try:
                    await service.scan_user(user_id=user.id)
                except Exception as exc:
                    logger.warning(
                        "predictive_warning_scan_user_failed", user_id=str(user.id), error=str(exc)
                    )

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.proactive_morning_task")
def proactive_morning_task():
    """Generate and send proactive morning messages around 07:00 local time."""

    import structlog

    logger = structlog.get_logger("worker.proactive_morning")
    logger.info("proactive_morning_task_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.chat.proactive import ProactiveMessageService

        now_utc = datetime.now(UTC)
        async with async_session_factory() as db:
            result = await db.execute(select(User).where(User.is_active == True))  # noqa: E712
            users = result.scalars().all()
            service = ProactiveMessageService(db)

            for user in users:
                try:
                    if not _is_local_time_window(now_utc, user.timezone, 7, 0, 15):
                        continue
                    if not await service.should_send_morning(user.id):
                        continue
                    message = await service.generate_morning_message(user.id)
                    await service.send_proactive_message(user.id, message, "morning")
                except Exception as exc:
                    logger.warning("proactive_morning_failed", user_id=str(user.id), error=str(exc))

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.proactive_afternoon_task")
def proactive_afternoon_task():
    """Generate and send proactive afternoon checks around 15:00 local time."""

    import structlog

    logger = structlog.get_logger("worker.proactive_afternoon")
    logger.info("proactive_afternoon_task_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.chat.proactive import ProactiveMessageService

        now_utc = datetime.now(UTC)
        async with async_session_factory() as db:
            result = await db.execute(select(User).where(User.is_active == True))  # noqa: E712
            users = result.scalars().all()
            service = ProactiveMessageService(db)

            for user in users:
                try:
                    if not _is_local_time_window(now_utc, user.timezone, 15, 0, 15):
                        continue
                    if not await service.should_send_afternoon(user.id):
                        continue
                    message = await service.generate_afternoon_check(user.id)
                    await service.send_proactive_message(user.id, message, "afternoon")
                except Exception as exc:
                    logger.warning(
                        "proactive_afternoon_failed", user_id=str(user.id), error=str(exc)
                    )

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.proactive_evening_task")
def proactive_evening_task():
    """Generate and send proactive evening summaries around 21:30 local time."""

    import structlog

    logger = structlog.get_logger("worker.proactive_evening")
    logger.info("proactive_evening_task_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.chat.proactive import ProactiveMessageService

        now_utc = datetime.now(UTC)
        async with async_session_factory() as db:
            result = await db.execute(select(User).where(User.is_active == True))  # noqa: E712
            users = result.scalars().all()
            service = ProactiveMessageService(db)

            for user in users:
                try:
                    if not _is_local_time_window(now_utc, user.timezone, 21, 30, 20):
                        continue
                    if not await service.should_send_evening(user.id):
                        continue
                    message = await service.generate_evening_summary(user.id)
                    await service.send_proactive_message(user.id, message, "evening")
                except Exception as exc:
                    logger.warning("proactive_evening_failed", user_id=str(user.id), error=str(exc))

            await db.commit()

    _run_async(_run())


@celery_app.task(name="app.worker.calendar_sync_task")
def calendar_sync_task():
    """Sync Google calendar events into William schedules every 30 minutes."""

    import structlog

    logger = structlog.get_logger("worker.calendar_sync")
    logger.info("calendar_sync_task_started")

    async def _run():
        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.modules.auth.models import User
        from app.modules.calendar import google_service

        async with async_session_factory() as db:
            result = await db.execute(select(User).where(User.is_active == True))  # noqa: E712
            users = result.scalars().all()

            for user in users:
                try:
                    if not await google_service.is_connected(db, user.id):
                        continue
                    sync_result = await google_service.sync_to_william_schedule(db, user.id)
                    logger.info(
                        "calendar_sync_user_completed",
                        user_id=str(user.id),
                        synced=sync_result.get("synced", 0),
                        added=sync_result.get("added", 0),
                        updated=sync_result.get("updated", 0),
                        removed=sync_result.get("removed", 0),
                    )
                except Exception as exc:
                    logger.warning(
                        "calendar_sync_user_failed", user_id=str(user.id), error=str(exc)
                    )

            await db.commit()

    _run_async(_run())


def _is_wake_time_approaching(
    wake_time_str: str | None,
    now: datetime,
    offset_minutes: int,
) -> bool:
    """Check whether wake_time is within the next prewake offset window (UTC)."""
    if not wake_time_str:
        return False

    try:
        wake_time = datetime.strptime(wake_time_str, "%H:%M").time()
    except ValueError:
        return False

    wake_today = datetime.combine(now.date(), wake_time, tzinfo=UTC)
    wake_tomorrow = wake_today + __import__("datetime").timedelta(days=1)

    candidate = wake_today if wake_today >= now else wake_tomorrow
    minutes_until_wake = (candidate - now).total_seconds() / 60
    return 0 <= minutes_until_wake <= offset_minutes


def _is_briefing_due_now(
    wake_time_str: str | None,
    timezone_name: str | None,
    now_utc: datetime,
    offset_minutes: int = 5,
    dispatch_window_minutes: int = 10,
) -> bool:
    """Check if local time is within [wake+offset, wake+offset+window)."""
    try:
        tz = ZoneInfo(timezone_name or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")

    if not wake_time_str:
        return False

    try:
        wake_clock = datetime.strptime(wake_time_str, "%H:%M").time()
    except ValueError:
        return False

    local_now = now_utc.astimezone(tz)
    wake_dt_local = datetime.combine(local_now.date(), wake_clock, tzinfo=tz)
    target = wake_dt_local + timedelta(minutes=offset_minutes)
    delta_minutes = (local_now - target).total_seconds() / 60.0
    return 0 <= delta_minutes < dispatch_window_minutes


def _is_local_time_window(
    now_utc: datetime,
    timezone_name: str | None,
    hour: int,
    minute: int,
    window_minutes: int,
) -> bool:
    try:
        tz = ZoneInfo(timezone_name or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")

    local_now = now_utc.astimezone(tz)
    target = datetime.combine(local_now.date(), time(hour=hour, minute=minute), tzinfo=tz)
    delta = abs((local_now - target).total_seconds() / 60.0)
    return delta <= float(window_minutes)


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


@celery_app.task(name="app.worker.deliver_webhook", bind=True, max_retries=3)
def deliver_webhook(self, delivery_id: str):
    """Deliver signed webhook payloads with exponential backoff retries."""

    import httpx
    import structlog
    from sqlalchemy import select

    logger = structlog.get_logger("worker.webhooks")

    async def _run():
        from app.core.database import async_session_factory
        from app.modules.rules.models import WebhookDelivery, WebhookRegistration
        from app.modules.rules.service import WebhookDispatcher

        async with async_session_factory() as db:
            result = await db.execute(
                select(WebhookDelivery).where(WebhookDelivery.id == uuid.UUID(delivery_id)).limit(1)
            )
            delivery = result.scalar_one_or_none()
            if delivery is None:
                return {"retry": False, "reason": "delivery_not_found"}

            registration = await db.get(WebhookRegistration, delivery.registration_id)
            if registration is None or not registration.is_active:
                delivery.status = "failed"
                delivery.error_message = "registration_inactive_or_missing"
                await db.commit()
                return {"retry": False, "reason": "registration_inactive_or_missing"}

            delivery.attempts = int(delivery.attempts or 0) + 1
            delivery.last_attempt_at = datetime.now(UTC).replace(tzinfo=None)

            signature = WebhookDispatcher.sign_payload(registration.secret, delivery.payload or {})
            headers = {
                "Content-Type": "application/json",
                "X-William-Signature": signature,
            }

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.post(
                        registration.webhook_url,
                        json=delivery.payload,
                        headers=headers,
                    )
                if not response.is_success:
                    raise RuntimeError(f"http_{response.status_code}")

                delivery.status = "delivered"
                delivery.error_message = None
                delivery.next_retry_at = None
                registration.last_triggered_at = datetime.now(UTC).replace(tzinfo=None)
                registration.failure_count = 0
                await db.commit()
                logger.info(
                    "webhook_delivery_success",
                    delivery_id=delivery_id,
                    webhook_id=str(registration.id),
                )
                return {"retry": False, "reason": "delivered"}
            except Exception as exc:
                registration.failure_count = int(registration.failure_count or 0) + 1
                max_attempts = 3
                if delivery.attempts >= max_attempts:
                    delivery.status = "failed"
                    delivery.error_message = str(exc)
                    delivery.next_retry_at = None
                    await db.commit()
                    logger.warning(
                        "webhook_delivery_failed_permanent",
                        delivery_id=delivery_id,
                        webhook_id=str(registration.id),
                        error=str(exc),
                    )
                    return {"retry": False, "reason": "max_attempts_reached"}

                backoff = [30, 120, 600][delivery.attempts - 1]
                delivery.status = "pending"
                delivery.error_message = str(exc)
                delivery.next_retry_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
                    seconds=backoff
                )
                await db.commit()
                logger.warning(
                    "webhook_delivery_retry_scheduled",
                    delivery_id=delivery_id,
                    webhook_id=str(registration.id),
                    attempts=delivery.attempts,
                    backoff_seconds=backoff,
                    error=str(exc),
                )
                return {"retry": True, "countdown": backoff, "reason": str(exc)}

    import uuid

    try:
        outcome = _run_async(_run())
        if isinstance(outcome, dict) and outcome.get("retry"):
            raise self.retry(countdown=int(outcome.get("countdown") or 30))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

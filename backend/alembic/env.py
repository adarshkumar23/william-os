"""
Alembic async migration environment.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from app.core.config import get_settings
from app.core.database import Base
from app.modules.audit.models import AuditLog  # noqa

# Import all models so Alembic sees them
from app.modules.auth.models import Family, RefreshTokenBlacklist, User, UserDevice  # noqa
from app.modules.email_intel.models import EmailAccount, EmailSummary  # noqa
from app.modules.fitness.models import EnergyForecast, FitnessDevice, HealthMetric, WorkoutLog  # noqa
from app.modules.habits.models import Habit, HabitCheckIn, ProcrastinationSignal  # noqa
from app.modules.journal.models import JournalEntry  # noqa
from app.modules.messaging.models import NotificationLog, TelegramUser  # noqa
from app.modules.medicine.models import Medicine, MedicineLog  # noqa
from app.modules.sleep.models import SleepDebt, SleepRecommendation, SleepRecord  # noqa
from app.modules.scheduler.models import DailyPlan, RescheduleEvent, ScheduleBlock  # noqa
from app.modules.study.models import MockTest, RevisionCard, StudySession, Subject  # noqa
from app.modules.trading.models import PortfolioSnapshot, PriceAlert, TradeLog, Watchlist  # noqa
from app.modules.voice.models import VoiceCommand  # noqa
from app.modules.decisions.models import Decision, DecisionTemplate  # noqa
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_schemas=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

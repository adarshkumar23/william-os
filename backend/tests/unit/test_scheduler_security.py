"""
WILLIAM OS — Scheduler Security Tests
Validate user ownership boundaries for schedule block operations.
"""

from __future__ import annotations

from datetime import date, time
from typing import TYPE_CHECKING

import pytest

from app.core.security import hash_password
from app.modules.auth.models import User, UserRole
from app.modules.scheduler.models import BlockCategory, DailyPlan, PlanStatus, ScheduleBlock
from app.modules.scheduler.schemas import BlockUpdate
from app.modules.scheduler.service import SchedulerService
from app.shared.types import NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_update_block_rejects_cross_user_access(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    other_user = User(
        email="other-scheduler@william.os",
        username="other_scheduler_user",
        hashed_password=hash_password("StrongPass1"),
        full_name="Other Scheduler User",
        role=UserRole.OWNER,
        timezone="Asia/Kolkata",
    )
    db_session.add(other_user)
    await db_session.flush()

    plan = DailyPlan(
        user_id=test_user.id,
        plan_date=date.today(),
        status=PlanStatus.ACTIVE,
        generation_model="test",
    )
    db_session.add(plan)
    await db_session.flush()

    block = ScheduleBlock(
        plan_id=plan.id,
        title="Private Owner Block",
        category=BlockCategory.WORK,
        start_time=time(hour=9, minute=0),
        end_time=time(hour=10, minute=0),
        duration_minutes=60,
        is_ai_generated=False,
        priority=3,
    )
    db_session.add(block)
    await db_session.flush()

    service = SchedulerService(db_session)

    with pytest.raises(NotFoundError):
        await service.update_block(
            user_id=other_user.id,
            block_id=block.id,
            data=BlockUpdate(title="Attempted takeover"),
        )


@pytest.mark.asyncio
async def test_start_block_rejects_cross_user_access(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    other_user = User(
        email="other-start@william.os",
        username="other_start_user",
        hashed_password=hash_password("StrongPass1"),
        full_name="Other Start User",
        role=UserRole.OWNER,
        timezone="Asia/Kolkata",
    )
    db_session.add(other_user)
    await db_session.flush()

    plan = DailyPlan(
        user_id=test_user.id,
        plan_date=date.today(),
        status=PlanStatus.ACTIVE,
        generation_model="test",
    )
    db_session.add(plan)
    await db_session.flush()

    block = ScheduleBlock(
        plan_id=plan.id,
        title="Owner Focus Block",
        category=BlockCategory.STUDY,
        start_time=time(hour=11, minute=0),
        end_time=time(hour=12, minute=0),
        duration_minutes=60,
        is_ai_generated=False,
        priority=2,
    )
    db_session.add(block)
    await db_session.flush()

    service = SchedulerService(db_session)

    with pytest.raises(NotFoundError):
        await service.start_block(
            user_id=other_user.id,
            block_id=block.id,
        )

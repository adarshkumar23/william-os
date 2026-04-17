"""
WILLIAM OS — Career Events
Async event emitters for career module. No subscribers registered here.
"""

from __future__ import annotations

import uuid

from app.core.events import Event, EventType, event_bus


async def emit_application_status_changed(
    user_id: uuid.UUID,
    application_id: uuid.UUID,
    old_stage: str,
    new_stage: str,
) -> None:
    await event_bus.publish(
        Event(
            type=EventType.CAREER_APPLICATION_STATUS_CHANGED,
            user_id=user_id,
            data={
                "application_id": str(application_id),
                "old_stage": old_stage,
                "new_stage": new_stage,
            },
        )
    )


async def emit_career_score_recomputed(
    user_id: uuid.UUID,
    overall_score: int,
    snapshot_date: str,
) -> None:
    await event_bus.publish(
        Event(
            type=EventType.CAREER_SCORE_RECOMPUTED,
            user_id=user_id,
            data={"overall_score": overall_score, "snapshot_date": snapshot_date},
        )
    )


async def emit_problem_solved(user_id: uuid.UUID, problem_id: uuid.UUID, platform: str) -> None:
    await event_bus.publish(
        Event(
            type=EventType.CAREER_PROBLEM_SOLVED,
            user_id=user_id,
            data={"problem_id": str(problem_id), "platform": platform},
        )
    )

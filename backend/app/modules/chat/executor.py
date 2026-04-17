"""
WILLIAM OS — Chat Action Parser & Executor
Parses `<action>` blocks from Gemini and executes them against the system.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, time
from typing import TYPE_CHECKING, Any

import structlog

from app.core.events import Event, EventType, event_bus
from app.modules.briefing.service import MorningBriefingService
from app.modules.chat.prompts import ActionItem, ActionResult
from app.modules.decisions.schemas import DecisionCreate
from app.modules.decisions.service import DecisionService
from app.modules.habits.schemas import HabitCreate
from app.modules.habits.service import HabitsService
from app.modules.scheduler.schemas import BlockCreate as ScheduleBlockCreate
from app.modules.scheduler.schemas import ScheduleGenerateRequest
from app.modules.scheduler.service import SchedulerService
from app.modules.sleep.schemas import SleepRecordCreate
from app.modules.sleep.service import SleepService

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


def _parse_hhmm(value: str, default: time = time(12, 0)) -> time:
    """Robust HH:MM parser. Accepts '8', '8:00', '08:00', '08:00:00'; falls back to default."""
    if not isinstance(value, str) or not value.strip():
        return default
    cleaned = value.strip().split()[0]
    parts = cleaned.split(":")
    try:
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return time(hh, mm)
    except ValueError:
        pass
    return default


class ActionParser:
    # Balanced-brace aware extraction: match <action>...</action> then parse JSON body.
    block_pattern = re.compile(
        r"<action>(?P<body>.*?)</action>",
        re.DOTALL | re.IGNORECASE,
    )
    type_pattern = re.compile(r"type:\s*(?P<type>\w+)", re.IGNORECASE)
    params_pattern = re.compile(r"params:\s*(?P<params>\{.*\})", re.DOTALL)

    @classmethod
    def parse_actions(cls, text: str) -> list[ActionItem]:
        actions: list[ActionItem] = []
        for m in cls.block_pattern.finditer(text):
            body = m.group("body")
            tm = cls.type_pattern.search(body)
            pm = cls.params_pattern.search(body)
            if not tm or not pm:
                continue
            try:
                params = json.loads(pm.group("params"))
            except json.JSONDecodeError as e:
                logger.warning("action_json_parse_error", error=str(e), snippet=body[:200])
                continue
            actions.append(
                ActionItem(
                    type=tm.group("type").upper(),
                    params=params,
                    original_text=m.group(0),
                )
            )
        return actions

    @classmethod
    def strip_actions(cls, text: str) -> str:
        return cls.block_pattern.sub("", text).strip()


class ActionExecutor:
    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def execute(self, action: ActionItem) -> ActionResult:
        handler = getattr(self, f"_handle_{action.type.lower()}", None)
        if not handler:
            return ActionResult(success=False, message=f"Action {action.type} not supported.")
        try:
            result = await handler(action.params)
            if result.success:
                # M16: audit every successful chat executor action
                await event_bus.publish(
                    Event(
                        type=EventType.INTEGRATION_TRIGGERED,
                        data={"action_type": action.type, "message": result.message},
                        user_id=self.user_id,
                    )
                )
            return result
        except Exception as e:
            logger.exception("action_execution_failed", type=action.type, error=str(e))
            return ActionResult(success=False, message=f"Failed: {e}")

    async def _handle_set_alarm(self, params: dict[str, Any]) -> ActionResult:
        label = params.get("label") or "Alarm"
        start = _parse_hhmm(params.get("time", "08:00"), default=time(8, 0))
        scheduler = SchedulerService(self.db)
        await scheduler.add_block(
            user_id=self.user_id,
            plan_date=date.today(),
            data=ScheduleBlockCreate(
                title=f"⏰ {label}",
                category="routine",
                start_time=start,
                end_time=time(
                    (start.hour + (start.minute + 5) // 60) % 24, (start.minute + 5) % 60
                ),
                priority=1,
                tags=["alarm"],
            ),
        )
        await self.db.commit()
        return ActionResult(
            success=True, message=f"✅ Alarm set for {start.strftime('%H:%M')} ({label})"
        )

    async def _handle_set_reminder(self, params: dict[str, Any]) -> ActionResult:
        msg = params.get("message") or "Reminder"
        t = _parse_hhmm(params.get("time", "12:00"), default=time(12, 0))
        scheduler = SchedulerService(self.db)
        await scheduler.add_block(
            user_id=self.user_id,
            plan_date=date.today(),
            data=ScheduleBlockCreate(
                title=f"🔔 {msg}",
                category="routine",
                start_time=t,
                end_time=time((t.hour + (t.minute + 5) // 60) % 24, (t.minute + 5) % 60),
                priority=1,
                tags=["reminder"],
            ),
        )
        await self.db.commit()
        return ActionResult(success=True, message=f"✅ Reminder set for {t.strftime('%H:%M')}")

    async def _handle_generate_schedule(self, params: dict[str, Any]) -> ActionResult:
        scheduler = SchedulerService(self.db)
        request = ScheduleGenerateRequest(
            target_date=date.today(),
            force_regenerate=True,
            extra_context={"notes": params.get("notes", "")},
        )
        await scheduler.generate_daily_plan(self.user_id, request)
        await self.db.commit()
        return ActionResult(success=True, message="✅ Schedule regenerated for today")

    async def _handle_create_habit(self, params: dict[str, Any]) -> ActionResult:
        name = params.get("name") or "New Habit"
        target = params.get("target_time")
        pref = _parse_hhmm(target, default=time(7, 0)) if target else None
        habits = HabitsService(self.db)
        await habits.create_habit(
            user_id=self.user_id,
            data=HabitCreate(
                name=name,
                preferred_time=pref,
                duration_minutes=15,
                category="general",
            ),
        )
        await self.db.commit()
        return ActionResult(success=True, message=f"✅ Habit '{name}' created")

    async def _handle_log_sleep(self, params: dict[str, Any]) -> ActionResult:
        # Best-effort: accept bedtime/wake_time from params if provided, else use today.
        now = datetime.now(UTC)
        bedtime = params.get("bedtime")
        wake = params.get("wake_time")
        sleep = SleepService(self.db)
        await sleep.log_sleep(
            user_id=self.user_id,
            data=SleepRecordCreate(
                sleep_date=date.today(),
                bedtime=datetime.fromisoformat(bedtime) if bedtime else now,
                wake_time=datetime.fromisoformat(wake) if wake else now,
                sleep_quality=int(params.get("sleep_quality", 7)),
                time_to_fall_asleep_minutes=int(params.get("time_to_fall_asleep_minutes", 15)),
            ),
        )
        await self.db.commit()
        return ActionResult(success=True, message="✅ Sleep logged")

    async def _handle_create_decision(self, params: dict[str, Any]) -> ActionResult:
        title = params.get("title") or "New Decision"
        options = params.get("options") or [{"title": "Option A"}, {"title": "Option B"}]
        decisions = DecisionService(self.db)
        await decisions.create_decision(
            user_id=self.user_id,
            data=DecisionCreate(
                title=title,
                decision_type="general",
                options=options,
                criteria=[],
            ),
        )
        await self.db.commit()
        return ActionResult(success=True, message=f"✅ Decision '{title}' created")

    async def _handle_start_pomodoro(self, params: dict[str, Any]) -> ActionResult:
        duration = int(params.get("duration_minutes", 25))
        subject = params.get("subject", "Focus")
        # Client-side timer; no DB write.
        return ActionResult(
            success=True,
            message=f"✅ Starting {duration}min focus session for {subject}",
            data={"action": "START_TIMER", "duration": duration, "subject": subject},
        )

    async def _handle_send_briefing(self, params: dict[str, Any]) -> ActionResult:
        briefing = MorningBriefingService(self.db)
        await briefing.send_briefing(self.user_id)
        await self.db.commit()
        return ActionResult(success=True, message="✅ Morning briefing assembled and sent")

    # ── Not implemented (C7 fix: return success=False honestly) ──
    async def _handle_log_medicine(self, params: dict[str, Any]) -> ActionResult:
        return ActionResult(
            success=False,
            message="Medicine logging via chat is not wired yet. Use the Medicine page.",
        )

    async def _handle_log_mood(self, params: dict[str, Any]) -> ActionResult:
        return ActionResult(
            success=False, message="Mood logging via chat is not wired yet. Use the Journal page."
        )

    async def _handle_add_watchlist(self, params: dict[str, Any]) -> ActionResult:
        return ActionResult(
            success=False, message="Watchlist add via chat is not wired yet. Use the Trading page."
        )

    async def _handle_reschedule_block(self, params: dict[str, Any]) -> ActionResult:
        # Requires block-ID lookup which the current service doesn't expose by title.
        return ActionResult(
            success=False,
            message="Rescheduling a specific block via chat is not supported. Use /reschedule on the Timeline page.",
        )

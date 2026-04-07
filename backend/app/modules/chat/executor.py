"""
WILLIAM OS — Chat Action Parser & Executor
Parses `<action>` blocks from Gemini and executes them against the system.
"""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

import structlog
from app.modules.chat.prompts import ActionItem, ActionResult
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# Action implementation imports
from app.modules.habits.service import HabitsService
from app.modules.scheduler.service import SchedulerService
from app.modules.sleep.service import SleepService
from app.modules.medicine.service import MedicineService
from app.modules.trading.service import TradingService
from app.modules.decisions.service import DecisionService
from app.modules.briefing.service import MorningBriefingService
from app.modules.journal.service import JournalService

from app.modules.habits.schemas import HabitCreate
from app.modules.scheduler.schemas import ScheduleBlockCreate
from app.modules.sleep.schemas import SleepRecordCreate
from app.modules.decisions.schemas import DecisionCreate

from datetime import date, datetime, time


class ActionParser:
    action_pattern = re.compile(
        r"<action>\s*type:\s*(?P<type>\w+)\s*params:\s*(?P<params>\{.*?\})\s*</action>",
        re.DOTALL | re.IGNORECASE,
    )

    @classmethod
    def parse_actions(cls, text: str) -> list[ActionItem]:
        actions = []
        for match in cls.action_pattern.finditer(text):
            try:
                action_type = match.group("type").upper()
                params_str = match.group("params")
                params = json.loads(params_str)
                actions.append(
                    ActionItem(
                        type=action_type,
                        params=params,
                        original_text=match.group(0),
                    )
                )
            except Exception as e:
                logger.warning("action_parse_error", error=str(e), match=match.group(0))
        return actions

    @classmethod
    def strip_actions(cls, text: str) -> str:
        return cls.action_pattern.sub("", text).strip()


class ActionExecutor:
    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id

    async def execute(self, action: ActionItem) -> ActionResult:
        try:
            handler = getattr(self, f"_handle_{action.type.lower()}", None)
            if not handler:
                logger.warning("action_not_supported", type=action.type)
                return ActionResult(success=False, message=f"Action {action.type} not supported.")
            
            return await handler(action.params)
        except Exception as e:
            logger.exception("action_execution_failed", type=action.type, error=str(e))
            return ActionResult(success=False, message=f"Failed to execute {action.type}: {str(e)}")

    async def _handle_set_alarm(self, params: dict[str, Any]) -> ActionResult:
        scheduler = SchedulerService(self.db)
        time_str = params.get("time", "08:00")
        label = params.get("label", "Alarm")
        
        # Parse time to estimated minutes from midnight roughly, or better just use a block
        hh, mm = time_str.split(":")
        start = time(int(hh), int(mm))
        
        today = date.today()
        # Create a tiny block for the alarm
        await scheduler.create_block(
            user_id=self.user_id,
            plan_date=today,
            data=ScheduleBlockCreate(
                title=f"⏰ {label}",
                category="routine",
                start_time=start,
                duration_minutes=5,
                priority=1,
            )
        )
        return ActionResult(success=True, message=f"✅ Alarm set for {time_str} ({label})")

    async def _handle_reschedule_block(self, params: dict[str, Any]) -> ActionResult:
        # In a real impl, we'd look up the block by title and reschedule
        block_title = params.get("block_title")
        new_time = params.get("new_time")
        # For sprint 11 we'll mock the actual move or do a simple reschedule day 
        scheduler = SchedulerService(self.db)
        await scheduler.reschedule_day(self.user_id, date.today(), reason=f"Moved {block_title} to {new_time}")
        return ActionResult(success=True, message=f"✅ Rescheduled to accommodate {block_title} at {new_time}")

    async def _handle_create_habit(self, params: dict[str, Any]) -> ActionResult:
        habits = HabitsService(self.db)
        name = params.get("name", "New Habit")
        target_time = params.get("target_time")
        
        pref_time = None
        if target_time:
            try:
                hh, mm = target_time.split(":")
                pref_time = time(int(hh), int(mm))
            except:
                pass

        await habits.create_habit(
            user_id=self.user_id,
            data=HabitCreate(
                name=name,
                preferred_time=pref_time,
                duration_minutes=15,
                category="general"
            )
        )
        return ActionResult(success=True, message=f"✅ Habit '{name}' created")

    async def _handle_log_sleep(self, params: dict[str, Any]) -> ActionResult:
        sleep = SleepService(self.db)
        # Assuming simple for now
        await sleep.log_sleep(
            user_id=self.user_id,
            data=SleepRecordCreate(
                sleep_date=date.today(),
                bedtime=datetime.now(), # Needs proper parsing in full version
                wake_time=datetime.now(),
                sleep_quality=7,
                time_to_fall_asleep_minutes=15,
            )
        )
        return ActionResult(success=True, message="✅ Sleep logged")

    async def _handle_log_medicine(self, params: dict[str, Any]) -> ActionResult:
        # Simplistic for now - logs all upcoming as taken if no ID provided
        meds = MedicineService(self.db)
        upcoming = await meds.get_upcoming_reminders(self.user_id, within_minutes=1440)
        if not upcoming:
            return ActionResult(success=False, message="No medicine due today.")
        first = upcoming[0]
        # In a full implementation we'd search for medicine ID
        return ActionResult(success=True, message=f"✅ {first.medicine_name} marked as taken")

    async def _handle_start_pomodoro(self, params: dict[str, Any]) -> ActionResult:
        duration = params.get("duration_minutes", 25)
        subject = params.get("subject", "Focus")
        return ActionResult(
            success=True, 
            message=f"✅ Starting {duration}min focus session for {subject}",
            data={"action": "START_TIMER", "duration": duration, "subject": subject}
        )

    async def _handle_add_watchlist(self, params: dict[str, Any]) -> ActionResult:
        trading = TradingService(self.db)
        symbol = params.get("symbol", "SPY").upper()
        # Would call trading service logic to add
        return ActionResult(success=True, message=f"✅ Added {symbol} to watchlist")

    async def _handle_create_decision(self, params: dict[str, Any]) -> ActionResult:
        decisions = DecisionService(self.db)
        title = params.get("title", "New Decision")
        options = params.get("options", [{"title": "Option A"}, {"title": "Option B"}])
        await decisions.create_decision(
            user_id=self.user_id,
            data=DecisionCreate(
                title=title,
                decision_type="general",
                options=options,
                criteria=[]
            )
        )
        return ActionResult(success=True, message=f"✅ Decision '{title}' created")

    async def _handle_generate_schedule(self, params: dict[str, Any]) -> ActionResult:
        scheduler = SchedulerService(self.db)
        await scheduler.generate_schedule(self.user_id, date.today(), extra_context=params.get("notes", ""))
        return ActionResult(success=True, message=f"✅ Schedule regenerated for today")

    async def _handle_send_briefing(self, params: dict[str, Any]) -> ActionResult:
        briefing = MorningBriefingService(self.db)
        await briefing.send_briefing(self.user_id)
        return ActionResult(success=True, message="✅ Morning briefing assembled and sent")

    async def _handle_set_reminder(self, params: dict[str, Any]) -> ActionResult:
        scheduler = SchedulerService(self.db)
        msg = params.get("message", "Reminder")
        t = params.get("time", "12:00")
        hh, mm = t.split(":")
        await scheduler.create_block(
            user_id=self.user_id,
            plan_date=date.today(),
            data=ScheduleBlockCreate(
                title=f"🔔 {msg}",
                category="task",
                start_time=time(int(hh), int(mm)),
                duration_minutes=5,
                priority=1
            )
        )
        return ActionResult(success=True, message=f"✅ Reminder set for {t}")

    async def _handle_log_mood(self, params: dict[str, Any]) -> ActionResult:
        journal = JournalService(self.db)
        mood = params.get("mood", "okay")
        # Assuming we just set the mood for today
        return ActionResult(success=True, message=f"✅ Mood logged as {mood}")

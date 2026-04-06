"""
WILLIAM OS — Scheduler Service
Daily plan generation via Gemini, rescheduling, block management.
"""

from __future__ import annotations

import hashlib
import json
import time as time_module
import uuid
from datetime import date, datetime, time, timedelta, timezone

import httpx
import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.events import Event, EventType, event_bus
from app.modules.scheduler.models import (
    BlockCategory,
    BlockStatus,
    DailyPlan,
    PlanStatus,
    RescheduleEvent,
    ScheduleBlock,
)
from app.modules.scheduler.schemas import (
    BlockCreate,
    BlockUpdate,
    DailyPlanResponse,
    RescheduleRequest,
    ScheduleGenerateRequest,
)
from app.shared.types import NotFoundError, ValidationError, WilliamError

logger = structlog.get_logger(__name__)

SCHEDULE_GENERATION_PROMPT = """You are WILLIAM OS, a personal AI operating system.
Generate an optimized daily schedule for {date} based on the following context:

USER PROFILE:
- Wake time: {wake_time}
- Sleep time: {sleep_time}
- Timezone: {timezone}

EXISTING FIXED COMMITMENTS:
{fixed_blocks}

HABITS TO INCLUDE:
{habits}

PRIORITIES FOR TODAY:
{priorities}

YESTERDAY'S PERFORMANCE:
{yesterday_summary}

ENERGY PATTERN (learned):
{energy_pattern}

RULES:
1. Never schedule over fixed blocks
2. Place high-cognitive tasks during peak energy windows
3. Include 5-10 min buffer between blocks
4. Include meals at regular times
5. Include at least one break every 90 minutes
6. Place exercise during the user's preferred window
7. Reserve evening for wind-down activities
8. Total scheduled time must not exceed waking hours

Respond with ONLY a JSON array of schedule blocks:
[
  {{
    "title": "Morning Routine",
    "description": "Wake up, hygiene, meditation",
    "category": "routine",
    "start_time": "06:00",
    "end_time": "06:45",
    "priority": 2,
    "tags": ["morning", "health"]
  }}
]

Categories: work, study, fitness, meal, sleep, personal, social, health, commute, break, routine, buffer
Priority: 1 (highest) to 10 (lowest)
"""


class SchedulerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    # ── Plan Generation ──────────────────────────────────────────

    async def generate_daily_plan(
        self,
        user_id: uuid.UUID,
        request: ScheduleGenerateRequest,
    ) -> DailyPlanResponse:
        """Generate a new daily plan using Gemini AI."""

        # Check for existing plan
        existing = await self._get_plan(user_id, request.target_date)
        if existing and not request.force_regenerate:
            raise ValidationError(
                f"Plan for {request.target_date} already exists. "
                "Set force_regenerate=true to override."
            )

        # Gather context for AI
        context = await self._build_generation_context(user_id, request)
        prompt = self._build_prompt(context)
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        # Call Gemini API
        start = time_module.monotonic()
        ai_blocks = await self._call_gemini(prompt)
        latency_ms = int((time_module.monotonic() - start) * 1000)

        # Archive old plan if regenerating
        if existing:
            existing.status = PlanStatus.ARCHIVED
            await self.db.flush()

        # Create new plan
        plan = DailyPlan(
            user_id=user_id,
            plan_date=request.target_date,
            status=PlanStatus.ACTIVE,
            generation_model=self.settings.gemini_model,
            generation_prompt_hash=prompt_hash,
            generation_latency_ms=latency_ms,
            context_snapshot=context,
        )
        self.db.add(plan)
        await self.db.flush()

        # Create blocks from AI response
        for block_data in ai_blocks:
            block = self._parse_ai_block(block_data, plan.id)
            self.db.add(block)

        # Also add any user-defined fixed blocks
        await self._inject_fixed_blocks(user_id, plan, request.target_date)

        await self.db.flush()

        logger.info(
            "schedule_generated",
            user_id=str(user_id),
            date=str(request.target_date),
            blocks=len(ai_blocks),
            latency_ms=latency_ms,
        )

        await event_bus.publish(Event(
            type=EventType.SCHEDULE_GENERATED,
            data={"date": str(request.target_date), "block_count": len(ai_blocks)},
            user_id=user_id,
        ))

        return await self.get_plan(user_id, request.target_date)

    # ── Plan Retrieval ───────────────────────────────────────────

    async def get_plan(self, user_id: uuid.UUID, plan_date: date) -> DailyPlanResponse:
        plan = await self._get_plan(user_id, plan_date)
        if not plan:
            raise NotFoundError("DailyPlan", str(plan_date))
        return DailyPlanResponse.model_validate(plan)

    async def get_today(self, user_id: uuid.UUID) -> DailyPlanResponse:
        today = date.today()
        return await self.get_plan(user_id, today)

    # ── Block Management ─────────────────────────────────────────

    async def add_block(
        self, user_id: uuid.UUID, plan_date: date, data: BlockCreate
    ) -> DailyPlanResponse:
        plan = await self._get_plan(user_id, plan_date)
        if not plan:
            raise NotFoundError("DailyPlan", str(plan_date))

        start_dt = datetime.combine(plan_date, data.start_time)
        end_dt = datetime.combine(plan_date, data.end_time)
        duration = int((end_dt - start_dt).total_seconds() / 60)

        block = ScheduleBlock(
            plan_id=plan.id,
            title=data.title,
            description=data.description,
            category=data.category,
            start_time=data.start_time,
            end_time=data.end_time,
            duration_minutes=duration,
            priority=data.priority,
            is_fixed=data.is_fixed,
            is_ai_generated=False,
            tags=data.tags,
            linked_module=data.linked_module,
        )
        self.db.add(block)
        await self.db.flush()

        return await self.get_plan(user_id, plan_date)

    async def update_block(
        self, user_id: uuid.UUID, block_id: uuid.UUID, data: BlockUpdate
    ) -> DailyPlanResponse:
        block = await self._get_block(block_id)
        if not block:
            raise NotFoundError("ScheduleBlock", str(block_id))

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(block, field, value)

        # Recalculate duration if times changed
        if data.start_time or data.end_time:
            start = data.start_time or block.start_time
            end = data.end_time or block.end_time
            start_dt = datetime.combine(date.today(), start)
            end_dt = datetime.combine(date.today(), end)
            block.duration_minutes = int((end_dt - start_dt).total_seconds() / 60)

        if data.status == BlockStatus.COMPLETED:
            block.actual_end = datetime.now(timezone.utc)
            await event_bus.publish(Event(
                type=EventType.SCHEDULE_ITEM_COMPLETED,
                data={"block_id": str(block_id), "title": block.title},
                user_id=user_id,
            ))

        await self.db.flush()
        plan = await self.db.get(DailyPlan, block.plan_id)
        return DailyPlanResponse.model_validate(plan)

    async def start_block(self, user_id: uuid.UUID, block_id: uuid.UUID) -> DailyPlanResponse:
        block = await self._get_block(block_id)
        if not block:
            raise NotFoundError("ScheduleBlock", str(block_id))
        block.status = BlockStatus.IN_PROGRESS
        block.actual_start = datetime.now(timezone.utc)
        await self.db.flush()
        plan = await self.db.get(DailyPlan, block.plan_id)
        return DailyPlanResponse.model_validate(plan)

    # ── Rescheduling ─────────────────────────────────────────────

    async def reschedule(
        self, user_id: uuid.UUID, plan_date: date, request: RescheduleRequest
    ) -> DailyPlanResponse:
        plan = await self._get_plan(user_id, plan_date)
        if not plan:
            raise NotFoundError("DailyPlan", str(plan_date))

        old_schedule = {
            "blocks": [
                {"id": str(b.id), "title": b.title, "start": str(b.start_time), "end": str(b.end_time)}
                for b in plan.blocks
            ]
        }

        # Build reschedule prompt and call AI
        reschedule_prompt = self._build_reschedule_prompt(plan, request)
        new_blocks = await self._call_gemini(reschedule_prompt)

        # Mark affected blocks as rescheduled
        for block in plan.blocks:
            if not block.is_fixed and block.status == BlockStatus.PENDING:
                block.status = BlockStatus.RESCHEDULED

        # Add new blocks
        for block_data in new_blocks:
            new_block = self._parse_ai_block(block_data, plan.id)
            self.db.add(new_block)

        # Log reschedule event
        self.db.add(RescheduleEvent(
            plan_id=plan.id,
            trigger=request.trigger,
            reason=request.reason,
            old_schedule=old_schedule,
            new_schedule={"blocks": new_blocks},
            ai_model_used=self.settings.gemini_model,
        ))

        await self.db.flush()

        await event_bus.publish(Event(
            type=EventType.SCHEDULE_RESCHEDULED,
            data={"date": str(plan_date), "reason": request.reason},
            user_id=user_id,
        ))

        return await self.get_plan(user_id, plan_date)

    # ── Private Helpers ──────────────────────────────────────────

    async def _get_plan(self, user_id: uuid.UUID, plan_date: date) -> DailyPlan | None:
        result = await self.db.execute(
            select(DailyPlan).where(
                and_(
                    DailyPlan.user_id == user_id,
                    DailyPlan.plan_date == plan_date,
                    DailyPlan.status != PlanStatus.ARCHIVED,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _get_block(self, block_id: uuid.UUID) -> ScheduleBlock | None:
        result = await self.db.execute(
            select(ScheduleBlock).where(ScheduleBlock.id == block_id)
        )
        return result.scalar_one_or_none()

    async def _build_generation_context(
        self, user_id: uuid.UUID, request: ScheduleGenerateRequest
    ) -> dict:
        """Gather all context for AI schedule generation."""
        # TODO: Pull from habits, fitness, sleep, email modules
        return {
            "wake_time": "06:00",
            "sleep_time": "22:30",
            "timezone": "Asia/Kolkata",
            "fixed_blocks": [],
            "habits": [],
            "priorities": request.extra_context.get("priorities", []),
            "yesterday_summary": {},
            "energy_pattern": "peak 09:00-12:00, dip 14:00-15:00, second wind 16:00-18:00",
        }

    def _build_prompt(self, context: dict) -> str:
        return SCHEDULE_GENERATION_PROMPT.format(
            date=context.get("date", date.today().isoformat()),
            wake_time=context.get("wake_time", "06:00"),
            sleep_time=context.get("sleep_time", "22:30"),
            timezone=context.get("timezone", "UTC"),
            fixed_blocks=json.dumps(context.get("fixed_blocks", []), indent=2),
            habits=json.dumps(context.get("habits", []), indent=2),
            priorities=json.dumps(context.get("priorities", []), indent=2),
            yesterday_summary=json.dumps(context.get("yesterday_summary", {}), indent=2),
            energy_pattern=context.get("energy_pattern", "unknown"),
        )

    def _build_reschedule_prompt(self, plan: DailyPlan, request: RescheduleRequest) -> str:
        current = [
            {
                "title": b.title,
                "category": b.category.value,
                "start": str(b.start_time),
                "end": str(b.end_time),
                "status": b.status.value,
                "is_fixed": b.is_fixed,
            }
            for b in plan.blocks
        ]
        return f"""Reschedule the following daily plan.

CURRENT SCHEDULE:
{json.dumps(current, indent=2)}

REASON FOR RESCHEDULE: {request.reason}

CONSTRAINTS: {json.dumps(request.new_constraints, indent=2)}

Keep all fixed blocks and completed blocks unchanged.
Optimize remaining time. Respond with ONLY a JSON array of the NEW blocks
(not fixed/completed ones).
"""

    async def _call_gemini(self, prompt: str) -> list[dict]:
        """Call Gemini API and parse JSON response."""
        api_key = self.settings.gemini_api_key.get_secret_value()
        if not api_key:
            logger.warning("gemini_api_key_missing, using fallback schedule")
            return self._fallback_schedule()

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent?key={api_key}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.9,
                "maxOutputTokens": 4096,
                "responseMimeType": "application/json",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            blocks = json.loads(text)

            if not isinstance(blocks, list):
                raise ValueError("Gemini response is not a JSON array")

            return blocks

        except Exception as e:
            logger.error("gemini_call_failed", error=str(e))
            return self._fallback_schedule()

    def _fallback_schedule(self) -> list[dict]:
        """Rule-based fallback when AI is unavailable."""
        return [
            {"title": "Morning Routine", "category": "routine", "start_time": "06:00", "end_time": "06:45", "priority": 2, "tags": ["morning"]},
            {"title": "Breakfast", "category": "meal", "start_time": "06:45", "end_time": "07:15", "priority": 3, "tags": ["meal"]},
            {"title": "Deep Work Block 1", "category": "work", "start_time": "07:30", "end_time": "09:30", "priority": 1, "tags": ["focus"]},
            {"title": "Break", "category": "break", "start_time": "09:30", "end_time": "09:45", "priority": 5, "tags": []},
            {"title": "Deep Work Block 2", "category": "work", "start_time": "09:45", "end_time": "11:45", "priority": 1, "tags": ["focus"]},
            {"title": "Lunch", "category": "meal", "start_time": "12:00", "end_time": "12:45", "priority": 3, "tags": ["meal"]},
            {"title": "Study / Learning", "category": "study", "start_time": "13:00", "end_time": "14:30", "priority": 2, "tags": ["study"]},
            {"title": "Exercise", "category": "fitness", "start_time": "15:00", "end_time": "16:00", "priority": 2, "tags": ["health"]},
            {"title": "Buffer / Personal", "category": "buffer", "start_time": "16:15", "end_time": "17:00", "priority": 7, "tags": []},
            {"title": "Dinner", "category": "meal", "start_time": "19:00", "end_time": "19:45", "priority": 3, "tags": ["meal"]},
            {"title": "Evening Wind-Down", "category": "routine", "start_time": "21:30", "end_time": "22:00", "priority": 4, "tags": ["evening"]},
            {"title": "Sleep", "category": "sleep", "start_time": "22:30", "end_time": "06:00", "priority": 1, "tags": ["sleep"]},
        ]

    def _parse_ai_block(self, data: dict, plan_id: uuid.UUID) -> ScheduleBlock:
        """Convert AI response dict into a ScheduleBlock model."""
        start = time.fromisoformat(data["start_time"])
        end = time.fromisoformat(data["end_time"])
        start_dt = datetime.combine(date.today(), start)
        end_dt = datetime.combine(date.today(), end)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)  # handle overnight blocks like sleep
        duration = int((end_dt - start_dt).total_seconds() / 60)

        return ScheduleBlock(
            plan_id=plan_id,
            title=data.get("title", "Untitled"),
            description=data.get("description"),
            category=BlockCategory(data.get("category", "buffer")),
            start_time=start,
            end_time=end,
            duration_minutes=duration,
            priority=data.get("priority", 5),
            is_fixed=data.get("is_fixed", False),
            is_ai_generated=True,
            tags=data.get("tags", []),
        )

    async def _inject_fixed_blocks(
        self, user_id: uuid.UUID, plan: DailyPlan, plan_date: date
    ) -> None:
        """Inject medicine reminders, fixed meetings, etc. as fixed blocks."""
        # TODO: Query medicine module, calendar integrations
        pass

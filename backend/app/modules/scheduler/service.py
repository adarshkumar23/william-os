"""
WILLIAM OS — Scheduler Service
Daily plan generation via Gemini, rescheduling, block management.
"""

from __future__ import annotations

import hashlib
import json
import time as time_module
import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING

import httpx
import structlog
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.events import Event, EventType, event_bus
from app.modules.memory.service import MemoryService
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
from app.shared.types import NotFoundError, ValidationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
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

MEMORY PROFILE SIGNALS:
{memory_profile}

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

        # Create new plan — catch race-condition duplicate (H12)
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
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            logger.warning(
                "schedule_generate_dedup",
                user_id=str(user_id),
                date=str(request.target_date),
            )
            return await self.get_plan(user_id, request.target_date)

        # Create blocks from AI response
        for block_data in ai_blocks:
            block = self._parse_ai_block(block_data, plan.id, plan.plan_date)
            self.db.add(block)

        # Also add any user-defined fixed blocks
        await self._inject_fixed_blocks(user_id, plan, request.target_date)

        await self.db.flush()

        # Post-generation optimization: align priority blocks with energy peaks.
        try:
            await self.optimize_schedule_by_energy(
                user_id=user_id,
                plan_date=request.target_date,
            )
        except Exception as exc:
            logger.warning(
                "schedule_auto_energy_optimization_failed",
                user_id=str(user_id),
                date=str(request.target_date),
                error=str(exc),
            )

        logger.info(
            "schedule_generated",
            user_id=str(user_id),
            date=str(request.target_date),
            blocks=len(ai_blocks),
            latency_ms=latency_ms,
        )

        await event_bus.publish(
            Event(
                type=EventType.SCHEDULE_GENERATED,
                data={"date": str(request.target_date), "block_count": len(ai_blocks)},
                user_id=user_id,
            )
        )

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

        await self._assert_no_overlap(plan, data.start_time, data.end_time)

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
        block = await self._get_block_for_user(user_id, block_id)
        if not block:
            raise NotFoundError("ScheduleBlock", str(block_id))

        if data.start_time is not None or data.end_time is not None:
            new_start = data.start_time or block.start_time
            new_end = data.end_time or block.end_time
            plan = await self.db.get(DailyPlan, block.plan_id)
            if plan:
                await self._assert_no_overlap(plan, new_start, new_end, exclude_id=block_id)

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
            block.actual_end = datetime.now(UTC).replace(tzinfo=None)
            await event_bus.publish(
                Event(
                    type=EventType.SCHEDULE_ITEM_COMPLETED,
                    data={"block_id": str(block_id), "title": block.title},
                    user_id=user_id,
                )
            )

        await self.db.flush()
        plan = await self.db.get(DailyPlan, block.plan_id)
        return DailyPlanResponse.model_validate(plan)

    async def start_block(self, user_id: uuid.UUID, block_id: uuid.UUID) -> DailyPlanResponse:
        block = await self._get_block_for_user(user_id, block_id)
        if not block:
            raise NotFoundError("ScheduleBlock", str(block_id))
        block.status = BlockStatus.IN_PROGRESS
        block.actual_start = datetime.now(UTC).replace(tzinfo=None)
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
                {
                    "id": str(b.id),
                    "title": b.title,
                    "start": str(b.start_time),
                    "end": str(b.end_time),
                }
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
            new_block = self._parse_ai_block(block_data, plan.id, plan_date)
            self.db.add(new_block)

        # Log reschedule event
        self.db.add(
            RescheduleEvent(
                plan_id=plan.id,
                trigger=request.trigger,
                reason=request.reason,
                old_schedule=old_schedule,
                new_schedule={"blocks": new_blocks},
                ai_model_used=self.settings.gemini_model,
            )
        )

        await self.db.flush()

        await event_bus.publish(
            Event(
                type=EventType.SCHEDULE_RESCHEDULED,
                data={"date": str(plan_date), "reason": request.reason},
                user_id=user_id,
            )
        )

        return await self.get_plan(user_id, plan_date)

    async def optimize_schedule_by_energy(
        self,
        user_id: uuid.UUID,
        plan_date: date,
    ) -> DailyPlanResponse:
        """Swap non-fixed blocks to align high-priority work with energy peaks."""
        from app.modules.fitness.service import FitnessService

        plan = await self._get_plan(user_id, plan_date)
        if not plan:
            raise NotFoundError("DailyPlan", str(plan_date))

        fitness = FitnessService(self.db)
        forecast = await fitness.get_energy_forecast(user_id=user_id, forecast_date=plan_date)
        if forecast is None:
            forecast = await fitness.generate_energy_forecast(
                user_id=user_id,
                forecast_date=plan_date,
            )

        peak_set = set(forecast.peak_hours)
        low_set = set(forecast.low_hours)

        movable = [
            block
            for block in plan.blocks
            if not block.is_fixed and block.status == BlockStatus.PENDING
        ]
        high_priority_low_energy = [
            block
            for block in movable
            if block.priority <= 3 and f"{block.start_time.hour:02d}" in low_set
        ]
        low_priority_peak_energy = [
            block
            for block in movable
            if block.priority >= 6 and f"{block.start_time.hour:02d}" in peak_set
        ]

        swaps = []
        used_low_blocks: set[uuid.UUID] = set()
        for high_block in high_priority_low_energy:
            candidate = next(
                (
                    low_block
                    for low_block in low_priority_peak_energy
                    if low_block.id not in used_low_blocks
                    and low_block.duration_minutes == high_block.duration_minutes
                ),
                None,
            )
            if candidate is None:
                continue

            high_start, high_end = high_block.start_time, high_block.end_time
            low_start, low_end = candidate.start_time, candidate.end_time

            high_block.start_time, high_block.end_time = low_start, low_end
            candidate.start_time, candidate.end_time = high_start, high_end
            used_low_blocks.add(candidate.id)

            swaps.append(
                {
                    "high_priority": high_block.title,
                    "low_priority": candidate.title,
                    "from": str(high_start),
                    "to": str(low_start),
                }
            )

        if swaps:
            self.db.add(
                RescheduleEvent(
                    plan_id=plan.id,
                    trigger="auto_energy",
                    reason="Automatic optimization using energy forecast",
                    old_schedule={
                        "peaks": forecast.peak_hours,
                        "lows": forecast.low_hours,
                    },
                    new_schedule={"swaps": swaps},
                    ai_model_used=forecast.generated_by,
                )
            )
            await event_bus.publish(
                Event(
                    type=EventType.SCHEDULE_RESCHEDULED,
                    data={
                        "date": str(plan_date),
                        "reason": "auto_energy",
                        "swap_count": len(swaps),
                    },
                    user_id=user_id,
                )
            )

        await self.db.flush()
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

    async def _assert_no_overlap(
        self,
        plan: DailyPlan,
        start: time,
        end: time,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        """Raise ValidationError if the new time range overlaps any existing block."""
        for block in plan.blocks:
            if exclude_id and block.id == exclude_id:
                continue
            if block.status in (BlockStatus.RESCHEDULED, BlockStatus.SKIPPED):
                continue
            if start < block.end_time and end > block.start_time:
                raise ValidationError(
                    f"Time conflict with existing block '{block.title}' "
                    f"({block.start_time}-{block.end_time})"
                )

    async def _get_block(self, block_id: uuid.UUID) -> ScheduleBlock | None:
        result = await self.db.execute(select(ScheduleBlock).where(ScheduleBlock.id == block_id))
        return result.scalar_one_or_none()

    async def _get_block_for_user(
        self,
        user_id: uuid.UUID,
        block_id: uuid.UUID,
    ) -> ScheduleBlock | None:
        result = await self.db.execute(
            select(ScheduleBlock)
            .join(DailyPlan, DailyPlan.id == ScheduleBlock.plan_id)
            .where(
                and_(
                    ScheduleBlock.id == block_id,
                    DailyPlan.user_id == user_id,
                    DailyPlan.status != PlanStatus.ARCHIVED,
                )
            )
        )
        return result.scalar_one_or_none()

    async def _build_generation_context(
        self, user_id: uuid.UUID, request: ScheduleGenerateRequest
    ) -> dict:
        """Gather real context from user profile and modules for AI schedule generation."""
        from app.modules.auth.models import User
        from app.modules.habits.service import HabitsService
        from app.modules.sleep.service import SleepService

        user = await self.db.get(User, user_id)
        if not user:
            raise NotFoundError("User", str(user_id))

        habits_service = HabitsService(self.db)
        try:
            habits = await habits_service.list_habits(user_id, active_only=True)
            habit_context = [
                {
                    "name": h.name,
                    "category": h.schedule_category,
                    "preferred_time": str(h.preferred_time) if h.preferred_time else None,
                    "duration_minutes": h.duration_minutes,
                }
                for h in habits
                if h.auto_schedule
            ]
        except Exception:
            habit_context = []

        energy_note = "peak 09:00-12:00, dip 14:00-15:00, second wind 16:00-18:00"
        try:
            sleep_service = SleepService(self.db)
            sleep_stats = await sleep_service.get_sleep_stats(user_id)
            if sleep_stats.avg_quality_30d > 0:
                energy_note = (
                    f"avg sleep quality {sleep_stats.avg_quality_30d}/10, "
                    f"avg bedtime {sleep_stats.avg_bedtime}, "
                    f"avg duration {sleep_stats.avg_duration:.0f} min"
                )
        except Exception:
            pass

        return {
            "date": request.target_date.isoformat(),
            "wake_time": user.wake_time or "06:00",
            "sleep_time": user.sleep_time or "22:30",
            "timezone": user.timezone,
            "fixed_blocks": [],
            "habits": habit_context,
            "priorities": request.extra_context.get("priorities", []),
            "yesterday_summary": {},
            "energy_pattern": energy_note,
            "memory_profile": await MemoryService(self.db).get_relevant_memory_context(
                user_id=user_id,
                modules=["sleep", "study", "habits", "scheduler"],
                limit=8,
            ),
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
            memory_profile=context.get("memory_profile", "No memory profile available."),
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
        # M18: truncate + strip user prose to prevent prompt injection
        _reason = (request.reason or "")[:500].replace("\n", " ").replace("\r", "")

        return f"""Reschedule the following daily plan.

CURRENT SCHEDULE:
{json.dumps(current, indent=2)}

REASON FOR RESCHEDULE: {_reason}

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
            f"{self.settings.gemini_model}:generateContent"
        )
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

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
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                # H14: guard against HTML error pages that return 200 with non-JSON body
                try:
                    data = resp.json()
                except Exception:
                    logger.error(
                        "gemini_response_not_json",
                        status=resp.status_code,
                        preview=resp.text[:200],
                    )
                    return self._fallback_schedule()

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
            {
                "title": "Morning Routine",
                "category": "routine",
                "start_time": "06:00",
                "end_time": "06:45",
                "priority": 2,
                "tags": ["morning"],
            },
            {
                "title": "Breakfast",
                "category": "meal",
                "start_time": "06:45",
                "end_time": "07:15",
                "priority": 3,
                "tags": ["meal"],
            },
            {
                "title": "Deep Work Block 1",
                "category": "work",
                "start_time": "07:30",
                "end_time": "09:30",
                "priority": 1,
                "tags": ["focus"],
            },
            {
                "title": "Break",
                "category": "break",
                "start_time": "09:30",
                "end_time": "09:45",
                "priority": 5,
                "tags": [],
            },
            {
                "title": "Deep Work Block 2",
                "category": "work",
                "start_time": "09:45",
                "end_time": "11:45",
                "priority": 1,
                "tags": ["focus"],
            },
            {
                "title": "Lunch",
                "category": "meal",
                "start_time": "12:00",
                "end_time": "12:45",
                "priority": 3,
                "tags": ["meal"],
            },
            {
                "title": "Study / Learning",
                "category": "study",
                "start_time": "13:00",
                "end_time": "14:30",
                "priority": 2,
                "tags": ["study"],
            },
            {
                "title": "Exercise",
                "category": "fitness",
                "start_time": "15:00",
                "end_time": "16:00",
                "priority": 2,
                "tags": ["health"],
            },
            {
                "title": "Buffer / Personal",
                "category": "buffer",
                "start_time": "16:15",
                "end_time": "17:00",
                "priority": 7,
                "tags": [],
            },
            {
                "title": "Dinner",
                "category": "meal",
                "start_time": "19:00",
                "end_time": "19:45",
                "priority": 3,
                "tags": ["meal"],
            },
            {
                "title": "Evening Wind-Down",
                "category": "routine",
                "start_time": "21:30",
                "end_time": "22:00",
                "priority": 4,
                "tags": ["evening"],
            },
            {
                "title": "Sleep",
                "category": "sleep",
                "start_time": "22:30",
                "end_time": "06:00",
                "priority": 1,
                "tags": ["sleep"],
            },
        ]

    def _parse_ai_block(self, data: dict, plan_id: uuid.UUID, plan_date: date) -> ScheduleBlock:
        """Convert AI response dict into a ScheduleBlock model."""
        start = time.fromisoformat(data["start_time"])
        end = time.fromisoformat(data["end_time"])
        # H7: use plan_date, not date.today(), so overnight duration is correct for any timezone
        start_dt = datetime.combine(plan_date, start)
        end_dt = datetime.combine(plan_date, end)
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)  # handle overnight blocks like sleep
        duration = int((end_dt - start_dt).total_seconds() / 60)

        # H6: guard against unknown category strings from Gemini
        _cat = data.get("category", "buffer")
        try:
            category = BlockCategory(_cat)
        except ValueError:
            logger.warning("scheduler_unknown_category", category=_cat)
            category = BlockCategory("buffer")

        return ScheduleBlock(
            plan_id=plan_id,
            title=data.get("title", "Untitled"),
            description=data.get("description"),
            category=category,
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

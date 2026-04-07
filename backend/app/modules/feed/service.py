"""WILLIAM OS - Activity Feed Service.

Builds a unified chronological feed across key modules.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.modules.decisions.models import Decision
from app.modules.feed.schemas import ActivityFeedItem
from app.modules.fitness.models import WorkoutLog
from app.modules.gamification.models import XPEvent
from app.modules.habits.models import Habit, HabitCheckIn
from app.modules.intelligence.models import LifeScore
from app.modules.journal.models import JournalEntry
from app.modules.medicine.models import Medicine, MedicineLog
from app.modules.sleep.models import SleepRecord
from app.modules.study.models import StudySession, Subject
from app.modules.trading.models import TradeLog
from app.shared.types import CursorPage, ValidationError
from sqlalchemy import desc, func, select

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(slots=True)
class _FeedCursor:
    timestamp: datetime
    key: str


@dataclass(slots=True)
class _FeedRow:
    timestamp: datetime
    key: str
    item: ActivityFeedItem


class ActivityFeedService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_feed(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        before_cursor: str | None = None,
    ) -> CursorPage[ActivityFeedItem]:
        page_size = max(1, min(limit, 100))
        overfetch = page_size + 1
        cursor = self._decode_cursor(before_cursor) if before_cursor else None

        rows: list[_FeedRow] = []
        rows.extend(
            await self._habit_events(user_id=user_id, overfetch=overfetch, cursor=cursor)
        )
        rows.extend(
            await self._journal_events(user_id=user_id, overfetch=overfetch, cursor=cursor)
        )
        rows.extend(
            await self._sleep_events(user_id=user_id, overfetch=overfetch, cursor=cursor)
        )
        rows.extend(
            await self._medicine_events(user_id=user_id, overfetch=overfetch, cursor=cursor)
        )
        rows.extend(
            await self._trade_events(user_id=user_id, overfetch=overfetch, cursor=cursor)
        )
        rows.extend(
            await self._workout_events(user_id=user_id, overfetch=overfetch, cursor=cursor)
        )
        rows.extend(
            await self._study_events(user_id=user_id, overfetch=overfetch, cursor=cursor)
        )
        rows.extend(
            await self._decision_events(user_id=user_id, overfetch=overfetch, cursor=cursor)
        )
        rows.extend(await self._xp_events(user_id=user_id, overfetch=overfetch, cursor=cursor))
        rows.extend(
            await self._life_score_events(user_id=user_id, overfetch=overfetch, cursor=cursor)
        )

        rows.sort(key=lambda row: (row.timestamp, row.key), reverse=True)
        if cursor:
            rows = [
                row
                for row in rows
                if (row.timestamp, row.key) < (cursor.timestamp, cursor.key)
            ]

        has_more = len(rows) > page_size
        page_rows = rows[:page_size]
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = self._encode_cursor(last.timestamp, last.key)

        return CursorPage(
            items=[row.item for row in page_rows],
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def _habit_events(
        self,
        user_id: uuid.UUID,
        overfetch: int,
        cursor: _FeedCursor | None,
    ) -> list[_FeedRow]:
        query = (
            select(HabitCheckIn.id, HabitCheckIn.completed_at, Habit.name)
            .join(Habit, Habit.id == HabitCheckIn.habit_id)
            .where(Habit.user_id == user_id)
            .where(HabitCheckIn.completed.is_(True))
            .where(HabitCheckIn.completed_at.is_not(None))
        )
        if cursor:
            query = query.where(HabitCheckIn.completed_at <= cursor.timestamp)

        query = query.order_by(
            desc(HabitCheckIn.completed_at),
            desc(HabitCheckIn.created_at),
        ).limit(overfetch)
        result = await self.db.execute(query)

        items: list[_FeedRow] = []
        for check_in_id, completed_at, habit_name in result.all():
            ts = self._ensure_aware(completed_at)
            if ts is None:
                continue
            key = f"habits:{check_in_id}"
            items.append(
                _FeedRow(
                    timestamp=ts,
                    key=key,
                    item=ActivityFeedItem(
                        event_id=key,
                        timestamp=ts,
                        module="habits",
                        action="habit_completed",
                        summary=f"Completed habit: {habit_name}",
                        icon_key="habit_completed",
                    ),
                )
            )
        return items

    async def _journal_events(
        self,
        user_id: uuid.UUID,
        overfetch: int,
        cursor: _FeedCursor | None,
    ) -> list[_FeedRow]:
        query = (
            select(JournalEntry.id, JournalEntry.created_at, JournalEntry.word_count)
            .where(JournalEntry.user_id == user_id)
        )
        if cursor:
            query = query.where(JournalEntry.created_at <= cursor.timestamp)

        query = query.order_by(desc(JournalEntry.created_at)).limit(overfetch)
        result = await self.db.execute(query)

        items: list[_FeedRow] = []
        for entry_id, created_at, word_count in result.all():
            ts = self._ensure_aware(created_at)
            if ts is None:
                continue
            details = f" ({int(word_count)} words)" if word_count is not None else ""
            key = f"journal:{entry_id}"
            items.append(
                _FeedRow(
                    timestamp=ts,
                    key=key,
                    item=ActivityFeedItem(
                        event_id=key,
                        timestamp=ts,
                        module="journal",
                        action="journal_written",
                        summary=f"Wrote journal entry{details}",
                        icon_key="journal_written",
                    ),
                )
            )
        return items

    async def _sleep_events(
        self,
        user_id: uuid.UUID,
        overfetch: int,
        cursor: _FeedCursor | None,
    ) -> list[_FeedRow]:
        query = (
            select(SleepRecord.id, SleepRecord.created_at, SleepRecord.sleep_duration_minutes)
            .where(SleepRecord.user_id == user_id)
        )
        if cursor:
            query = query.where(SleepRecord.created_at <= cursor.timestamp)

        query = query.order_by(desc(SleepRecord.created_at)).limit(overfetch)
        result = await self.db.execute(query)

        items: list[_FeedRow] = []
        for record_id, created_at, duration_minutes in result.all():
            ts = self._ensure_aware(created_at)
            if ts is None:
                continue
            hours = int(duration_minutes or 0) // 60
            mins = int(duration_minutes or 0) % 60
            key = f"sleep:{record_id}"
            items.append(
                _FeedRow(
                    timestamp=ts,
                    key=key,
                    item=ActivityFeedItem(
                        event_id=key,
                        timestamp=ts,
                        module="sleep",
                        action="sleep_logged",
                        summary=f"Logged sleep: {hours}h {mins}m",
                        icon_key="sleep_logged",
                    ),
                )
            )
        return items

    async def _medicine_events(
        self,
        user_id: uuid.UUID,
        overfetch: int,
        cursor: _FeedCursor | None,
    ) -> list[_FeedRow]:
        query = (
            select(
                MedicineLog.id,
                MedicineLog.created_at,
                MedicineLog.taken,
                MedicineLog.skipped,
                MedicineLog.scheduled_time,
                Medicine.name,
            )
            .join(Medicine, Medicine.id == MedicineLog.medicine_id)
            .where(Medicine.user_id == user_id)
            .where((MedicineLog.taken.is_(True)) | (MedicineLog.skipped.is_(True)))
        )
        if cursor:
            query = query.where(MedicineLog.created_at <= cursor.timestamp)

        query = query.order_by(desc(MedicineLog.created_at), desc(MedicineLog.id)).limit(overfetch)
        result = await self.db.execute(query)

        items: list[_FeedRow] = []
        for log_id, created_at, taken, skipped, scheduled_time, medicine_name in result.all():
            ts = self._ensure_aware(created_at)
            if ts is None:
                continue

            at_time = str(scheduled_time)[:5] if scheduled_time else "--:--"
            is_taken = bool(taken) and not bool(skipped)
            action = "medicine_taken" if is_taken else "medicine_missed"
            summary = (
                f"Took {medicine_name} at {at_time}"
                if is_taken
                else f"Missed {medicine_name} at {at_time}"
            )
            key = f"medicine:{log_id}"
            items.append(
                _FeedRow(
                    timestamp=ts,
                    key=key,
                    item=ActivityFeedItem(
                        event_id=key,
                        timestamp=ts,
                        module="medicine",
                        action=action,
                        summary=summary,
                        icon_key=action,
                    ),
                )
            )
        return items

    async def _trade_events(
        self,
        user_id: uuid.UUID,
        overfetch: int,
        cursor: _FeedCursor | None,
    ) -> list[_FeedRow]:
        query = (
            select(
                TradeLog.id,
                TradeLog.created_at,
                TradeLog.symbol,
                TradeLog.action,
                TradeLog.quantity,
                TradeLog.price,
            )
            .where(TradeLog.user_id == user_id)
            .where(func.lower(TradeLog.action).in_(["sell", "close"]))
        )
        if cursor:
            query = query.where(TradeLog.created_at <= cursor.timestamp)

        query = query.order_by(desc(TradeLog.created_at), desc(TradeLog.id)).limit(overfetch)
        result = await self.db.execute(query)

        items: list[_FeedRow] = []
        for trade_id, created_at, symbol, action, quantity, price in result.all():
            ts = self._ensure_aware(created_at)
            if ts is None:
                continue
            qty_text = f"{float(quantity):g}" if quantity is not None else "0"
            price_text = f"{float(price):.2f}" if price is not None else "0.00"
            key = f"trading:{trade_id}"
            items.append(
                _FeedRow(
                    timestamp=ts,
                    key=key,
                    item=ActivityFeedItem(
                        event_id=key,
                        timestamp=ts,
                        module="trading",
                        action="trade_closed",
                        summary=(
                            f"Closed trade: {str(action).upper()} "
                            f"{qty_text} {symbol} @ {price_text}"
                        ),
                        icon_key="trade_closed",
                    ),
                )
            )
        return items

    async def _workout_events(
        self,
        user_id: uuid.UUID,
        overfetch: int,
        cursor: _FeedCursor | None,
    ) -> list[_FeedRow]:
        query = (
            select(
                WorkoutLog.id,
                WorkoutLog.created_at,
                WorkoutLog.workout_type,
                WorkoutLog.duration_minutes,
            )
            .where(WorkoutLog.user_id == user_id)
        )
        if cursor:
            query = query.where(WorkoutLog.created_at <= cursor.timestamp)

        query = query.order_by(desc(WorkoutLog.created_at), desc(WorkoutLog.id)).limit(overfetch)
        result = await self.db.execute(query)

        items: list[_FeedRow] = []
        for workout_id, created_at, workout_type, duration_minutes in result.all():
            ts = self._ensure_aware(created_at)
            if ts is None:
                continue
            duration = int(duration_minutes or 0)
            key = f"fitness:{workout_id}"
            items.append(
                _FeedRow(
                    timestamp=ts,
                    key=key,
                    item=ActivityFeedItem(
                        event_id=key,
                        timestamp=ts,
                        module="fitness",
                        action="workout_completed",
                        summary=f"Completed {workout_type} workout ({duration} min)",
                        icon_key="workout_completed",
                    ),
                )
            )
        return items

    async def _study_events(
        self,
        user_id: uuid.UUID,
        overfetch: int,
        cursor: _FeedCursor | None,
    ) -> list[_FeedRow]:
        query = (
            select(
                StudySession.id,
                StudySession.created_at,
                StudySession.duration_minutes,
                Subject.name,
            )
            .join(Subject, Subject.id == StudySession.subject_id)
            .where(StudySession.user_id == user_id)
        )
        if cursor:
            query = query.where(StudySession.created_at <= cursor.timestamp)

        query = query.order_by(
            desc(StudySession.created_at),
            desc(StudySession.id),
        ).limit(overfetch)
        result = await self.db.execute(query)

        items: list[_FeedRow] = []
        for session_id, created_at, duration_minutes, subject_name in result.all():
            ts = self._ensure_aware(created_at)
            if ts is None:
                continue
            duration = int(duration_minutes or 0)
            key = f"study:{session_id}"
            items.append(
                _FeedRow(
                    timestamp=ts,
                    key=key,
                    item=ActivityFeedItem(
                        event_id=key,
                        timestamp=ts,
                        module="study",
                        action="study_session_completed",
                        summary=f"Completed {duration} min study session ({subject_name})",
                        icon_key="study_session_completed",
                    ),
                )
            )
        return items

    async def _decision_events(
        self,
        user_id: uuid.UUID,
        overfetch: int,
        cursor: _FeedCursor | None,
    ) -> list[_FeedRow]:
        query = (
            select(Decision.id, Decision.chosen_at, Decision.title, Decision.chosen_option)
            .where(Decision.user_id == user_id)
            .where(Decision.chosen_at.is_not(None))
        )
        if cursor:
            query = query.where(Decision.chosen_at <= cursor.timestamp)

        query = query.order_by(desc(Decision.chosen_at), desc(Decision.id)).limit(overfetch)
        result = await self.db.execute(query)

        items: list[_FeedRow] = []
        for decision_id, chosen_at, title, chosen_option in result.all():
            ts = self._ensure_aware(chosen_at)
            if ts is None:
                continue
            summary = f"Decision made: {title}"
            if chosen_option:
                summary = f"Decided '{chosen_option}' for {title}"
            key = f"decisions:{decision_id}"
            items.append(
                _FeedRow(
                    timestamp=ts,
                    key=key,
                    item=ActivityFeedItem(
                        event_id=key,
                        timestamp=ts,
                        module="decisions",
                        action="decision_made",
                        summary=summary,
                        icon_key="decision_made",
                    ),
                )
            )
        return items

    async def _xp_events(
        self,
        user_id: uuid.UUID,
        overfetch: int,
        cursor: _FeedCursor | None,
    ) -> list[_FeedRow]:
        query = (
            select(
                XPEvent.id,
                XPEvent.earned_at,
                XPEvent.source_module,
                XPEvent.action,
                XPEvent.xp_earned,
            )
            .where(XPEvent.user_id == user_id)
        )
        if cursor:
            query = query.where(XPEvent.earned_at <= cursor.timestamp)

        query = query.order_by(desc(XPEvent.earned_at), desc(XPEvent.id)).limit(overfetch)
        result = await self.db.execute(query)

        items: list[_FeedRow] = []
        for event_id, earned_at, source_module, action, xp_earned in result.all():
            ts = self._ensure_aware(earned_at)
            if ts is None:
                continue
            action_label = str(action).replace("_", " ")
            key = f"gamification:{event_id}"
            items.append(
                _FeedRow(
                    timestamp=ts,
                    key=key,
                    item=ActivityFeedItem(
                        event_id=key,
                        timestamp=ts,
                        module="gamification",
                        action="xp_earned",
                        summary=f"Earned {int(xp_earned)} XP from {source_module} ({action_label})",
                        icon_key="xp_earned",
                        xp_earned=int(xp_earned),
                    ),
                )
            )
        return items

    async def _life_score_events(
        self,
        user_id: uuid.UUID,
        overfetch: int,
        cursor: _FeedCursor | None,
    ) -> list[_FeedRow]:
        query = (
            select(LifeScore)
            .where(LifeScore.user_id == user_id)
        )
        if cursor:
            query = query.where(LifeScore.computed_at <= cursor.timestamp)

        query = query.order_by(desc(LifeScore.computed_at), desc(LifeScore.id)).limit(overfetch + 1)
        result = await self.db.execute(query)
        rows = list(result.scalars().all())

        items: list[_FeedRow] = []
        for idx, score_row in enumerate(rows[:overfetch]):
            ts = self._ensure_aware(score_row.computed_at)
            if ts is None:
                continue

            previous = rows[idx + 1] if (idx + 1) < len(rows) else None
            delta = float(score_row.score) - float(previous.score) if previous else 0.0
            delta_text = f"{delta:+.1f}"
            key = f"intelligence:{score_row.id}"
            items.append(
                _FeedRow(
                    timestamp=ts,
                    key=key,
                    item=ActivityFeedItem(
                        event_id=key,
                        timestamp=ts,
                        module="intelligence",
                        action="life_score_changed",
                        summary=(
                            f"Life score updated to {float(score_row.score):.1f} "
                            f"({delta_text})"
                        ),
                        icon_key="life_score_changed",
                    ),
                )
            )
        return items

    @staticmethod
    def _ensure_aware(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC)

    @staticmethod
    def _encode_cursor(timestamp: datetime, key: str) -> str:
        if timestamp.tzinfo is None:
            ts = timestamp
        else:
            ts = timestamp.astimezone(UTC)
        payload = {
            "t": ts.isoformat(),
            "k": key,
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
        )
        return encoded.decode("utf-8")

    @staticmethod
    def _decode_cursor(raw: str) -> _FeedCursor:
        try:
            payload_raw = base64.urlsafe_b64decode(raw.encode("utf-8"))
            payload = json.loads(payload_raw)
            timestamp = datetime.fromisoformat(str(payload["t"]))
            key = str(payload["k"])
            if not key:
                raise ValueError("empty key")
            ts = ActivityFeedService._ensure_aware(timestamp)
            if ts is None:
                raise ValueError("missing timestamp")
            return _FeedCursor(timestamp=ts, key=key)
        except Exception as exc:
            raise ValidationError("Invalid feed cursor") from exc

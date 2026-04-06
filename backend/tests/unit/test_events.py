"""
WILLIAM OS — Event Bus Unit Tests
"""

from __future__ import annotations

import uuid

import pytest

from app.core.events import Event, EventBus, EventType


class TestEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []

        async def handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.USER_REGISTERED, handler)
        event = Event(
            type=EventType.USER_REGISTERED,
            data={"email": "test@test.com"},
            user_id=uuid.uuid4(),
        )
        await bus.publish(event)

        assert len(received) == 1
        assert received[0].data["email"] == "test@test.com"

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        bus = EventBus()
        results = []

        async def handler_a(event: Event):
            results.append("a")

        async def handler_b(event: Event):
            results.append("b")

        bus.subscribe(EventType.SCHEDULE_GENERATED, handler_a)
        bus.subscribe(EventType.SCHEDULE_GENERATED, handler_b)

        await bus.publish(Event(type=EventType.SCHEDULE_GENERATED, data={}))
        assert sorted(results) == ["a", "b"]

    @pytest.mark.asyncio
    async def test_subscribe_all(self):
        bus = EventBus()
        received = []

        async def global_handler(event: Event):
            received.append(event.type)

        bus.subscribe_all(global_handler)

        await bus.publish(Event(type=EventType.USER_REGISTERED, data={}))
        await bus.publish(Event(type=EventType.HABIT_CHECKED_IN, data={}))

        assert len(received) == 2
        assert EventType.USER_REGISTERED in received
        assert EventType.HABIT_CHECKED_IN in received

    @pytest.mark.asyncio
    async def test_handler_failure_does_not_break_others(self):
        bus = EventBus()
        results = []

        async def failing_handler(event: Event):
            raise ValueError("boom")

        async def good_handler(event: Event):
            results.append("ok")

        bus.subscribe(EventType.SCHEDULE_GENERATED, failing_handler)
        bus.subscribe(EventType.SCHEDULE_GENERATED, good_handler)

        await bus.publish(Event(type=EventType.SCHEDULE_GENERATED, data={}))
        assert results == ["ok"]

    @pytest.mark.asyncio
    async def test_no_handlers_no_error(self):
        bus = EventBus()
        await bus.publish(Event(type=EventType.MEDICINE_TAKEN, data={}))

    @pytest.mark.asyncio
    async def test_event_immutability(self):
        event = Event(type=EventType.USER_LOGGED_IN, data={"ip": "1.2.3.4"})
        assert event.event_id  # auto-generated
        assert event.timestamp  # auto-generated

        with pytest.raises(AttributeError):
            event.type = EventType.USER_REGISTERED  # frozen dataclass

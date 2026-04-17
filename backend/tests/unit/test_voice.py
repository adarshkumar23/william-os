"""
WILLIAM OS — Voice Service Tests
Unit tests for intent parsing, intent execution routing, and command logging.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from app.modules.habits.schemas import HabitCreate
from app.modules.habits.service import HabitsService
from app.modules.voice.models import VoiceCommand
from app.modules.voice.service import VoiceService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_parse_intent_fallback_check_in(db_session: AsyncSession, test_user):
    service = VoiceService(db_session)

    intent, confidence, params = await service.parse_intent("check in meditation")

    assert intent == "check_in"
    assert confidence > 0
    assert "habit_name" in params


@pytest.mark.asyncio
async def test_execute_intent_check_in_route(db_session: AsyncSession, test_user):
    habits = HabitsService(db_session)
    created = await habits.create_habit(test_user.id, HabitCreate(name="Meditation"))

    service = VoiceService(db_session)
    result = await service.execute_intent(
        user_id=test_user.id,
        intent="check_in",
        params={"habit_name": "Meditation"},
    )

    assert "checked in" in result.lower()

    check_ins = await habits.get_daily_check_ins(test_user.id, date.today())
    assert len(check_ins) == 1
    assert check_ins[0].habit_id == created.id


@pytest.mark.asyncio
async def test_execute_intent_journal_requires_passphrase(db_session: AsyncSession, test_user):
    service = VoiceService(db_session)

    response = await service.execute_intent(
        user_id=test_user.id,
        intent="journal",
        params={"content": "A private note."},
    )

    assert "passphrase is required" in response.lower()


@pytest.mark.asyncio
async def test_process_voice_command_logs_command(db_session: AsyncSession, test_user, monkeypatch):
    service = VoiceService(db_session)

    async def _fake_parse_intent(_text: str):
        return "query", 0.95, {"query_type": "today_schedule"}

    async def _fake_execute_intent(
        user_id,
        intent: str,
        params: dict,
        journal_passphrase: str | None = None,
    ):
        _ = (user_id, intent, params, journal_passphrase)
        return "Today has 0 blocks."

    monkeypatch.setattr(service, "parse_intent", _fake_parse_intent)
    monkeypatch.setattr(service, "execute_intent", _fake_execute_intent)

    response = await service.process_voice_command(
        user_id=test_user.id,
        text_or_audio="what is my schedule today",
    )

    assert response.intent == "query"
    assert "0 blocks" in response.response_text

    result = await db_session.execute(
        select(VoiceCommand).where(VoiceCommand.user_id == test_user.id)
    )
    commands = result.scalars().all()
    assert len(commands) == 1
    assert commands[0].intent == "query"

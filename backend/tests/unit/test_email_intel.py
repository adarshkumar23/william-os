"""
WILLIAM OS — Email Intelligence Service Tests
Unit tests for account linking, syncing summaries, and morning briefing assembly.
"""

from __future__ import annotations

import pytest
from app.modules.email_intel.service import EmailIntelService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_connect_account(db_session: AsyncSession, test_user):
    service = EmailIntelService(db_session)

    account = await service.connect_account(
        user_id=test_user.id,
        provider="gmail",
        email_address="alerts@example.com",
        oauth_token="oauth-secret-token",
    )

    assert account.provider == "gmail"
    assert account.email_address == "alerts@example.com"
    assert account.is_active is True


@pytest.mark.asyncio
async def test_sync_and_get_latest_summary(db_session: AsyncSession, test_user, monkeypatch):
    service = EmailIntelService(db_session)

    await service.connect_account(
        user_id=test_user.id,
        provider="gmail",
        email_address="daily@example.com",
        oauth_token="oauth-secret-token",
    )

    async def _fake_fetch(_accounts):
        return ["Urgent bill payment reminder", "Interview schedule confirmation"]

    async def _fake_summarize(subjects):
        return {
            "summary_text": "Two unread emails, one urgent payment and one interview schedule.",
            "priority_emails": [{"subject": subjects[0]}],
            "action_items": ["Pay bill", "Confirm interview slot"],
        }

    monkeypatch.setattr(service, "_fetch_unread_emails", _fake_fetch)
    monkeypatch.setattr(service, "_summarize_unread", _fake_summarize)

    synced = await service.sync_emails(user_id=test_user.id)
    latest = await service.get_latest_summary(user_id=test_user.id)

    assert synced.email_count == 2
    assert latest is not None
    assert latest.summary_text.startswith("Two unread emails")


@pytest.mark.asyncio
async def test_build_morning_briefing(db_session: AsyncSession, test_user, monkeypatch):
    service = EmailIntelService(db_session)

    await service.connect_account(
        user_id=test_user.id,
        provider="gmail",
        email_address="briefing@example.com",
        oauth_token="oauth-secret-token",
    )

    async def _fake_fetch(_accounts):
        return ["Project deadline update", "Family event plan"]

    async def _fake_summarize(_subjects):
        return {
            "summary_text": "You have two unread emails to review this morning.",
            "priority_emails": [{"subject": "Project deadline update"}],
            "action_items": ["Review project deadlines"],
        }

    monkeypatch.setattr(service, "_fetch_unread_emails", _fake_fetch)
    monkeypatch.setattr(service, "_summarize_unread", _fake_summarize)

    await service.sync_emails(user_id=test_user.id)
    briefing = await service.build_morning_briefing(user_id=test_user.id)

    assert briefing.schedule_summary["plan_date"]
    assert briefing.email_summary is not None
    assert "summary_text" in briefing.email_summary
    assert isinstance(briefing.top_priorities, list)

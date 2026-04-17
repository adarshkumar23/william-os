"""
WILLIAM OS — Journal Vault Service Tests
Unit tests for encrypted journal workflows.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.modules.journal.models import JournalMood
from app.modules.journal.schemas import JournalCreate
from app.modules.journal.service import JournalService
from app.shared.types import EncryptionError, NotFoundError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_and_read_roundtrip(db_session: AsyncSession, test_user):
    service = JournalService(db_session)

    created = await service.create_entry(
        user_id=test_user.id,
        data=JournalCreate(
            content="Today I completed all my planned blocks and felt focused.",
            passphrase="journal-pass-123",
            mood=JournalMood.GOOD,
            tags=["focus", "wins"],
        ),
    )

    decrypted = await service.read_entry(
        user_id=test_user.id,
        entry_id=created.id,
        passphrase="journal-pass-123",
    )

    assert decrypted.id == created.id
    assert "felt focused" in decrypted.content
    assert decrypted.summary is None
    assert decrypted.word_count == 10


@pytest.mark.asyncio
async def test_wrong_passphrase_raises_encryption_error(db_session: AsyncSession, test_user):
    service = JournalService(db_session)

    created = await service.create_entry(
        user_id=test_user.id,
        data=JournalCreate(
            content="I had a reflective evening walk.",
            passphrase="correct-pass",
            mood=JournalMood.OKAY,
            tags=["reflection"],
        ),
    )

    with pytest.raises(EncryptionError):
        await service.read_entry(
            user_id=test_user.id,
            entry_id=created.id,
            passphrase="wrong-pass",
        )


@pytest.mark.asyncio
async def test_list_returns_metadata_only_no_content(db_session: AsyncSession, test_user):
    service = JournalService(db_session)

    await service.create_entry(
        user_id=test_user.id,
        data=JournalCreate(
            content="Entry one content",
            passphrase="journal-pass",
            mood=JournalMood.GREAT,
            tags=["personal"],
        ),
    )
    await service.create_entry(
        user_id=test_user.id,
        data=JournalCreate(
            content="Entry two content",
            passphrase="journal-pass",
            mood=JournalMood.LOW,
            tags=["work"],
        ),
    )

    entries = await service.list_entries(
        user_id=test_user.id,
        date_from=date.today(),
        date_to=date.today(),
    )

    assert len(entries) == 2
    dumped = entries[0].model_dump(mode="json")
    assert "content" not in dumped
    assert "summary" not in dumped
    assert "word_count" in dumped


@pytest.mark.asyncio
async def test_delete_entry_hard_delete(db_session: AsyncSession, test_user):
    service = JournalService(db_session)

    created = await service.create_entry(
        user_id=test_user.id,
        data=JournalCreate(
            content="This entry will be deleted.",
            passphrase="journal-pass",
            mood=JournalMood.BAD,
            tags=["cleanup"],
        ),
    )

    await service.delete_entry(entry_id=created.id, user_id=test_user.id)

    with pytest.raises(NotFoundError):
        await service.read_entry(
            user_id=test_user.id,
            entry_id=created.id,
            passphrase="journal-pass",
        )


@pytest.mark.asyncio
async def test_generate_summary_encrypts_and_returns_summary(
    db_session: AsyncSession,
    test_user,
    monkeypatch,
):
    service = JournalService(db_session)

    created = await service.create_entry(
        user_id=test_user.id,
        data=JournalCreate(
            content="I studied economics for two hours and revised modern history notes.",
            passphrase="journal-pass",
            mood=JournalMood.GOOD,
            tags=["study"],
        ),
    )

    async def _fake_summary(_content: str) -> str:
        return "Focused study session with economics and history revision."

    monkeypatch.setattr(service, "_summarize_content", _fake_summary)

    summarized = await service.generate_summary(
        user_id=test_user.id,
        entry_id=created.id,
        passphrase="journal-pass",
    )

    assert summarized.summary is not None
    assert "economics" in summarized.summary.lower()

    reread = await service.read_entry(
        user_id=test_user.id,
        entry_id=created.id,
        passphrase="journal-pass",
    )
    assert reread.summary == summarized.summary

"""
WILLIAM OS — Journal Vault Routes
Encrypted journal create, list, read, delete, and summary generation.
"""

from __future__ import annotations

import uuid
from datetime import date

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.journal.models import JournalMood
from app.modules.journal.schemas import JournalCreate, JournalRead
from app.modules.journal.service import JournalService
from app.shared.types import success
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/journal", tags=["Journal Vault"])


@router.post("", status_code=201)
async def create_entry(
    data: JournalCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = JournalService(db)
    created = await service.create_entry(user_id=user_id, data=data)
    return success(created.model_dump(mode="json"))


@router.get("")
async def list_entries(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    mood: JournalMood | None = Query(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = JournalService(db)
    entries = await service.list_entries(
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        mood_filter=mood,
    )
    return success([entry.model_dump(mode="json") for entry in entries])


@router.post("/{entry_id}/read")
async def read_entry(
    entry_id: uuid.UUID,
    data: JournalRead,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = JournalService(db)
    entry = await service.read_entry(
        user_id=user_id,
        entry_id=entry_id,
        passphrase=data.passphrase,
    )
    return success(entry.model_dump(mode="json"))


@router.delete("/{entry_id}")
async def delete_entry(
    entry_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = JournalService(db)
    await service.delete_entry(entry_id=entry_id, user_id=user_id)
    return success({"deleted": True})


@router.post("/{entry_id}/summary")
async def generate_summary(
    entry_id: uuid.UUID,
    data: JournalRead,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = JournalService(db)
    entry = await service.generate_summary(
        user_id=user_id,
        entry_id=entry_id,
        passphrase=data.passphrase,
    )
    return success(entry.model_dump(mode="json"))

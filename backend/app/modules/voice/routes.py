"""
WILLIAM OS — Voice Routes
Voice command execution endpoints.
"""

from __future__ import annotations

import uuid

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.voice.schemas import VoiceCommandRequest
from app.modules.voice.service import VoiceService
from app.shared.types import success
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/voice", tags=["Voice Interface"])


@router.post("/command")
async def process_text_command(
    data: VoiceCommandRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = VoiceService(db)
    response = await service.process_voice_command(
        user_id=user_id,
        text_or_audio=data.text,
        journal_passphrase=data.journal_passphrase,
    )
    return success(response.model_dump(mode="json"))


@router.post("/transcribe")
async def transcribe_and_execute(
    audio: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    audio_bytes = await audio.read()
    service = VoiceService(db)
    response = await service.process_voice_command(user_id=user_id, text_or_audio=audio_bytes)
    return success(response.model_dump(mode="json"))


@router.get("/history")
async def get_voice_history(
    limit: int = Query(default=50, ge=1, le=200),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = VoiceService(db)
    history = await service.get_history(user_id=user_id, limit=limit)
    return success([item.model_dump(mode="json") for item in history])

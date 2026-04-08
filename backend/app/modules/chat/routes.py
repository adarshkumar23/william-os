"""
WILLIAM OS — Chat Routes
Endpoints for creating chat sessions and sending messages.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.chat.proactive import ProactiveMessageService
from app.modules.chat.schemas import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionListItem,
    ChatSessionResponse,
)
from app.modules.chat.service import ChatService
from app.shared.types import success
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/chat", tags=["Chat"])


class ProactiveTriggerRequest(BaseModel):
    trigger: str = Field(pattern=r"^(morning|afternoon|evening)$")


@router.post("/sessions", status_code=201)
async def create_session(
    data: ChatSessionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ChatService(db)
    session = await service.create_session(
        user_id=user_id,
        agent_name=data.agent_name,
        title=data.title,
    )
    return success(ChatSessionResponse.model_validate(session).model_dump(mode="json", by_alias=True))


@router.get("/sessions")
async def list_sessions(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ChatService(db)
    sessions = await service.get_sessions(user_id)
    
    items = []
    for s in sessions:
        last_msg_text = None
        if s.messages:
            last = s.messages[-1]
            last_msg_text = last.content if getattr(last, "content", None) else "Action taken"
            
        items.append(ChatSessionListItem(
            id=s.id,
            user_id=s.user_id,
            agent_name=s.agent_name,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            last_message_preview=last_msg_text
        ).model_dump(mode="json"))

    return success(items)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ChatService(db)
    deleted = await service.delete_session(session_id, user_id)
    return success({"deleted": deleted})


@router.post("/sessions/{session_id}/messages", status_code=201)
async def send_message(
    session_id: uuid.UUID,
    data: ChatMessageCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ChatService(db)
    user_msg, assistant_msg = await service.send_message(
        session_id=session_id,
        user_id=user_id,
        content=data.content
    )
    return success({
        "user_message": ChatMessageResponse.model_validate(user_msg).model_dump(mode="json", by_alias=True),
        "assistant_message": ChatMessageResponse.model_validate(assistant_msg).model_dump(mode="json", by_alias=True)
    })


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: uuid.UUID,
    limit: int = 50,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ChatService(db)
    messages = await service.get_messages(session_id, user_id, limit=limit)
    items = [ChatMessageResponse.model_validate(m).model_dump(mode="json", by_alias=True) for m in messages]
    return success(items)


@router.post("/proactive/trigger")
async def trigger_proactive_message(
    request: ProactiveTriggerRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = ProactiveMessageService(db)
    if request.trigger == "morning":
        message = await service.generate_morning_message(user_id=user_id)
    elif request.trigger == "afternoon":
        message = await service.generate_afternoon_check(user_id=user_id)
    else:
        message = await service.generate_evening_summary(user_id=user_id)

    await service.send_proactive_message(
        user_id=user_id,
        message=message,
        trigger=request.trigger,
    )
    return success({"message": message, "sent": True})

"""
WILLIAM OS — Study Routes
Study mentor CRUD and analytics endpoints.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.study.schemas import (
    FocusSessionCompleteRequest,
    FocusSessionStartRequest,
    MockTestCreate,
    MockTestUpdate,
    ReviewResult,
    RevisionCardCreate,
    StudyPlanRequest,
    StudySessionCreate,
    StudySessionUpdate,
    SubjectCreate,
    SubjectUpdate,
)
from app.modules.study.service import StudyService
from app.shared.types import success

router = APIRouter(prefix="/study", tags=["IAS Study Mentor"])


@router.post("/subjects", status_code=201)
async def create_subject(
    data: SubjectCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    subject = await service.create_subject(user_id=user_id, data=data)
    return success(subject.model_dump(mode="json"))


@router.get("/subjects")
async def list_subjects(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    subjects = await service.list_subjects(user_id=user_id)
    return success([item.model_dump(mode="json") for item in subjects])


@router.get("/subjects/{subject_id}")
async def get_subject(
    subject_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    subject = await service.get_subject(user_id=user_id, subject_id=subject_id)
    return success(subject.model_dump(mode="json"))


@router.patch("/subjects/{subject_id}")
async def update_subject(
    subject_id: uuid.UUID,
    data: SubjectUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    subject = await service.update_subject(user_id=user_id, subject_id=subject_id, data=data)
    return success(subject.model_dump(mode="json"))


@router.delete("/subjects/{subject_id}")
async def delete_subject(
    subject_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    await service.delete_subject(user_id=user_id, subject_id=subject_id)
    return success({"deleted": True})


@router.post("/sessions", status_code=201)
async def create_session(
    data: StudySessionCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    session = await service.log_session(user_id=user_id, subject_id=data.subject_id, data=data)
    return success(session.model_dump(mode="json"))


@router.get("/sessions")
async def list_sessions(
    subject_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    sessions = await service.list_sessions(
        user_id=user_id,
        subject_id=subject_id,
        limit=limit,
        offset=offset,
    )
    return success([item.model_dump(mode="json") for item in sessions])


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    session = await service.get_session(user_id=user_id, session_id=session_id)
    return success(session.model_dump(mode="json"))


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: uuid.UUID,
    data: StudySessionUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    session = await service.update_session(user_id=user_id, session_id=session_id, data=data)
    return success(session.model_dump(mode="json"))


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    await service.delete_session(user_id=user_id, session_id=session_id)
    return success({"deleted": True})


@router.post("/focus/start", status_code=201)
async def start_focus_session(
    data: FocusSessionStartRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    session = await service.start_focus_session(user_id=user_id, data=data)
    return success(session.model_dump(mode="json"))


@router.get("/focus/active")
async def active_focus_session(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    session = await service.get_active_focus_session(user_id=user_id)
    return success(session.model_dump(mode="json") if session else None)


@router.post("/focus/{session_id}/complete")
async def complete_focus_session(
    session_id: uuid.UUID,
    data: FocusSessionCompleteRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    session = await service.complete_focus_session(
        user_id=user_id,
        session_id=session_id,
        data=data,
    )
    return success(session.model_dump(mode="json"))


@router.post("/focus/{session_id}/cancel")
async def cancel_focus_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    session = await service.cancel_focus_session(user_id=user_id, session_id=session_id)
    return success(session.model_dump(mode="json"))


@router.post("/cards", status_code=201)
async def create_card(
    data: RevisionCardCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    card = await service.create_card(user_id=user_id, data=data)
    return success(card.model_dump(mode="json"))


@router.get("/cards")
async def list_cards(
    subject_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    cards = await service.list_cards(
        user_id=user_id,
        subject_id=subject_id,
        limit=limit,
        offset=offset,
    )
    return success([item.model_dump(mode="json") for item in cards])


@router.get("/cards/due")
async def cards_due(
    for_date: date | None = Query(default=None),
    on_date: date | None = Query(default=None),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    resolved_date = for_date or on_date or date.today()
    cards = await service.get_cards_due(user_id=user_id, on_date=resolved_date)
    return success([item.model_dump(mode="json") for item in cards])


@router.get("/cards/{card_id}")
async def get_card(
    card_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    card = await service.get_card(user_id=user_id, card_id=card_id)
    return success(card.model_dump(mode="json"))


@router.post("/cards/{card_id}/review")
async def review_card(
    card_id: uuid.UUID,
    data: ReviewResult,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    card = await service.review_card(user_id=user_id, card_id=card_id, quality=data.quality)
    return success(card.model_dump(mode="json"))


@router.post("/mocks", status_code=201)
async def create_mock(
    data: MockTestCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    mock = await service.create_mock_test(user_id=user_id, data=data)
    return success(mock.model_dump(mode="json"))


@router.get("/mocks")
async def list_mocks(
    subject_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    mocks = await service.list_mock_tests(
        user_id=user_id,
        subject_id=subject_id,
        limit=limit,
        offset=offset,
    )
    return success([item.model_dump(mode="json") for item in mocks])


@router.get("/mocks/{mock_id}")
async def get_mock(
    mock_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    mock = await service.get_mock_test(user_id=user_id, mock_id=mock_id)
    return success(mock.model_dump(mode="json"))


@router.patch("/mocks/{mock_id}")
async def update_mock(
    mock_id: uuid.UUID,
    data: MockTestUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    mock = await service.update_mock_test(user_id=user_id, mock_id=mock_id, data=data)
    return success(mock.model_dump(mode="json"))


@router.delete("/mocks/{mock_id}")
async def delete_mock(
    mock_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    await service.delete_mock_test(user_id=user_id, mock_id=mock_id)
    return success({"deleted": True})


@router.get("/progress")
async def get_progress(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    progress = await service.get_progress(user_id=user_id)
    return success([item.model_dump(mode="json") for item in progress])


@router.get("/dashboard")
async def get_dashboard(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    dashboard = await service.get_dashboard(user_id=user_id)
    return success(dashboard)


@router.post("/plan")
async def generate_plan(
    data: StudyPlanRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    plan = await service.generate_study_plan(user_id=user_id, request=data)
    return success(plan)


@router.get("/suggest")
async def suggest_next_topic(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = StudyService(db)
    suggestion = await service.suggest_next_topic(user_id=user_id)
    return success(suggestion)

"""
WILLIAM OS — Study Service Tests
Unit tests for SM-2 review updates, due cards query, and progress aggregation.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from app.modules.study.schemas import (
    MockTestCreate,
    RevisionCardCreate,
    StudySessionCreate,
    SubjectCreate,
)
from app.modules.study.service import StudyService
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_sm2_quality_five_increases_interval(db_session: AsyncSession, test_user):
    service = StudyService(db_session)
    subject = await service.create_subject(
        user_id=test_user.id,
        data=SubjectCreate(name="Polity", total_weight=15.0),
    )
    card = await service.create_card(
        user_id=test_user.id,
        data=RevisionCardCreate(
            subject_id=subject.id,
            question="What is DPSP?",
            answer="Directive Principles of State Policy",
            next_review_date=date.today(),
        ),
    )

    card_model = await service._card_for_user(test_user.id, card.id)
    card_model.repetitions = 3
    card_model.interval_days = 4
    card_model.ease_factor = 2.5
    await db_session.flush()

    reviewed = await service.review_card(user_id=test_user.id, card_id=card.id, quality=5)

    assert reviewed.interval_days > 4
    assert reviewed.repetitions == 4


@pytest.mark.asyncio
async def test_sm2_quality_one_resets_card(db_session: AsyncSession, test_user):
    service = StudyService(db_session)
    subject = await service.create_subject(
        user_id=test_user.id,
        data=SubjectCreate(name="Economy", total_weight=20.0),
    )
    card = await service.create_card(
        user_id=test_user.id,
        data=RevisionCardCreate(
            subject_id=subject.id,
            question="Define inflation",
            answer="Sustained increase in price level",
            next_review_date=date.today(),
        ),
    )

    reviewed = await service.review_card(user_id=test_user.id, card_id=card.id, quality=1)

    assert reviewed.repetitions == 0
    assert reviewed.interval_days == 1


@pytest.mark.asyncio
async def test_cards_due_query(db_session: AsyncSession, test_user):
    service = StudyService(db_session)
    subject = await service.create_subject(
        user_id=test_user.id,
        data=SubjectCreate(name="History", total_weight=10.0),
    )

    await service.create_card(
        user_id=test_user.id,
        data=RevisionCardCreate(
            subject_id=subject.id,
            question="Question due",
            answer="Answer",
            next_review_date=date.today(),
        ),
    )
    await service.create_card(
        user_id=test_user.id,
        data=RevisionCardCreate(
            subject_id=subject.id,
            question="Future question",
            answer="Answer",
            next_review_date=date.today() + timedelta(days=5),
        ),
    )

    due_cards = await service.get_cards_due(user_id=test_user.id, on_date=date.today())
    assert len(due_cards) == 1
    assert due_cards[0].question == "Question due"


@pytest.mark.asyncio
async def test_progress_aggregation(db_session: AsyncSession, test_user):
    service = StudyService(db_session)
    subject = await service.create_subject(
        user_id=test_user.id,
        data=SubjectCreate(name="Geography", total_weight=12.0),
    )

    await service.log_session(
        user_id=test_user.id,
        subject_id=subject.id,
        data=StudySessionCreate(
            subject_id=subject.id,
            duration_minutes=120,
            topics_covered=["Climatology"],
            comprehension_score=8.0,
            session_date=date.today(),
        ),
    )

    await service.create_card(
        user_id=test_user.id,
        data=RevisionCardCreate(
            subject_id=subject.id,
            question="What is monsoon?",
            answer="Seasonal wind pattern",
            next_review_date=date.today(),
        ),
    )

    await service.create_mock_test(
        user_id=test_user.id,
        data=MockTestCreate(
            subject_id=subject.id,
            test_name="Geo Mock 1",
            score=80,
            total=100,
            date=date.today(),
        ),
    )

    progress = await service.get_progress(user_id=test_user.id)
    assert len(progress) == 1
    assert progress[0].subject == "Geography"
    assert progress[0].hours_studied == 2.0
    assert progress[0].cards_due == 1
    assert progress[0].mock_avg == 80.0
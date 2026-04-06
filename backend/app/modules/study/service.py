"""
WILLIAM OS — Study Service
Study tracking, spaced repetition, and planning intelligence.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import httpx
import structlog
from app.core.config import get_settings
from app.modules.study.models import MockTest, RevisionCard, StudySession, Subject
from app.modules.study.schemas import (
    MockTestCreate,
    MockTestResponse,
    MockTestUpdate,
    RevisionCardCreate,
    RevisionCardResponse,
    RevisionCardUpdate,
    StudyPlanRequest,
    StudyProgress,
    StudySessionCreate,
    StudySessionResponse,
    StudySessionUpdate,
    SubjectCreate,
    SubjectResponse,
    SubjectUpdate,
)
from app.shared.types import NotFoundError
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class StudyService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def create_subject(self, user_id: uuid.UUID, data: SubjectCreate) -> SubjectResponse:
        subject = Subject(user_id=user_id, **data.model_dump())
        self.db.add(subject)
        await self.db.flush()
        await self.db.refresh(subject)
        return SubjectResponse.model_validate(subject)

    async def list_subjects(self, user_id: uuid.UUID) -> list[SubjectResponse]:
        result = await self.db.execute(
            select(Subject).where(Subject.user_id == user_id).order_by(Subject.name.asc())
        )
        return [SubjectResponse.model_validate(item) for item in result.scalars().all()]

    async def get_subject(self, user_id: uuid.UUID, subject_id: uuid.UUID) -> SubjectResponse:
        subject = await self._subject_for_user(user_id, subject_id)
        return SubjectResponse.model_validate(subject)

    async def update_subject(
        self,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
        data: SubjectUpdate,
    ) -> SubjectResponse:
        subject = await self._subject_for_user(user_id, subject_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(subject, field, value)
        await self.db.flush()
        await self.db.refresh(subject)
        return SubjectResponse.model_validate(subject)

    async def delete_subject(self, user_id: uuid.UUID, subject_id: uuid.UUID) -> None:
        subject = await self._subject_for_user(user_id, subject_id)
        await self.db.delete(subject)
        await self.db.flush()

    async def log_session(
        self,
        user_id: uuid.UUID,
        subject_id: uuid.UUID,
        data: StudySessionCreate,
    ) -> StudySessionResponse:
        await self._subject_for_user(user_id, subject_id)
        session = StudySession(
            user_id=user_id,
            subject_id=subject_id,
            duration_minutes=data.duration_minutes,
            topics_covered=data.topics_covered,
            comprehension_score=data.comprehension_score,
            notes=data.notes,
            session_date=data.session_date,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return StudySessionResponse.model_validate(session)

    async def list_sessions(
        self,
        user_id: uuid.UUID,
        subject_id: uuid.UUID | None = None,
    ) -> list[StudySessionResponse]:
        query = select(StudySession).where(StudySession.user_id == user_id)
        if subject_id:
            query = query.where(StudySession.subject_id == subject_id)
        query = query.order_by(desc(StudySession.session_date), desc(StudySession.created_at))
        result = await self.db.execute(query)
        return [StudySessionResponse.model_validate(item) for item in result.scalars().all()]

    async def get_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> StudySessionResponse:
        session = await self._session_for_user(user_id, session_id)
        return StudySessionResponse.model_validate(session)

    async def update_session(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        data: StudySessionUpdate,
    ) -> StudySessionResponse:
        session = await self._session_for_user(user_id, session_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(session, field, value)
        await self.db.flush()
        await self.db.refresh(session)
        return StudySessionResponse.model_validate(session)

    async def delete_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        session = await self._session_for_user(user_id, session_id)
        await self.db.delete(session)
        await self.db.flush()

    async def create_card(
        self,
        user_id: uuid.UUID,
        data: RevisionCardCreate,
    ) -> RevisionCardResponse:
        await self._subject_for_user(user_id, data.subject_id)
        card = RevisionCard(user_id=user_id, **data.model_dump())
        self.db.add(card)
        await self.db.flush()
        await self.db.refresh(card)
        return RevisionCardResponse.model_validate(card)

    async def list_cards(
        self,
        user_id: uuid.UUID,
        subject_id: uuid.UUID | None = None,
    ) -> list[RevisionCardResponse]:
        query = select(RevisionCard).where(RevisionCard.user_id == user_id)
        if subject_id:
            query = query.where(RevisionCard.subject_id == subject_id)
        query = query.order_by(RevisionCard.next_review_date.asc(), RevisionCard.created_at.asc())
        result = await self.db.execute(query)
        return [RevisionCardResponse.model_validate(item) for item in result.scalars().all()]

    async def get_card(self, user_id: uuid.UUID, card_id: uuid.UUID) -> RevisionCardResponse:
        card = await self._card_for_user(user_id, card_id)
        return RevisionCardResponse.model_validate(card)

    async def update_card(
        self,
        user_id: uuid.UUID,
        card_id: uuid.UUID,
        data: RevisionCardUpdate,
    ) -> RevisionCardResponse:
        card = await self._card_for_user(user_id, card_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(card, field, value)
        await self.db.flush()
        await self.db.refresh(card)
        return RevisionCardResponse.model_validate(card)

    async def delete_card(self, user_id: uuid.UUID, card_id: uuid.UUID) -> None:
        card = await self._card_for_user(user_id, card_id)
        await self.db.delete(card)
        await self.db.flush()

    async def get_cards_due(
        self,
        user_id: uuid.UUID,
        on_date: date,
    ) -> list[RevisionCardResponse]:
        result = await self.db.execute(
            select(RevisionCard)
            .where(RevisionCard.user_id == user_id)
            .where(RevisionCard.next_review_date <= on_date)
            .order_by(RevisionCard.next_review_date.asc())
        )
        return [RevisionCardResponse.model_validate(item) for item in result.scalars().all()]

    async def review_card(
        self,
        user_id: uuid.UUID,
        card_id: uuid.UUID,
        quality: int,
    ) -> RevisionCardResponse:
        card = await self._card_for_user(user_id, card_id)

        old_interval = max(1, card.interval_days)
        old_repetitions = max(0, card.repetitions)
        old_ease = max(1.3, card.ease_factor)

        ease_delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        new_ease = max(1.3, old_ease + ease_delta)

        if quality < 3:
            new_repetitions = 0
            new_interval = 1
        else:
            new_repetitions = old_repetitions + 1
            if old_repetitions == 0:
                new_interval = 1
            elif old_repetitions == 1:
                new_interval = 6
            else:
                new_interval = max(1, int(round(old_interval * old_ease)))

        today = date.today()
        card.repetitions = new_repetitions
        card.interval_days = new_interval
        card.ease_factor = round(new_ease, 4)
        card.last_reviewed = today
        card.next_review_date = today + timedelta(days=new_interval)

        await self.db.flush()
        await self.db.refresh(card)

        return RevisionCardResponse.model_validate(card)

    async def create_mock_test(self, user_id: uuid.UUID, data: MockTestCreate) -> MockTestResponse:
        if data.subject_id:
            await self._subject_for_user(user_id, data.subject_id)

        percentage = self._calc_percentage(data.score, data.total)
        mock = MockTest(
            user_id=user_id,
            subject_id=data.subject_id,
            test_name=data.test_name,
            score=data.score,
            total=data.total,
            percentage=percentage,
            date=data.date,
            analysis=data.analysis,
        )
        self.db.add(mock)
        await self.db.flush()
        await self.db.refresh(mock)
        return MockTestResponse.model_validate(mock)

    async def list_mock_tests(
        self,
        user_id: uuid.UUID,
        subject_id: uuid.UUID | None = None,
    ) -> list[MockTestResponse]:
        query = select(MockTest).where(MockTest.user_id == user_id)
        if subject_id:
            query = query.where(MockTest.subject_id == subject_id)
        query = query.order_by(MockTest.date.desc(), MockTest.created_at.desc())
        result = await self.db.execute(query)
        return [MockTestResponse.model_validate(item) for item in result.scalars().all()]

    async def get_mock_test(self, user_id: uuid.UUID, mock_id: uuid.UUID) -> MockTestResponse:
        mock = await self._mock_for_user(user_id, mock_id)
        return MockTestResponse.model_validate(mock)

    async def update_mock_test(
        self,
        user_id: uuid.UUID,
        mock_id: uuid.UUID,
        data: MockTestUpdate,
    ) -> MockTestResponse:
        mock = await self._mock_for_user(user_id, mock_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(mock, field, value)

        if "score" in update_data or "total" in update_data:
            mock.percentage = self._calc_percentage(mock.score, mock.total)

        await self.db.flush()
        await self.db.refresh(mock)
        return MockTestResponse.model_validate(mock)

    async def delete_mock_test(self, user_id: uuid.UUID, mock_id: uuid.UUID) -> None:
        mock = await self._mock_for_user(user_id, mock_id)
        await self.db.delete(mock)
        await self.db.flush()

    async def get_progress(self, user_id: uuid.UUID) -> list[StudyProgress]:
        subjects = await self.list_subjects(user_id)
        if not subjects:
            return []

        progress: list[StudyProgress] = []
        today = date.today()

        for subject in subjects:
            session_agg = await self.db.execute(
                select(
                    func.coalesce(func.sum(StudySession.duration_minutes), 0),
                    func.coalesce(func.avg(StudySession.comprehension_score), 0.0),
                )
                .where(StudySession.user_id == user_id)
                .where(StudySession.subject_id == subject.id)
            )
            total_minutes, avg_comprehension = session_agg.one()

            due_cards_query = await self.db.execute(
                select(func.count(RevisionCard.id))
                .where(RevisionCard.user_id == user_id)
                .where(RevisionCard.subject_id == subject.id)
                .where(RevisionCard.next_review_date <= today)
            )
            cards_due = int(due_cards_query.scalar() or 0)

            mock_avg_query = await self.db.execute(
                select(func.coalesce(func.avg(MockTest.percentage), 0.0))
                .where(MockTest.user_id == user_id)
                .where(MockTest.subject_id == subject.id)
            )
            mock_avg = float(mock_avg_query.scalar() or 0.0)

            progress.append(
                StudyProgress(
                    subject=subject.name,
                    hours_studied=round(float(total_minutes or 0) / 60.0, 2),
                    avg_comprehension=round(float(avg_comprehension or 0.0), 2),
                    cards_due=cards_due,
                    mock_avg=round(mock_avg, 2),
                )
            )

        return progress

    async def generate_study_plan(
        self,
        user_id: uuid.UUID,
        request: StudyPlanRequest,
    ) -> list[dict]:
        progress = await self.get_progress(user_id)
        weakest = sorted(progress, key=lambda item: (item.avg_comprehension, item.mock_avg))
        weak_subjects = [item.subject for item in weakest[:3]]

        plan = await self._generate_ai_plan(
            target_date=request.target_date,
            daily_hours=request.daily_hours,
            weak_subjects=weak_subjects,
            progress=progress,
        )
        if plan:
            return plan

        return self._fallback_study_plan(
            target_date=request.target_date,
            daily_hours=request.daily_hours,
            weak_subjects=weak_subjects,
        )

    async def suggest_next_topic(self, user_id: uuid.UUID) -> dict:
        progress = await self.get_progress(user_id)
        if not progress:
            return {"subject": None, "recommendation": "Create a subject and log sessions first."}

        ranked = sorted(progress, key=lambda item: (item.avg_comprehension, -item.cards_due))
        candidate = ranked[0]
        return {
            "subject": candidate.subject,
            "recommendation": (
                f"Focus next on {candidate.subject}: low comprehension and/or pending revisions."
            ),
            "cards_due": candidate.cards_due,
            "avg_comprehension": candidate.avg_comprehension,
        }

    async def _generate_ai_plan(
        self,
        target_date: date,
        daily_hours: int,
        weak_subjects: list[str],
        progress: list[StudyProgress],
    ) -> list[dict] | None:
        api_key = self.settings.gemini_api_key.get_secret_value()
        if not api_key:
            return None

        prompt = (
            "Generate prioritized study schedule blocks as JSON array. "
            "Each item must include title, category, start_time, end_time, priority, tags. "
            f"Target date: {target_date}. Daily hours: {daily_hours}. "
            f"Weak subjects: {weak_subjects}. Progress: {[item.model_dump() for item in progress]}"
        )
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()

            raw = response.json()
            candidates = raw.get("candidates") or []
            if not candidates:
                return None

            parts = (candidates[0].get("content") or {}).get("parts") or []
            text = str(parts[0].get("text") if parts else "")
            parsed = self._extract_json_list(text)
            if parsed:
                return parsed
        except Exception as exc:
            logger.warning("study_plan_generation_failed", error=str(exc))

        return None

    @staticmethod
    def _fallback_study_plan(
        target_date: date,
        daily_hours: int,
        weak_subjects: list[str],
    ) -> list[dict]:
        primary = weak_subjects[0] if weak_subjects else "General Studies"
        secondary = weak_subjects[1] if len(weak_subjects) > 1 else "Current Affairs"
        hours = max(1, daily_hours)

        return [
            {
                "title": f"Deep Study — {primary}",
                "category": "study",
                "start_time": "06:00",
                "end_time": f"{6 + min(3, hours):02d}:00",
                "priority": 1,
                "tags": ["study", "priority"],
                "target_date": str(target_date),
            },
            {
                "title": f"Revision Practice — {secondary}",
                "category": "study",
                "start_time": "18:00",
                "end_time": "20:00",
                "priority": 2,
                "tags": ["revision", "sm2"],
                "target_date": str(target_date),
            },
        ]

    @staticmethod
    def _extract_json_list(text: str) -> list[dict] | None:
        cleaned = text.strip().replace("```json", "").replace("```", "").strip()
        try:
            loaded = json.loads(cleaned)
        except Exception:
            return None
        if isinstance(loaded, list) and all(isinstance(item, dict) for item in loaded):
            return loaded
        return None

    @staticmethod
    def _calc_percentage(score: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return round((score / total) * 100, 2)

    async def _subject_for_user(self, user_id: uuid.UUID, subject_id: uuid.UUID) -> Subject:
        result = await self.db.execute(
            select(Subject).where(and_(Subject.id == subject_id, Subject.user_id == user_id))
        )
        subject = result.scalar_one_or_none()
        if not subject:
            raise NotFoundError("Subject", str(subject_id))
        return subject

    async def _session_for_user(self, user_id: uuid.UUID, session_id: uuid.UUID) -> StudySession:
        result = await self.db.execute(
            select(StudySession).where(
                and_(StudySession.id == session_id, StudySession.user_id == user_id)
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundError("StudySession", str(session_id))
        return session

    async def _card_for_user(self, user_id: uuid.UUID, card_id: uuid.UUID) -> RevisionCard:
        result = await self.db.execute(
            select(RevisionCard).where(
                and_(RevisionCard.id == card_id, RevisionCard.user_id == user_id)
            )
        )
        card = result.scalar_one_or_none()
        if not card:
            raise NotFoundError("RevisionCard", str(card_id))
        return card

    async def _mock_for_user(self, user_id: uuid.UUID, mock_id: uuid.UUID) -> MockTest:
        result = await self.db.execute(
            select(MockTest).where(and_(MockTest.id == mock_id, MockTest.user_id == user_id))
        )
        mock = result.scalar_one_or_none()
        if not mock:
            raise NotFoundError("MockTest", str(mock_id))
        return mock
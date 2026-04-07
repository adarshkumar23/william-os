"""
WILLIAM OS — Decisions Service
Decision lifecycle management and AI-assisted analysis.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from time import perf_counter

import httpx
import structlog
from app.core.config import get_settings
from app.core.events import Event, EventType, event_bus
from app.core.metrics import observe_ai_call
from app.modules.memory.service import MemoryService
from app.modules.decisions.models import Decision, DecisionTemplate
from app.modules.decisions.schemas import (
    DecisionAnalysis,
    DecisionChoose,
    DecisionCreate,
    DecisionOutcome,
    DecisionResponse,
    DecisionStats,
)
from app.shared.types import NotFoundError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class DecisionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def create_decision(self, user_id: uuid.UUID, data: DecisionCreate) -> DecisionResponse:
        decision = Decision(user_id=user_id, **data.model_dump())
        self.db.add(decision)
        await self.db.flush()
        await self.db.refresh(decision)
        return DecisionResponse.model_validate(decision)

    async def list_decisions(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DecisionResponse]:
        result = await self.db.execute(
            select(Decision)
            .where(Decision.user_id == user_id)
            .order_by(Decision.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [DecisionResponse.model_validate(row) for row in result.scalars().all()]

    async def update_decision(
        self,
        user_id: uuid.UUID,
        decision_id: uuid.UUID,
        data: DecisionCreate,
    ) -> DecisionResponse:
        decision = await self._get_user_decision(user_id=user_id, decision_id=decision_id)
        update_data = data.model_dump()
        for field, value in update_data.items():
            setattr(decision, field, value)
        await self.db.flush()
        await self.db.refresh(decision)
        return DecisionResponse.model_validate(decision)

    async def delete_decision(self, user_id: uuid.UUID, decision_id: uuid.UUID) -> None:
        decision = await self._get_user_decision(user_id=user_id, decision_id=decision_id)
        await self.db.delete(decision)
        await self.db.flush()

    async def analyze_decision(
        self,
        user_id: uuid.UUID,
        decision_id: uuid.UUID,
    ) -> DecisionAnalysis:
        decision = await self._get_user_decision(user_id=user_id, decision_id=decision_id)
        decision.status = "analyzing"

        analysis = await self._call_ai_analysis(
            user_id=user_id,
            payload={
                "title": decision.title,
                "description": decision.description,
                "type": decision.decision_type,
                "options": decision.options,
                "criteria": decision.criteria,
                "deadline": str(decision.deadline) if decision.deadline else None,
            },
        )
        if analysis is None:
            analysis = self._fallback_analysis(decision.options, decision.criteria)

        decision.ai_analysis = analysis.reasoning
        decision.ai_scores = analysis.scores
        await self.db.flush()

        return analysis

    async def choose_option(
        self,
        user_id: uuid.UUID,
        decision_id: uuid.UUID,
        payload: DecisionChoose,
    ) -> DecisionResponse:
        decision = await self._get_user_decision(user_id=user_id, decision_id=decision_id)
        decision.chosen_option = payload.chosen_option
        decision.chosen_at = datetime.now(UTC).replace(tzinfo=None)
        decision.status = "decided"
        if payload.reasoning:
            decision.ai_analysis = (
                decision.ai_analysis or ""
            ) + f"\nUser note: {payload.reasoning}"
        await self.db.flush()
        await self.db.refresh(decision)
        return DecisionResponse.model_validate(decision)

    async def log_outcome(
        self,
        user_id: uuid.UUID,
        decision_id: uuid.UUID,
        payload: DecisionOutcome,
    ) -> DecisionResponse:
        decision = await self._get_user_decision(user_id=user_id, decision_id=decision_id)
        decision.outcome = payload.outcome
        decision.outcome_rating = payload.outcome_rating
        decision.reviewed_at = datetime.now(UTC).replace(tzinfo=None)
        decision.status = "reviewed"
        await self.db.flush()
        await self.db.refresh(decision)

        await event_bus.publish(
            Event(
                type=EventType.DECISION_COMPLETED_WITH_OUTCOME,
                data={
                    "decision_id": str(decision.id),
                    "decision_type": decision.decision_type,
                    "outcome_rating": decision.outcome_rating,
                },
                user_id=user_id,
            )
        )

        return DecisionResponse.model_validate(decision)

    async def get_decision_quality(self, user_id: uuid.UUID) -> DecisionStats:
        result = await self.db.execute(select(Decision).where(Decision.user_id == user_id))
        decisions = result.scalars().all()
        total = len(decisions)
        if total == 0:
            return DecisionStats(
                total=0,
                avg_time_to_decide=0.0,
                ai_agreement_rate=0.0,
                avg_outcome_rating=0.0,
                by_type={},
            )

        decided_deltas = []
        agreement_checks = []
        ratings = []
        by_type = defaultdict(int)

        for item in decisions:
            by_type[item.decision_type] += 1
            if item.chosen_at:
                decided_deltas.append((item.chosen_at - item.created_at).total_seconds() / 3600.0)
            if item.outcome_rating is not None:
                ratings.append(float(item.outcome_rating))
            if item.ai_scores and item.chosen_option:
                top = self._top_scored_option(item.ai_scores)
                if top:
                    agreement_checks.append(1.0 if top == item.chosen_option else 0.0)

        avg_time = round(sum(decided_deltas) / len(decided_deltas), 2) if decided_deltas else 0.0
        ai_agreement = (
            round((sum(agreement_checks) / len(agreement_checks)) * 100, 2)
            if agreement_checks
            else 0.0
        )
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

        return DecisionStats(
            total=total,
            avg_time_to_decide=avg_time,
            ai_agreement_rate=ai_agreement,
            avg_outcome_rating=avg_rating,
            by_type=dict(by_type),
        )

    async def list_templates(self) -> list[dict]:
        result = await self.db.execute(
            select(DecisionTemplate)
            .where(DecisionTemplate.is_public.is_(True))
            .order_by(DecisionTemplate.name.asc())
        )
        rows = result.scalars().all()
        return [
            {
                "id": str(item.id),
                "name": item.name,
                "description": item.description,
                "decision_type": item.decision_type,
                "default_criteria": item.default_criteria,
            }
            for item in rows
        ]

    async def create_from_template(
        self,
        user_id: uuid.UUID,
        template_id: uuid.UUID,
        title: str,
        description: str,
        options: list[dict],
        deadline,
    ) -> DecisionResponse:
        template = await self.db.get(DecisionTemplate, template_id)
        if template is None:
            raise NotFoundError("DecisionTemplate", str(template_id))

        return await self.create_decision(
            user_id=user_id,
            data=DecisionCreate(
                title=title,
                description=description,
                decision_type=template.decision_type,
                deadline=deadline,
                options=options,
                criteria=template.default_criteria,
            ),
        )

    async def _get_user_decision(self, user_id: uuid.UUID, decision_id: uuid.UUID) -> Decision:
        result = await self.db.execute(
            select(Decision).where(and_(Decision.id == decision_id, Decision.user_id == user_id))
        )
        decision = result.scalar_one_or_none()
        if decision is None:
            raise NotFoundError("Decision", str(decision_id))
        return decision

    async def _call_ai_analysis(self, user_id: uuid.UUID, payload: dict) -> DecisionAnalysis | None:
        api_key = self.settings.openrouter_api_key.get_secret_value()
        if not api_key:
            return None

        memory_context = await MemoryService(self.db).get_relevant_memory_context(
            user_id=user_id,
            modules=["decisions", "sleep", "journal", "trading"],
            limit=6,
        )

        prompt = (
            "Analyze this decision payload and return JSON with keys: "
            "scores (object of option->score), "
            "recommendation, reasoning, confidence, risk_factors (array). Payload: "
            f"{json.dumps(payload)}. Memory context: {memory_context}"
        )
        body = {
            "model": self.settings.openrouter_model,
            "messages": [
                {"role": "system", "content": "You are a multi-criteria decision analyst."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 500,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.base_url,
            "X-Title": self.settings.app_name,
        }

        started = perf_counter()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=body,
                    headers=headers,
                )
                response.raise_for_status()
            observe_ai_call(provider="openrouter", duration_seconds=perf_counter() - started)
            content = response.json()["choices"][0]["message"]["content"].strip()
            cleaned = content.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                return None
            return DecisionAnalysis(
                scores=parsed.get("scores") or {},
                recommendation=str(parsed.get("recommendation") or ""),
                reasoning=str(parsed.get("reasoning") or ""),
                confidence=float(parsed.get("confidence") or 0.0),
                risk_factors=parsed.get("risk_factors") or [],
            )
        except Exception as exc:
            observe_ai_call(provider="openrouter", duration_seconds=perf_counter() - started)
            logger.warning("decision_analysis_ai_failed", error=str(exc))
            return None

    @staticmethod
    def _fallback_analysis(options: list[dict], criteria: list[dict]) -> DecisionAnalysis:
        if not options:
            return DecisionAnalysis(
                scores={},
                recommendation="",
                reasoning="No options provided.",
                confidence=0.0,
                risk_factors=["No options supplied"],
            )

        option_names = [
            str(item.get("name") or f"option_{idx + 1}") for idx, item in enumerate(options)
        ]
        criteria_weights = sum(float(item.get("weight", 0.0)) for item in criteria) or 1.0

        scores = {
            name: round(
                0.5
                + (idx / max(1, len(option_names) - 1))
                * (criteria_weights / max(1.0, len(criteria))),
                3,
            )
            for idx, name in enumerate(option_names)
        }
        recommendation = max(scores.items(), key=lambda x: x[1])[0]
        return DecisionAnalysis(
            scores=scores,
            recommendation=recommendation,
            reasoning="Fallback weighted heuristic based on provided criteria.",
            confidence=0.62,
            risk_factors=["Heuristic mode", "Limited signal from historical outcomes"],
        )

    @staticmethod
    def _top_scored_option(ai_scores: dict) -> str | None:
        if not ai_scores:
            return None
        try:
            return max(ai_scores.items(), key=lambda x: float(x[1]))[0]
        except Exception:
            return None

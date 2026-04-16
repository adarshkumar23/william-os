"""WILLIAM OS - Agent orchestration service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from app.modules.agents.base import AgentContext, BaseAgent
from app.modules.agents.models import AgentActionLog, AgentRecommendationLog, AgentStatus
from app.modules.agents.schemas import AgentAction, AgentRecommendation
from app.modules.audit.models import AuditAction, AuditLog
from app.modules.decisions.models import Decision
from app.modules.fitness.models import WorkoutLog
from app.modules.habits.models import ProcrastinationSignal
from app.modules.memory.service import MemoryService
from app.modules.medicine.models import Medicine, MedicineLog
from app.modules.messaging.schemas import NotificationPayload
from app.modules.messaging.service import MessagingService
from app.modules.scheduler.models import DailyPlan, ScheduleBlock
from app.modules.scheduler.models import BlockCategory
from app.modules.scheduler.schemas import RescheduleRequest
from app.modules.scheduler.service import SchedulerService
from app.modules.sleep.models import SleepDebt, SleepRecord
from app.modules.study.models import RevisionCard, StudySession
from app.modules.trading.models import PortfolioSnapshot, TradeLog
from sqlalchemy import desc, func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class _RecommendationBundle:
    recommendation: AgentRecommendation
    action: AgentAction | None = None


class _HeuristicAgent(BaseAgent):
    def __init__(self, db: AsyncSession):
        self.db = db
        self.messaging = MessagingService(db)
        self._user_id: uuid.UUID | None = None

    async def act(self, recommendation: AgentRecommendation) -> AgentAction:
        if self._user_id is None:
            raise RuntimeError("agent user context is not set")

        payload = NotificationPayload(
            title=f"{recommendation.agent_name} alert",
            body=recommendation.summary,
            notification_type="agent_recommendation",
            data={
                "agent": recommendation.agent_name,
                "severity": recommendation.severity,
                "urgency": recommendation.urgency,
                "recommended_action": recommendation.recommended_action,
                "context": recommendation.context,
            },
        )
        in_app = await self.messaging.send_in_app_notification(
            user_id=self._user_id,
            payload=payload,
        )
        await self.messaging.send_notification(user_id=self._user_id, payload=payload)
        return AgentAction(
            agent_name=recommendation.agent_name,
            action_type="notify",
            details={"notification_id": str(in_app.id), "recommended_action": recommendation.recommended_action},
            success=True,
        )


class HealthAgent(_HeuristicAgent):
    name = "health"
    description = "Monitors sleep, medicine, and fitness collapse risk."
    memory = "health"
    goals = ["avoid sleep collapse", "prevent missed medication streak", "avoid overtraining"]
    permissions = ["notify", "recommend", "reschedule"]
    action_scope = "health"
    notification_style = "direct"

    async def analyze(self, context: AgentContext) -> AgentRecommendation | None:
        self._user_id = context.user_id
        seven_days = date.today() - timedelta(days=7)

        missed_result = await self.db.execute(
            select(func.count(MedicineLog.id))
            .join(Medicine, Medicine.id == MedicineLog.medicine_id)
            .where(Medicine.user_id == context.user_id)
            .where(MedicineLog.log_date >= seven_days)
            .where(MedicineLog.skipped.is_(True))
        )
        missed = int(missed_result.scalar() or 0)

        sleep_result = await self.db.execute(
            select(func.avg(SleepRecord.sleep_quality), func.avg(SleepRecord.sleep_duration_minutes))
            .where(SleepRecord.user_id == context.user_id)
            .where(SleepRecord.sleep_date >= seven_days)
        )
        avg_quality, avg_duration = sleep_result.one()
        quality = float(avg_quality or 0.0)
        duration = float(avg_duration or 0.0)

        workout_result = await self.db.execute(
            select(func.count(WorkoutLog.id))
            .where(WorkoutLog.user_id == context.user_id)
            .where(WorkoutLog.workout_date >= date.today() - timedelta(days=3))
        )
        workout_3d = int(workout_result.scalar() or 0)

        urgency = 0
        if quality < 5.5 or duration < 360:
            urgency += 35
        if missed >= 3:
            urgency += 40
        if workout_3d >= 6:
            urgency += 25
        if urgency < 35:
            return None

        severity = "critical" if urgency >= 80 else "high" if urgency >= 60 else "medium"
        summary = "Health risk pattern detected: "
        if missed >= 3:
            summary += f"{missed} missed doses in last 7 days. "
        if quality < 5.5 or duration < 360:
            summary += "Sleep quality/duration is deteriorating. "
        if workout_3d >= 6:
            summary += "Training load in the last 3 days may be too high."

        return AgentRecommendation(
            agent_name=self.name,
            summary=summary.strip(),
            severity=severity,
            urgency=min(100, urgency),
            recommended_action="reduce intensity and restore sleep/medication consistency",
            context={"missed_medication_7d": missed, "sleep_quality_7d": round(quality, 2), "sleep_minutes_7d": round(duration, 2), "workouts_3d": workout_3d},
        )


class StudyAgent(_HeuristicAgent):
    name = "study"
    description = "Monitors consistency, cramming risk, and burnout for study." 
    memory = "study"
    goals = ["maintain consistency", "avoid cramming", "prevent burnout"]
    permissions = ["notify", "recommend"]
    action_scope = "study"
    notification_style = "coach"

    async def analyze(self, context: AgentContext) -> AgentRecommendation | None:
        self._user_id = context.user_id
        five_days = date.today() - timedelta(days=5)
        sessions_result = await self.db.execute(
            select(func.count(StudySession.id))
            .where(StudySession.user_id == context.user_id)
            .where(StudySession.session_date >= five_days)
        )
        sessions_5d = int(sessions_result.scalar() or 0)

        due_cards_result = await self.db.execute(
            select(func.count(RevisionCard.id))
            .where(RevisionCard.user_id == context.user_id)
            .where(RevisionCard.next_review_date <= date.today())
        )
        due_cards = int(due_cards_result.scalar() or 0)

        urgency = 0
        if sessions_5d == 0:
            urgency += 55
        elif sessions_5d <= 2:
            urgency += 25
        if due_cards >= 20:
            urgency += 35
        elif due_cards >= 10:
            urgency += 20

        if urgency < 30:
            return None

        severity = "high" if urgency >= 60 else "medium"
        return AgentRecommendation(
            agent_name=self.name,
            summary=(
                f"Study consistency is slipping ({sessions_5d} sessions in 5 days) "
                f"with {due_cards} revision cards due."
            ),
            severity=severity,
            urgency=min(100, urgency),
            recommended_action="schedule focused catch-up blocks and clear due revision cards",
            context={"sessions_last_5_days": sessions_5d, "due_revision_cards": due_cards},
        )


class TradingAgent(_HeuristicAgent):
    name = "trading"
    description = "Monitors overtrading and stress-driven trading behaviors."
    memory = "trading"
    goals = ["avoid overtrading", "reduce stress-driven entries"]
    permissions = ["notify", "recommend"]
    action_scope = "trading"
    notification_style = "risk"

    async def analyze(self, context: AgentContext) -> AgentRecommendation | None:
        self._user_id = context.user_id
        yesterday = date.today() - timedelta(days=1)

        trades_24h_result = await self.db.execute(
            select(func.count(TradeLog.id))
            .where(TradeLog.user_id == context.user_id)
            .where(TradeLog.trade_date >= yesterday)
        )
        trades_24h = int(trades_24h_result.scalar() or 0)

        snapshot_result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == context.user_id)
            .order_by(desc(PortfolioSnapshot.snapshot_date))
            .limit(1)
        )
        latest = snapshot_result.scalar_one_or_none()
        pnl_down = bool(latest and (latest.daily_pnl < 0 or latest.total_pnl < 0))

        urgency = 0
        if trades_24h > 5:
            urgency += 45
        if pnl_down:
            urgency += 25

        if urgency < 40:
            return None

        return AgentRecommendation(
            agent_name=self.name,
            summary=(
                f"Potential overtrading behavior detected: {trades_24h} trades in last 24h "
                f"with {'negative' if pnl_down else 'mixed'} portfolio momentum."
            ),
            severity="high" if urgency >= 65 else "medium",
            urgency=min(100, urgency),
            recommended_action="reduce position frequency and enforce cooldown between trades",
            context={"trades_last_24h": trades_24h, "portfolio_down": pnl_down},
        )


class ExecutiveAgent(_HeuristicAgent):
    name = "executive"
    description = "Monitors schedule pressure, deadline collisions, and buffer erosion."
    memory = "executive"
    goals = ["prevent overcommitment", "protect buffers", "resolve collisions"]
    permissions = ["notify", "recommend", "reschedule"]
    action_scope = "schedule"
    notification_style = "prioritized"

    async def analyze(self, context: AgentContext) -> AgentRecommendation | None:
        self._user_id = context.user_id
        today = date.today()
        tomorrow = today + timedelta(days=2)

        plans_result = await self.db.execute(
            select(DailyPlan.id)
            .where(DailyPlan.user_id == context.user_id)
            .where(DailyPlan.plan_date == today)
        )
        plan_ids = [item for item in plans_result.scalars().all()]

        block_count = 0
        buffer_count = 0
        if plan_ids:
            block_result = await self.db.execute(
                select(ScheduleBlock.category)
                .where(ScheduleBlock.plan_id.in_(plan_ids))
            )
            categories = [item for item in block_result.scalars().all()]
            block_count = len(categories)
            buffer_count = sum(1 for category in categories if category == BlockCategory.BUFFER)

        deadlines_result = await self.db.execute(
            select(func.count(Decision.id))
            .where(Decision.user_id == context.user_id)
            .where(Decision.deadline.is_not(None))
            .where(Decision.deadline <= tomorrow)
            .where(Decision.status != "reviewed")
        )
        deadlines_48h = int(deadlines_result.scalar() or 0)

        urgency = 0
        if block_count >= 12:
            urgency += 30
        if buffer_count <= 1 and block_count > 0:
            urgency += 25
        if deadlines_48h >= 2:
            urgency += 35

        if urgency < 35:
            return None

        return AgentRecommendation(
            agent_name=self.name,
            summary=(
                f"Executive risk: {block_count} blocks today, {buffer_count} buffer blocks, "
                f"{deadlines_48h} deadlines within 48h."
            ),
            severity="high" if urgency >= 65 else "medium",
            urgency=min(100, urgency),
            recommended_action="rebalance schedule and protect buffer windows",
            context={"today_block_count": block_count, "buffer_blocks": buffer_count, "deadlines_48h": deadlines_48h},
        )


class RecoveryAgent(_HeuristicAgent):
    name = "recovery"
    description = "Monitors burnout, procrastination spirals, and mood decline." 
    memory = "recovery"
    goals = ["interrupt spirals", "protect recovery windows"]
    permissions = ["notify", "recommend", "reschedule"]
    action_scope = "recovery"
    notification_style = "supportive"

    async def analyze(self, context: AgentContext) -> AgentRecommendation | None:
        self._user_id = context.user_id
        cutoff = date.today() - timedelta(days=7)

        procrastination_result = await self.db.execute(
            select(func.count(ProcrastinationSignal.id))
            .where(ProcrastinationSignal.user_id == context.user_id)
            .where(ProcrastinationSignal.signal_date >= cutoff)
        )
        procrastination_hits = int(procrastination_result.scalar() or 0)

        debt_result = await self.db.execute(
            select(SleepDebt)
            .where(SleepDebt.user_id == context.user_id)
            .order_by(desc(SleepDebt.calculated_date))
            .limit(1)
        )
        debt_row = debt_result.scalar_one_or_none()
        debt_hours = float(debt_row.debt_hours) if debt_row else 0.0

        urgency = 0
        if procrastination_hits >= 3:
            urgency += 35
        if debt_hours >= 3.0:
            urgency += 35

        if urgency < 35:
            return None

        return AgentRecommendation(
            agent_name=self.name,
            summary=(
                f"Recovery warning: {procrastination_hits} procrastination signals in 7d "
                f"and sleep debt {debt_hours:.1f}h."
            ),
            severity="high" if urgency >= 60 else "medium",
            urgency=min(100, urgency),
            recommended_action="activate a light recovery routine and trim workload today",
            context={"procrastination_signals_7d": procrastination_hits, "sleep_debt_hours": debt_hours},
        )


class OrchestratorAgentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.memory_service = MemoryService(db)
        self.messaging = MessagingService(db)
        self.scheduler = SchedulerService(db)

    def _agent_instances(self) -> list[BaseAgent]:
        return [
            HealthAgent(self.db),
            StudyAgent(self.db),
            TradingAgent(self.db),
            ExecutiveAgent(self.db),
            RecoveryAgent(self.db),
        ]

    async def run_for_user(self, user_id: uuid.UUID) -> dict:
        memory_text = await self.memory_service.get_relevant_memory_context(
            user_id=user_id,
            modules=["sleep", "medicine", "fitness", "study", "trading", "scheduler", "habits", "journal"],
            limit=8,
        )
        context = AgentContext(user_id=user_id, memory=memory_text)

        bundles: list[_RecommendationBundle] = []
        for agent in self._agent_instances():
            recommendation = await agent.analyze(context)
            await self._upsert_agent_status(user_id=user_id, agent=agent, recommendation=recommendation)
            if recommendation is None:
                continue
            log_row = await self._create_recommendation_log(user_id=user_id, recommendation=recommendation)
            bundles.append(_RecommendationBundle(recommendation=recommendation))
            await self._log_audit(
                user_id=user_id,
                details={"event": "agent_recommendation", "agent": agent.name, "recommendation_id": str(log_row.id)},
            )

        bundles.sort(key=lambda bundle: bundle.recommendation.urgency, reverse=True)
        executed = None
        if bundles:
            top = bundles[0]
            executed = await self._execute_top_recommendation(user_id=user_id, recommendation=top.recommendation)

        return {
            "recommendations": [bundle.recommendation.model_dump(mode="json") for bundle in bundles],
            "executed_action": executed.model_dump(mode="json") if executed else None,
        }

    async def run_for_all_active_users(self) -> dict:
        from app.modules.auth.models import User

        result = await self.db.execute(select(User.id).where(User.is_active.is_(True)))
        user_ids = [item for item in result.scalars().all()]

        run_count = 0
        action_count = 0
        for user_id in user_ids:
            try:
                payload = await self.run_for_user(user_id=user_id)
                run_count += 1
                if payload.get("executed_action"):
                    action_count += 1
            except Exception as exc:
                logger.warning("orchestrator_user_run_failed", user_id=str(user_id), error=str(exc))

        return {"users_processed": run_count, "actions_executed": action_count}

    async def trigger_agent(self, user_id: uuid.UUID, agent_name: str) -> dict:
        mapping = {agent.name: agent for agent in self._agent_instances()}
        agent = mapping.get(agent_name.lower())
        if agent is None:
            return {"found": False, "agent": agent_name}

        memory_text = await self.memory_service.get_relevant_memory_context(user_id=user_id, limit=6)
        recommendation = await agent.analyze(AgentContext(user_id=user_id, memory=memory_text))
        await self._upsert_agent_status(user_id=user_id, agent=agent, recommendation=recommendation)
        if recommendation is None:
            return {"found": True, "agent": agent_name, "recommendation": None, "action": None}

        await self._create_recommendation_log(user_id=user_id, recommendation=recommendation)
        action = await self._execute_top_recommendation(user_id=user_id, recommendation=recommendation)
        return {
            "found": True,
            "agent": agent_name,
            "recommendation": recommendation.model_dump(mode="json"),
            "action": action.model_dump(mode="json") if action else None,
        }

    async def list_statuses(self, user_id: uuid.UUID) -> list[AgentStatus]:
        result = await self.db.execute(
            select(AgentStatus)
            .where(AgentStatus.user_id == user_id)
            .order_by(AgentStatus.agent_name.asc())
        )
        return list(result.scalars().all())

    async def list_recommendations(self, user_id: uuid.UUID, limit: int = 20) -> list[AgentRecommendationLog]:
        result = await self.db.execute(
            select(AgentRecommendationLog)
            .where(AgentRecommendationLog.user_id == user_id)
            .order_by(desc(AgentRecommendationLog.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _execute_top_recommendation(
        self,
        user_id: uuid.UUID,
        recommendation: AgentRecommendation,
    ) -> AgentAction | None:
        action: AgentAction | None = None
        success = True
        error_text = None

        try:
            if recommendation.urgency >= 70:
                action = await self._apply_high_urgency_response(user_id=user_id, recommendation=recommendation)
            else:
                action = await self._notify_only(user_id=user_id, recommendation=recommendation)
        except Exception as exc:
            success = False
            error_text = str(exc)
            action = AgentAction(
                agent_name=recommendation.agent_name,
                action_type="failed",
                details={"recommended_action": recommendation.recommended_action},
                success=False,
                error=error_text,
            )

        await self._create_action_log(user_id=user_id, action=action, success=success, error=error_text)
        await self._mark_latest_recommendation_executed(user_id=user_id, agent_name=recommendation.agent_name, success=success)
        await self._update_status_action(user_id=user_id, agent_name=recommendation.agent_name, action=action)
        await self._log_audit(
            user_id=user_id,
            details={
                "event": "agent_action",
                "agent": recommendation.agent_name,
                "action_type": action.action_type,
                "success": success,
                "error": error_text,
            },
        )

        return action

    async def _notify_only(self, user_id: uuid.UUID, recommendation: AgentRecommendation) -> AgentAction:
        payload = NotificationPayload(
            title=f"{recommendation.agent_name.capitalize()} Agent",
            body=recommendation.summary,
            notification_type="agent_recommendation",
            data={"recommendation": recommendation.model_dump(mode="json")},
        )
        in_app = await self.messaging.send_in_app_notification(user_id=user_id, payload=payload)
        return AgentAction(
            agent_name=recommendation.agent_name,
            action_type="notify",
            details={"notification_id": str(in_app.id), "channel": "in_app"},
            success=True,
        )

    async def _apply_high_urgency_response(
        self,
        user_id: uuid.UUID,
        recommendation: AgentRecommendation,
    ) -> AgentAction:
        details = {}

        payload = NotificationPayload(
            title=f"{recommendation.agent_name.capitalize()} Agent: high urgency",
            body=recommendation.summary,
            notification_type="agent_high_urgency",
            data={"recommendation": recommendation.model_dump(mode="json")},
        )
        in_app = await self.messaging.send_in_app_notification(user_id=user_id, payload=payload)
        details["in_app_notification"] = str(in_app.id)
        telegram = await self.messaging.send_notification(user_id=user_id, payload=payload)
        details["telegram_delivered"] = telegram.delivered

        if recommendation.agent_name in {"executive", "recovery", "health"}:
            try:
                await self.scheduler.reschedule(
                    user_id=user_id,
                    plan_date=date.today(),
                    request=RescheduleRequest(
                        reason=f"Agent intervention: {recommendation.summary}",
                        trigger="agent",
                        new_constraints={"intensity": "reduced", "buffer_min": 2},
                    ),
                )
                details["schedule_adjusted"] = True
            except Exception as exc:
                details["schedule_adjusted"] = False
                details["schedule_adjustment_error"] = str(exc)

        return AgentAction(
            agent_name=recommendation.agent_name,
            action_type="notify_and_adjust",
            details=details,
            success=True,
        )

    async def _upsert_agent_status(
        self,
        user_id: uuid.UUID,
        agent: BaseAgent,
        recommendation: AgentRecommendation | None,
    ) -> None:
        result = await self.db.execute(
            select(AgentStatus)
            .where(AgentStatus.user_id == user_id)
            .where(AgentStatus.agent_name == agent.name)
            .limit(1)
        )
        row = result.scalar_one_or_none()

        status_value = "idle"
        rec_payload = {}
        if recommendation:
            status_value = "critical" if recommendation.urgency >= 80 else "warning" if recommendation.urgency >= 50 else "stable"
            rec_payload = recommendation.model_dump(mode="json")

        if row is None:
            row = AgentStatus(
                user_id=user_id,
                agent_name=agent.name,
                description=agent.description,
                status=status_value,
                last_recommendation=rec_payload,
                last_action={},
                last_run_at=datetime.now(UTC),
            )
            self.db.add(row)
        else:
            row.description = agent.description
            row.status = status_value
            row.last_recommendation = rec_payload
            row.last_run_at = datetime.now(UTC)

        await self.db.flush()

    async def _create_recommendation_log(
        self,
        user_id: uuid.UUID,
        recommendation: AgentRecommendation,
    ) -> AgentRecommendationLog:
        row = AgentRecommendationLog(
            user_id=user_id,
            agent_name=recommendation.agent_name,
            severity=recommendation.severity,
            urgency=recommendation.urgency,
            recommendation=recommendation.model_dump(mode="json"),
            status="pending",
            is_active=True,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def _create_action_log(
        self,
        user_id: uuid.UUID,
        action: AgentAction,
        success: bool,
        error: str | None,
    ) -> None:
        row = AgentActionLog(
            user_id=user_id,
            agent_name=action.agent_name,
            action_type=action.action_type,
            action_payload=action.model_dump(mode="json"),
            executed_at=datetime.now(UTC),
            success=success,
            error=error,
        )
        self.db.add(row)
        await self.db.flush()

    async def _mark_latest_recommendation_executed(
        self,
        user_id: uuid.UUID,
        agent_name: str,
        success: bool,
    ) -> None:
        result = await self.db.execute(
            select(AgentRecommendationLog)
            .where(AgentRecommendationLog.user_id == user_id)
            .where(AgentRecommendationLog.agent_name == agent_name)
            .where(AgentRecommendationLog.is_active.is_(True))
            .order_by(desc(AgentRecommendationLog.created_at))
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.status = "executed" if success else "failed"
        row.is_active = False
        await self.db.flush()

    async def _update_status_action(self, user_id: uuid.UUID, agent_name: str, action: AgentAction) -> None:
        result = await self.db.execute(
            select(AgentStatus)
            .where(AgentStatus.user_id == user_id)
            .where(AgentStatus.agent_name == agent_name)
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        row.last_action = action.model_dump(mode="json")
        row.last_run_at = datetime.now(UTC)
        await self.db.flush()

    async def _log_audit(self, user_id: uuid.UUID, details: dict) -> None:
        log_row = AuditLog(
            user_id=user_id,
            action=AuditAction.AI_CALL,
            resource_type="agent",
            resource_id=details.get("agent"),
            details=details,
            module="agents",
        )
        self.db.add(log_row)
        await self.db.flush()

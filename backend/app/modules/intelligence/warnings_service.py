"""WILLIAM OS - Predictive warnings service."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import structlog
from app.modules.decisions.models import Decision
from app.modules.intelligence.models import ModuleSignal, PredictiveWarning
from app.modules.intelligence.schemas import PredictiveWarningResponse
from app.modules.journal.models import JournalEntry, JournalMood
from app.modules.medicine.models import Medicine, MedicineLog
from app.modules.messaging.schemas import NotificationPayload
from app.modules.messaging.service import MessagingService
from app.modules.scheduler.schemas import RescheduleRequest
from app.modules.scheduler.service import SchedulerService
from app.modules.sleep.models import SleepDebt, SleepRecord
from app.modules.study.models import MockTest, StudySession, Subject
from app.modules.trading.models import PortfolioSnapshot, TradeLog
from sqlalchemy import desc, func, select

logger = structlog.get_logger(__name__)

_MOOD_SCORE = {
    JournalMood.GREAT: 90.0,
    JournalMood.GOOD: 75.0,
    JournalMood.OKAY: 55.0,
    JournalMood.LOW: 35.0,
    JournalMood.BAD: 20.0,
}


class PredictiveWarningService:
    def __init__(self, db):
        self.db = db
        self.messaging = MessagingService(db)
        self.scheduler = SchedulerService(db)

    async def get_active_warnings(self, user_id: uuid.UUID) -> list[PredictiveWarningResponse]:
        result = await self.db.execute(
            select(PredictiveWarning)
            .where(PredictiveWarning.user_id == user_id)
            .where(PredictiveWarning.is_active.is_(True))
            .order_by(desc(PredictiveWarning.detected_at), desc(PredictiveWarning.created_at))
        )
        return [PredictiveWarningResponse.model_validate(row) for row in result.scalars().all()]

    async def scan_user(self, user_id: uuid.UUID) -> list[PredictiveWarningResponse]:
        detected: dict[str, dict] = {}

        burnout = await self._detect_burnout_risk(user_id)
        if burnout:
            detected["burnout_risk"] = burnout

        sleep_collapse = await self._detect_sleep_collapse_risk(user_id)
        if sleep_collapse:
            detected["sleep_collapse_risk"] = sleep_collapse

        med_streak = await self._detect_missed_medication_streak(user_id)
        if med_streak:
            detected["missed_medication_streak"] = med_streak

        study_dropout = await self._detect_study_dropout_risk(user_id)
        if study_dropout:
            detected["study_dropout_risk"] = study_dropout

        mood_downturn = await self._detect_emotional_downturn(user_id)
        if mood_downturn:
            detected["emotional_downturn"] = mood_downturn

        overtrading = await self._detect_overtrading_risk(user_id)
        if overtrading:
            detected["overtrading_risk"] = overtrading

        collision = await self._detect_deadline_collision(user_id)
        if collision:
            detected["deadline_collision"] = collision

        active_result = await self.db.execute(
            select(PredictiveWarning)
            .where(PredictiveWarning.user_id == user_id)
            .where(PredictiveWarning.is_active.is_(True))
        )
        active_rows = {row.warning_type: row for row in active_result.scalars().all()}

        for warning_type, row in active_rows.items():
            if warning_type not in detected:
                row.is_active = False
                row.resolved_at = datetime.now(UTC)

        output: list[PredictiveWarningResponse] = []
        for warning_type, details in detected.items():
            row = await self.generate_warning(
                user_id=user_id,
                warning_type=warning_type,
                details=details,
            )
            output.append(row)
            await self.trigger_response(user_id=user_id, warning=row)

        return output

    async def generate_warning(
        self,
        user_id: uuid.UUID,
        warning_type: str,
        details: dict,
    ) -> PredictiveWarningResponse:
        explanation, severity, recommended_action = self._compose_warning_payload(warning_type, details)

        existing_result = await self.db.execute(
            select(PredictiveWarning)
            .where(PredictiveWarning.user_id == user_id)
            .where(PredictiveWarning.warning_type == warning_type)
            .where(PredictiveWarning.is_active.is_(True))
            .limit(1)
        )
        row = existing_result.scalar_one_or_none()
        if row is None:
            row = PredictiveWarning(
                user_id=user_id,
                warning_type=warning_type,
                severity=severity,
                explanation=explanation,
                recommended_action=recommended_action,
                details=details,
                is_active=True,
                detected_at=datetime.now(UTC),
                resolved_at=None,
            )
            self.db.add(row)
        else:
            row.severity = severity
            row.explanation = explanation
            row.recommended_action = recommended_action
            row.details = details
            row.detected_at = datetime.now(UTC)
            row.is_active = True
            row.resolved_at = None

        await self.db.flush()
        await self.db.refresh(row)
        return PredictiveWarningResponse.model_validate(row)

    async def trigger_response(self, user_id: uuid.UUID, warning: PredictiveWarningResponse) -> dict:
        actions: list[str] = []

        payload = NotificationPayload(
            title=f"Predictive warning: {warning.warning_type}",
            body=f"[{warning.severity.upper()}] {warning.explanation}",
            notification_type="predictive_warning",
            data=warning.model_dump(mode="json"),
        )

        in_app = await self.messaging.send_in_app_notification(user_id=user_id, payload=payload)
        actions.append(f"in_app:{in_app.id}")

        if warning.severity in {"high", "critical"}:
            telegram = await self.messaging.send_notification(user_id=user_id, payload=payload)
            actions.append(f"telegram_delivered:{telegram.delivered}")

            try:
                await self.scheduler.reschedule(
                    user_id=user_id,
                    plan_date=date.today(),
                    request=RescheduleRequest(
                        reason=f"Predictive warning response: {warning.warning_type}",
                        trigger="predictive_warning",
                        new_constraints={"intensity": "reduced", "insert_recovery_block": True},
                    ),
                )
                actions.append("schedule_reduced")
            except Exception as exc:
                logger.warning("warning_schedule_adjustment_failed", user_id=str(user_id), warning_type=warning.warning_type, error=str(exc))

        return {"actions": actions}

    async def _detect_burnout_risk(self, user_id: uuid.UUID) -> dict | None:
        cutoff_dt = datetime.now(UTC) - timedelta(days=3)
        signals_result = await self.db.execute(
            select(ModuleSignal)
            .where(ModuleSignal.user_id == user_id)
            .where(ModuleSignal.recorded_at >= cutoff_dt)
            .order_by(ModuleSignal.recorded_at.desc())
        )
        rows = list(signals_result.scalars().all())
        if not rows:
            return None

        sleep_energy = [float(r.value) for r in rows if r.source_module == "sleep" and r.signal_type == "energy"]
        habits_focus = [float(r.value) for r in rows if r.source_module == "habits" and r.signal_type == "focus"]
        fitness_energy = [float(r.value) for r in rows if r.source_module == "fitness" and r.signal_type == "energy"]

        plan_rows = await self.db.execute(
            select(func.count(StudySession.id), StudySession.session_date)
            .where(StudySession.user_id == user_id)
            .where(StudySession.session_date >= date.today() - timedelta(days=2))
            .group_by(StudySession.session_date)
        )
        avg_workload = 0.0
        grouped = plan_rows.all()
        if grouped:
            avg_workload = sum(float(count) for count, _ in grouped) / len(grouped)

        low_sleep = sleep_energy and (sum(sleep_energy) / len(sleep_energy)) < 55
        declining_habits = habits_focus and (sum(habits_focus[-2:]) / max(1, len(habits_focus[-2:]))) < 50
        low_energy = fitness_energy and (sum(fitness_energy) / len(fitness_energy)) < 50

        if low_sleep and declining_habits and low_energy and avg_workload >= 1.5:
            return {
                "signals_window_days": 3,
                "sleep_energy_avg": round(sum(sleep_energy) / len(sleep_energy), 2) if sleep_energy else 0,
                "habits_focus_avg": round(sum(habits_focus) / len(habits_focus), 2) if habits_focus else 0,
                "fitness_energy_avg": round(sum(fitness_energy) / len(fitness_energy), 2) if fitness_energy else 0,
                "study_sessions_per_day_avg": round(avg_workload, 2),
            }
        return None

    async def _detect_sleep_collapse_risk(self, user_id: uuid.UUID) -> dict | None:
        debt_result = await self.db.execute(
            select(SleepDebt)
            .where(SleepDebt.user_id == user_id)
            .order_by(desc(SleepDebt.calculated_date))
            .limit(1)
        )
        debt = debt_result.scalar_one_or_none()

        quality_result = await self.db.execute(
            select(SleepRecord.sleep_quality)
            .where(SleepRecord.user_id == user_id)
            .where(SleepRecord.sleep_date >= date.today() - timedelta(days=7))
            .order_by(SleepRecord.sleep_date.asc())
        )
        quality_points = [float(item) for item in quality_result.scalars().all()]
        if len(quality_points) < 3:
            return None

        trend_down = quality_points[-1] < quality_points[0]
        debt_hours = float(debt.debt_hours) if debt else 0.0

        if debt_hours > 4.0 and trend_down:
            return {
                "sleep_debt_hours": debt_hours,
                "quality_start": quality_points[0],
                "quality_latest": quality_points[-1],
            }
        return None

    async def _detect_missed_medication_streak(self, user_id: uuid.UUID) -> dict | None:
        result = await self.db.execute(
            select(func.count(MedicineLog.id))
            .join(Medicine, Medicine.id == MedicineLog.medicine_id)
            .where(Medicine.user_id == user_id)
            .where(MedicineLog.log_date >= date.today() - timedelta(days=7))
            .where(MedicineLog.skipped.is_(True))
        )
        skipped = int(result.scalar() or 0)
        if skipped >= 3:
            return {"missed_doses_7d": skipped}
        return None

    async def _detect_study_dropout_risk(self, user_id: uuid.UUID) -> dict | None:
        subjects_result = await self.db.execute(
            select(func.count(Subject.id)).where(Subject.user_id == user_id)
        )
        subjects_count = int(subjects_result.scalar() or 0)
        if subjects_count == 0:
            return None

        recent_sessions_result = await self.db.execute(
            select(func.count(StudySession.id))
            .where(StudySession.user_id == user_id)
            .where(StudySession.session_date >= date.today() - timedelta(days=5))
        )
        sessions = int(recent_sessions_result.scalar() or 0)
        if sessions == 0:
            return {"active_subjects": subjects_count, "study_sessions_5d": sessions}
        return None

    async def _detect_emotional_downturn(self, user_id: uuid.UUID) -> dict | None:
        result = await self.db.execute(
            select(JournalEntry.entry_date, JournalEntry.mood)
            .where(JournalEntry.user_id == user_id)
            .where(JournalEntry.entry_date >= date.today() - timedelta(days=7))
            .where(JournalEntry.mood.is_not(None))
            .order_by(JournalEntry.entry_date.asc())
        )
        rows = result.all()
        streak = 0
        for _, mood in rows:
            score = _MOOD_SCORE.get(mood, 55.0)
            if score < 40.0:
                streak += 1
            else:
                streak = 0
        if streak >= 3:
            return {"low_mood_streak_days": streak}
        return None

    async def _detect_overtrading_risk(self, user_id: uuid.UUID) -> dict | None:
        trades_result = await self.db.execute(
            select(func.count(TradeLog.id))
            .where(TradeLog.user_id == user_id)
            .where(TradeLog.trade_date >= date.today() - timedelta(days=1))
        )
        trades_24h = int(trades_result.scalar() or 0)

        snapshot_result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.user_id == user_id)
            .order_by(desc(PortfolioSnapshot.snapshot_date))
            .limit(1)
        )
        latest = snapshot_result.scalar_one_or_none()
        down = bool(latest and latest.total_pnl < 0)

        if trades_24h > 5 and down:
            return {"trades_24h": trades_24h, "portfolio_total_pnl": float(latest.total_pnl) if latest else 0.0}
        return None

    async def _detect_deadline_collision(self, user_id: uuid.UUID) -> dict | None:
        horizon = date.today() + timedelta(days=2)
        decision_result = await self.db.execute(
            select(func.count(Decision.id))
            .where(Decision.user_id == user_id)
            .where(Decision.deadline.is_not(None))
            .where(Decision.deadline <= horizon)
            .where(Decision.status != "reviewed")
        )
        decisions_due = int(decision_result.scalar() or 0)

        mock_result = await self.db.execute(
            select(func.count(MockTest.id))
            .where(MockTest.user_id == user_id)
            .where(MockTest.date <= horizon)
            .where(MockTest.date >= date.today())
        )
        mocks_due = int(mock_result.scalar() or 0)

        major_due = decisions_due + mocks_due
        if major_due >= 2:
            return {"major_items_due_48h": major_due, "decision_deadlines": decisions_due, "mock_tests": mocks_due}
        return None

    @staticmethod
    def _compose_warning_payload(warning_type: str, details: dict) -> tuple[str, str, str]:
        if warning_type == "burnout_risk":
            return (
                "Multi-signal burnout pattern detected for the last 3+ days (low sleep, low energy, and habit decline).",
                "high",
                "reduce schedule intensity and activate recovery routine",
            )
        if warning_type == "sleep_collapse_risk":
            return (
                "Sleep debt exceeds 4 hours while sleep quality trend is declining.",
                "critical",
                "prioritize sleep recovery and lighten tomorrow's schedule",
            )
        if warning_type == "missed_medication_streak":
            return (
                "Three or more missed medication logs were detected in the last 7 days.",
                "high",
                "send medication escalation alert and reinforce reminders",
            )
        if warning_type == "study_dropout_risk":
            return (
                "No study sessions were recorded in 5+ days despite active study subjects.",
                "medium",
                "insert short focused study blocks immediately",
            )
        if warning_type == "emotional_downturn":
            return (
                "Journal mood indicates a sustained emotional downturn over consecutive days.",
                "high",
                "reduce cognitive load and activate emotional recovery routine",
            )
        if warning_type == "overtrading_risk":
            return (
                "Trade frequency is elevated while portfolio trend is negative.",
                "high",
                "enforce trading cooldown and reduce discretionary trades",
            )
        if warning_type == "deadline_collision":
            return (
                "Two or more major deadlines are clustered within 48 hours.",
                "medium",
                "rebalance schedule and protect deep work blocks",
            )

        return (
            f"Predictive risk detected: {warning_type}",
            "medium",
            "review and rebalance workload",
        )

"""
WILLIAM OS — Email Intelligence Service
Email account linking, unread email summarization, and morning briefing assembly.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, date, datetime

import httpx
import structlog
from app.core.config import get_settings
from app.core.events import Event, EventType, event_bus
from app.core.security import encrypt_text
from app.modules.email_intel.models import EmailAccount, EmailSummary
from app.modules.email_intel.schemas import (
    EmailAccountResponse,
    EmailSummaryResponse,
    MorningBriefing,
)
from app.modules.scheduler.service import SchedulerService
from app.shared.types import NotFoundError, ValidationError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class EmailIntelService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def connect_account(
        self,
        user_id: uuid.UUID,
        provider: str,
        email_address: str,
        oauth_token: str,
    ) -> EmailAccountResponse:
        if not oauth_token:
            raise ValidationError("oauth_token is required")

        existing = await self.db.execute(
            select(EmailAccount).where(
                and_(
                    EmailAccount.user_id == user_id,
                    EmailAccount.provider == provider,
                    EmailAccount.email_address == email_address,
                )
            )
        )
        account = existing.scalar_one_or_none()
        encrypted_token = encrypt_text(oauth_token, self._token_passphrase(user_id))

        if account:
            account.oauth_token_encrypted = encrypted_token
            account.is_active = True
        else:
            account = EmailAccount(
                user_id=user_id,
                provider=provider,
                email_address=email_address,
                oauth_token_encrypted=encrypted_token,
                is_active=True,
            )
            self.db.add(account)

        await self.db.flush()
        await self.db.refresh(account)

        logger.info("email_account_connected", user_id=str(user_id), account_id=str(account.id))
        return EmailAccountResponse.model_validate(account)

    async def list_accounts(self, user_id: uuid.UUID) -> list[EmailAccountResponse]:
        result = await self.db.execute(
            select(EmailAccount)
            .where(EmailAccount.user_id == user_id)
            .where(EmailAccount.is_active.is_(True))
            .order_by(EmailAccount.created_at.desc())
        )
        accounts = result.scalars().all()
        return [EmailAccountResponse.model_validate(account) for account in accounts]

    async def sync_emails(self, user_id: uuid.UUID) -> EmailSummaryResponse:
        accounts = await self.list_accounts(user_id)
        if not accounts:
            raise ValidationError("No active email account connected")

        start = time.monotonic()
        unread_subjects = await self._fetch_unread_emails(accounts)
        summary_payload = await self._summarize_unread(unread_subjects)
        latency_ms = int((time.monotonic() - start) * 1000)

        summary = EmailSummary(
            user_id=user_id,
            summary_date=date.today(),
            email_count=len(unread_subjects),
            summary_text=summary_payload["summary_text"],
            priority_emails=summary_payload["priority_emails"],
            action_items=summary_payload["action_items"],
            generated_by=self.settings.openrouter_model,
            generation_latency_ms=latency_ms,
        )
        self.db.add(summary)

        now = datetime.now(UTC)
        for account in await self._get_active_account_models(user_id):
            account.last_sync_at = now

        await self.db.flush()
        await self.db.refresh(summary)

        await event_bus.publish(
            Event(
                type=EventType.EMAIL_SUMMARY_READY,
                data={
                    "summary_id": str(summary.id),
                    "summary_date": str(summary.summary_date),
                    "email_count": summary.email_count,
                },
                user_id=user_id,
            )
        )

        logger.info(
            "email_synced",
            user_id=str(user_id),
            summary_id=str(summary.id),
            email_count=summary.email_count,
            latency_ms=latency_ms,
        )
        return EmailSummaryResponse.model_validate(summary)

    async def get_latest_summary(self, user_id: uuid.UUID) -> EmailSummaryResponse | None:
        result = await self.db.execute(
            select(EmailSummary)
            .where(EmailSummary.user_id == user_id)
            .order_by(EmailSummary.summary_date.desc(), EmailSummary.created_at.desc())
            .limit(1)
        )
        summary = result.scalar_one_or_none()
        if not summary:
            return None
        return EmailSummaryResponse.model_validate(summary)

    async def build_morning_briefing(self, user_id: uuid.UUID) -> MorningBriefing:
        schedule_summary: dict
        top_priorities: list[str] = []

        scheduler = SchedulerService(self.db)
        try:
            today_plan = await scheduler.get_today(user_id)
            schedule_summary = {
                "plan_date": str(today_plan.plan_date),
                "status": today_plan.status.value,
                "total_blocks": len(today_plan.blocks),
            }
            ordered = sorted(today_plan.blocks, key=lambda block: block.priority)
            top_priorities = [block.title for block in ordered[:3]]
        except Exception:
            schedule_summary = {
                "plan_date": str(date.today()),
                "status": "not_available",
                "total_blocks": 0,
            }

        latest_summary = await self.get_latest_summary(user_id)
        email_summary = latest_summary.model_dump(mode="json") if latest_summary else None

        return MorningBriefing(
            schedule_summary=schedule_summary,
            email_summary=email_summary,
            weather=None,
            top_priorities=top_priorities,
        )

    async def disconnect_account(self, user_id: uuid.UUID, account_id: uuid.UUID) -> None:
        account = await self._get_account_for_user(user_id=user_id, account_id=account_id)
        account.is_active = False
        await self.db.flush()

        logger.info("email_account_disconnected", user_id=str(user_id), account_id=str(account_id))

    async def _get_account_for_user(
        self,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> EmailAccount:
        result = await self.db.execute(
            select(EmailAccount).where(
                and_(
                    EmailAccount.id == account_id,
                    EmailAccount.user_id == user_id,
                )
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NotFoundError("EmailAccount", str(account_id))
        return account

    async def _get_active_account_models(self, user_id: uuid.UUID) -> list[EmailAccount]:
        result = await self.db.execute(
            select(EmailAccount)
            .where(EmailAccount.user_id == user_id)
            .where(EmailAccount.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def _fetch_unread_emails(self, accounts: list[EmailAccountResponse]) -> list[str]:
        subjects: list[str] = []
        for account in accounts:
            subjects.extend(
                [
                    f"[{account.provider}] Important update from team for {account.email_address}",
                    f"[{account.provider}] Meeting invite and agenda",
                ]
            )
        return subjects

    async def _summarize_unread(self, subjects: list[str]) -> dict:
        if not subjects:
            return {
                "summary_text": "No unread emails.",
                "priority_emails": [],
                "action_items": [],
            }

        api_key = self.settings.openrouter_api_key.get_secret_value()
        if not api_key:
            return self._fallback_summary(subjects)

        prompt = (
            "Summarize these unread email subjects. Return JSON with keys: "
            "summary_text (string), priority_emails (array of objects with subject), "
            "action_items (array of strings). Subjects: "
            f"{json.dumps(subjects)}"
        )
        payload = {
            "model": self.settings.openrouter_model,
            "messages": [
                {"role": "system", "content": "You are an assistant for morning email triage."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 400,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.base_url,
            "X-Title": self.settings.app_name,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                return self._fallback_summary(subjects)
            fallback = self._fallback_summary(subjects)
            return {
                "summary_text": parsed.get("summary_text") or fallback["summary_text"],
                "priority_emails": parsed.get("priority_emails") or [],
                "action_items": parsed.get("action_items") or [],
            }
        except Exception as exc:
            logger.warning("email_summary_generation_failed", error=str(exc))
            return self._fallback_summary(subjects)

    @staticmethod
    def _fallback_summary(subjects: list[str]) -> dict:
        priority = [{"subject": subject} for subject in subjects[:3]]
        action_items = [f"Review: {subject}" for subject in subjects[:3]]
        return {
            "summary_text": (
                f"You have {len(subjects)} unread emails. Review the top priorities first."
            ),
            "priority_emails": priority,
            "action_items": action_items,
        }

    @staticmethod
    def _token_passphrase(user_id: uuid.UUID) -> str:
        return f"email-token-passphrase:{user_id}"

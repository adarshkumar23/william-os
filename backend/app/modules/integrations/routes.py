"""WILLIAM OS - Integrations routes."""

from __future__ import annotations

import uuid

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.integrations.schemas import (
    IntegrationApiKeyCreateIn,
    IntegrationDecisionChooseIn,
    IntegrationDecisionCreateIn,
    IntegrationDecisionOutcomeIn,
    IntegrationHabitCheckInIn,
    IntegrationJournalEntryIn,
    IntegrationMedicineLogIn,
    IntegrationMoodIn,
    IntegrationScheduleBlockIn,
    IntegrationScheduleGenerateIn,
    IntegrationSleepIn,
    IntegrationStudySessionIn,
    IntegrationTelegramDailyIn,
    IntegrationTradeIn,
    IntegrationTriggerIn,
    IntegrationWorkoutIn,
)
from app.modules.integrations.service import IntegrationsService
from app.shared.types import AuthenticationError, success
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/integrations", tags=["Integrations"])


async def _auth_meta(
    authorization: str = Header(..., description="Bearer <jwt-or-wos-api-key>"),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await service.authenticate_bearer(authorization)


async def _run_with_log(
    db: AsyncSession,
    user_id: uuid.UUID,
    source: str,
    endpoint: str,
    payload: dict,
    fn,
):
    service = IntegrationsService(db)
    try:
        result = await fn()
        await service.log_integration_call(
            user_id=user_id,
            endpoint=endpoint,
            source=source,
            payload=payload,
            success=True,
            error_message=None,
        )
        await db.commit()
        return success(result)
    except Exception as exc:
        await db.rollback()
        await service.log_integration_call(
            user_id=user_id,
            endpoint=endpoint,
            source=source,
            payload=payload,
            success=False,
            error_message=str(exc),
        )
        await db.commit()
        raise


@router.post("/api-keys", status_code=201)
async def create_api_key(
    data: IntegrationApiKeyCreateIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = IntegrationsService(db)
    payload = await service.create_api_key(user_id=user_id, data=data)
    return success(payload.model_dump(mode="json"))


@router.get("/api-keys")
async def list_api_keys(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = IntegrationsService(db)
    payload = await service.list_api_keys(user_id=user_id)
    return success([item.model_dump(mode="json") for item in payload])


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = IntegrationsService(db)
    deleted = await service.revoke_api_key(user_id=user_id, key_id=key_id)
    return success({"revoked": deleted})


@router.post("/sleep")
async def integrations_sleep(
    body: IntegrationSleepIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "sleep",
        body.model_dump(mode="json"),
        lambda: service.ingest_sleep(auth.user_id, body),
    )


@router.post("/workout")
async def integrations_workout(
    body: IntegrationWorkoutIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "workout",
        body.model_dump(mode="json"),
        lambda: service.ingest_workout(auth.user_id, body),
    )


@router.post("/habit-checkin")
async def integrations_habit_checkin(
    body: IntegrationHabitCheckInIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "habit-checkin",
        body.model_dump(mode="json"),
        lambda: service.ingest_habit_checkin(auth.user_id, body),
    )


@router.post("/journal-entry")
async def integrations_journal_entry(
    body: IntegrationJournalEntryIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
    x_journal_passphrase: str | None = Header(default=None, alias="X-Journal-Passphrase"),
):
    if not x_journal_passphrase:
        raise AuthenticationError("X-Journal-Passphrase header is required")

    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "journal-entry",
        body.model_dump(mode="json"),
        lambda: service.ingest_journal_entry(auth.user_id, body, x_journal_passphrase),
    )


@router.post("/trade")
async def integrations_trade(
    body: IntegrationTradeIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "trade",
        body.model_dump(mode="json"),
        lambda: service.ingest_trade(auth.user_id, body),
    )


@router.post("/medicine-log")
async def integrations_medicine_log(
    body: IntegrationMedicineLogIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "medicine-log",
        body.model_dump(mode="json"),
        lambda: service.ingest_medicine_log(auth.user_id, body),
    )


@router.post("/mood")
async def integrations_mood(
    body: IntegrationMoodIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
    x_journal_passphrase: str | None = Header(default=None, alias="X-Journal-Passphrase"),
):
    if not x_journal_passphrase:
        raise AuthenticationError("X-Journal-Passphrase header is required")

    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "mood",
        body.model_dump(mode="json"),
        lambda: service.ingest_mood(auth.user_id, body, x_journal_passphrase),
    )


@router.post("/study-session")
async def integrations_study_session(
    body: IntegrationStudySessionIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "study-session",
        body.model_dump(mode="json"),
        lambda: service.ingest_study_session(auth.user_id, body),
    )


@router.post("/schedule/generate")
async def integrations_schedule_generate(
    body: IntegrationScheduleGenerateIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "schedule-generate",
        body.model_dump(mode="json"),
        lambda: service.ingest_schedule_generate(auth.user_id, body),
    )


@router.post("/schedule/block")
async def integrations_schedule_block(
    body: IntegrationScheduleBlockIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "schedule-block",
        body.model_dump(mode="json"),
        lambda: service.ingest_schedule_block(auth.user_id, body),
    )


@router.post("/decision")
async def integrations_decision_create(
    body: IntegrationDecisionCreateIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "decision-create",
        body.model_dump(mode="json"),
        lambda: service.ingest_decision_create(auth.user_id, body),
    )


@router.post("/decision/choose")
async def integrations_decision_choose(
    body: IntegrationDecisionChooseIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "decision-choose",
        body.model_dump(mode="json"),
        lambda: service.ingest_decision_choose(auth.user_id, body),
    )


@router.post("/decision/outcome")
async def integrations_decision_outcome(
    body: IntegrationDecisionOutcomeIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "decision-outcome",
        body.model_dump(mode="json"),
        lambda: service.ingest_decision_outcome(auth.user_id, body),
    )


@router.post("/telegram/daily")
async def integrations_telegram_daily(
    body: IntegrationTelegramDailyIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "telegram-daily",
        body.model_dump(mode="json"),
        lambda: service.telegram_daily_action(auth.user_id, body),
    )


@router.get("/webhook-test")
async def integrations_webhook_test(
    request: Request,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    payload = {
        "connected": True,
        "user_id": str(auth.user_id),
        "source": auth.source,
        "token_type": auth.token_type,
        "path": request.url.path,
    }
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "webhook-test",
        payload,
        lambda: payload,
    )


@router.post("/trigger")
async def integrations_trigger(
    body: IntegrationTriggerIn,
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "trigger",
        body.model_dump(mode="json"),
        lambda: service.trigger_event(auth.user_id, body),
    )


@router.get("/daily-summary")
async def integrations_daily_summary(
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return await _run_with_log(
        db,
        auth.user_id,
        auth.source,
        "daily-summary",
        {},
        lambda: service.daily_summary(auth.user_id),
    )


@router.get("/sync-status")
async def integrations_sync_status(
    auth=Depends(_auth_meta),
    db: AsyncSession = Depends(get_db),
):
    service = IntegrationsService(db)
    return success(await service.sync_status(auth.user_id))

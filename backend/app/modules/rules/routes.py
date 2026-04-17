"""WILLIAM OS - User automation rules routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.rules.schemas import (
    RuleCreate,
    RuleUpdate,
    RuleWebhookTrigger,
    WebhookRegistrationCreate,
)
from app.modules.rules.service import RulesService
from app.shared.types import success

router = APIRouter(prefix="/rules", tags=["Rules Engine"])


@router.get("")
async def list_rules(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RulesService(db)
    rows = await service.list_rules(user_id=user_id)
    return success([item.model_dump(mode="json") for item in rows])


@router.get("/templates")
async def list_rule_templates(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _ = user_id
    service = RulesService(db)
    rows = await service.list_templates()
    return success([item.model_dump(mode="json") for item in rows])


@router.post("", status_code=201)
async def create_rule(
    payload: RuleCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RulesService(db)
    row = await service.create_rule(user_id=user_id, rule_data=payload)
    return success(row.model_dump(mode="json"))


@router.put("/{rule_id}")
async def update_rule(
    rule_id: uuid.UUID,
    payload: RuleUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RulesService(db)
    row = await service.update_rule(user_id=user_id, rule_id=rule_id, data=payload)
    return success(row.model_dump(mode="json"))


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RulesService(db)
    await service.delete_rule(user_id=user_id, rule_id=rule_id)
    return success({"deleted": True})


@router.post("/evaluate-now")
async def evaluate_rules_now(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RulesService(db)
    result = await service.evaluate_rules(user_id=user_id)
    return success(result.model_dump(mode="json"))


@router.post("/webhook")
async def evaluate_rules_webhook(
    payload: RuleWebhookTrigger,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RulesService(db)
    result = await service.evaluate_webhook_event(
        user_id=user_id,
        trigger_module=payload.trigger_module,
        event_name=payload.event_name,
        event_data=payload.data,
    )
    return success(result.model_dump(mode="json"))


@router.post("/webhooks/register", status_code=201)
async def register_webhook(
    payload: WebhookRegistrationCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RulesService(db)
    row = await service.register_webhook(user_id=user_id, payload=payload)
    return success(row.model_dump(mode="json"))


@router.get("/webhooks")
async def list_webhooks(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RulesService(db)
    rows = await service.list_webhooks(user_id=user_id)
    return success([item.model_dump(mode="json") for item in rows])


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RulesService(db)
    deleted = await service.delete_webhook(user_id=user_id, webhook_id=webhook_id)
    return success({"deleted": deleted})


@router.get("/webhooks/health")
async def webhooks_health(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RulesService(db)
    payload = await service.webhooks_health(user_id=user_id)
    return success(payload)


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(
    webhook_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RulesService(db)
    payload = await service.test_webhook(user_id=user_id, webhook_id=webhook_id)
    return success(payload)

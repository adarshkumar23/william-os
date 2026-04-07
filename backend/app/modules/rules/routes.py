"""WILLIAM OS - User automation rules routes."""

from __future__ import annotations

import uuid

from app.core.database import get_db
from app.modules.auth.routes import get_current_user_id
from app.modules.rules.schemas import RuleCreate, RuleUpdate
from app.modules.rules.service import RulesService
from app.shared.types import success
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

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

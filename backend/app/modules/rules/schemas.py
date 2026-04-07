"""WILLIAM OS - User automation rules schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    trigger_module: str = Field(min_length=1, max_length=50)
    trigger_condition: dict = Field(default_factory=dict)
    action_module: str = Field(min_length=1, max_length=50)
    action_type: str = Field(min_length=1, max_length=80)
    action_params: dict = Field(default_factory=dict)
    is_active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    trigger_module: str | None = Field(default=None, min_length=1, max_length=50)
    trigger_condition: dict | None = None
    action_module: str | None = Field(default=None, min_length=1, max_length=50)
    action_type: str | None = Field(default=None, min_length=1, max_length=80)
    action_params: dict | None = None
    is_active: bool | None = None


class RuleResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    trigger_module: str
    trigger_condition: dict
    action_module: str
    action_type: str
    action_params: dict
    is_active: bool
    last_triggered: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RuleExecutionLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    rule_id: UUID
    matched: bool
    action_success: bool
    context_snapshot: dict
    action_result: dict
    error: str | None
    executed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class RuleEvaluateResponse(BaseModel):
    evaluated: int
    matched: int
    executed: int
    logs: list[RuleExecutionLogResponse]


class RuleTemplate(BaseModel):
    name: str
    trigger_module: str
    trigger_condition: dict
    action_module: str
    action_type: str
    action_params: dict

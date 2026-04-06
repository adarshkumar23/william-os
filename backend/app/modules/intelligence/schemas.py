"""
WILLIAM OS — Intelligence Schemas
Request and response contracts for intelligence endpoints.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ModuleSignalResponse(BaseModel):
    id: UUID
    user_id: UUID
    source_module: str
    signal_type: str
    value: float
    recorded_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class CrossModuleRuleCreate(BaseModel):
    trigger_module: str = Field(min_length=1, max_length=50)
    trigger_condition: dict = Field(default_factory=dict)
    affected_module: str = Field(min_length=1, max_length=50)
    adjustment_type: str = Field(min_length=1, max_length=50)
    adjustment_value: float
    is_active: bool = True


class CrossModuleRuleResponse(BaseModel):
    id: UUID
    trigger_module: str
    trigger_condition: dict
    affected_module: str
    adjustment_type: str
    adjustment_value: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdjustmentItem(BaseModel):
    rule_name: str
    affected_module: str
    field: str
    operation: str
    value: float
    target_label: str | None = None


class AdjustmentsResponse(BaseModel):
    generated_at: datetime
    count: int
    adjustments: dict[str, list[AdjustmentItem]]


class LifeScoreResponse(BaseModel):
    id: UUID
    user_id: UUID
    score: float
    component_scores: dict[str, float]
    explanation: str
    computed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class LifeScoreHistoryPoint(BaseModel):
    score: float
    computed_at: datetime

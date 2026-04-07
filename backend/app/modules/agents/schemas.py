"""WILLIAM OS - Agent layer schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRecommendation(BaseModel):
    agent_name: str
    summary: str
    severity: str = Field(default="low")
    urgency: int = Field(default=0, ge=0, le=100)
    recommended_action: str
    context: dict = Field(default_factory=dict)


class AgentAction(BaseModel):
    agent_name: str
    action_type: str
    details: dict = Field(default_factory=dict)
    success: bool = True
    error: str | None = None


class AgentStatusResponse(BaseModel):
    id: UUID
    user_id: UUID
    agent_name: str
    description: str
    status: str
    last_recommendation: dict
    last_action: dict
    last_run_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentRecommendationLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    agent_name: str
    severity: str
    urgency: int
    recommendation: dict
    status: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentActionLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    agent_name: str
    action_type: str
    action_payload: dict
    executed_at: datetime
    success: bool
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

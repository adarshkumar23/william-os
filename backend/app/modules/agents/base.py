"""WILLIAM OS - Base interfaces for autonomous agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.modules.agents.schemas import AgentAction, AgentRecommendation


@dataclass(slots=True)
class AgentContext:
    user_id: Any
    memory: str


class BaseAgent(ABC):
    name: str
    description: str
    memory: str
    goals: list[str]
    permissions: list[str]
    action_scope: str
    notification_style: str

    @abstractmethod
    async def analyze(self, context: AgentContext) -> AgentRecommendation | None:
        raise NotImplementedError

    @abstractmethod
    async def act(self, recommendation: AgentRecommendation) -> AgentAction:
        raise NotImplementedError

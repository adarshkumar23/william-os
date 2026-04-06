"""
WILLIAM OS - A/B experiment assignment endpoints.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.experiments import get_assignments
from app.modules.auth.routes import get_current_user_id
from app.shared.types import success

router = APIRouter(prefix="/experiments", tags=["Experiments"])
UserIdDep = Annotated[uuid.UUID, Depends(get_current_user_id)]

EXPERIMENTS: dict[str, list[str]] = {
    "dashboard_layout": ["control", "focus"],
    "habit_prompt_style": ["compact", "coaching"],
    "journal_summary_cta": ["off", "inline"],
}


@router.get("/assignments")
async def assignments(
    user_id: UserIdDep,
) -> dict:
    settings = get_settings()
    allocated = get_assignments(
        user_id=user_id,
        experiments=EXPERIMENTS,
        seed=settings.experiment_rollout_seed,
    )
    return success({"assignments": allocated})

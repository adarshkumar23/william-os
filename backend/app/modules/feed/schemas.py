"""WILLIAM OS - Activity Feed Schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ActivityFeedItem(BaseModel):
    event_id: str
    timestamp: datetime
    module: str
    action: str
    summary: str
    icon_key: str
    xp_earned: int | None = None

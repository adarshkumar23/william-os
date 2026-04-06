"""
WILLIAM OS — Realtime WebSocket Sync
Per-user connection manager and authenticated sync endpoint.
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_token

logger = structlog.get_logger(__name__)

SYNC_MESSAGE_TYPES = {
    "schedule_updated",
    "habit_checked_in",
    "medicine_logged",
    "journal_created",
    "block_completed",
}


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[uuid.UUID, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.setdefault(user_id, []).append(websocket)

        logger.info("ws_connected", user_id=str(user_id), count=self.connection_count(user_id))

    async def disconnect(self, user_id: uuid.UUID, websocket: WebSocket) -> None:
        async with self._lock:
            current = self.active_connections.get(user_id, [])
            if websocket in current:
                current.remove(websocket)
            if not current:
                self.active_connections.pop(user_id, None)

        logger.info("ws_disconnected", user_id=str(user_id), count=self.connection_count(user_id))

    async def broadcast(
        self,
        user_id: uuid.UUID,
        message: dict,
        sender: WebSocket | None = None,
    ) -> None:
        async with self._lock:
            targets = list(self.active_connections.get(user_id, []))

        stale: list[WebSocket] = []
        for websocket in targets:
            if sender is not None and websocket is sender:
                continue
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)

        for websocket in stale:
            await self.disconnect(user_id, websocket)

    def connection_count(self, user_id: uuid.UUID) -> int:
        return len(self.active_connections.get(user_id, []))


connection_manager = ConnectionManager()


def _authenticate_websocket_token(token: str | None) -> uuid.UUID | None:
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access" or not payload.get("sub"):
            return None
        return uuid.UUID(payload["sub"])
    except Exception:
        return None


async def websocket_sync_endpoint(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    user_id = _authenticate_websocket_token(token)
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await connection_manager.connect(user_id=user_id, websocket=websocket)
    try:
        while True:
            incoming = await websocket.receive_json()
            if not isinstance(incoming, dict):
                continue

            message_type = str(incoming.get("type") or "")
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if message_type not in SYNC_MESSAGE_TYPES:
                continue

            payload = {
                "type": message_type,
                "data": incoming.get("data") or {},
            }
            await connection_manager.broadcast(user_id=user_id, message=payload, sender=websocket)
    except WebSocketDisconnect:
        pass
    finally:
        await connection_manager.disconnect(user_id=user_id, websocket=websocket)


def register_websocket_routes(app: FastAPI) -> None:
    app.websocket("/ws/v1/sync")(websocket_sync_endpoint)

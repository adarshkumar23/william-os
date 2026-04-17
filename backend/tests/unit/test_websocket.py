"""
WILLIAM OS — WebSocket Sync Tests
Connection auth, connect/disconnect bookkeeping, and cross-device broadcast.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.core.websocket import connection_manager, register_websocket_routes


@pytest.fixture(autouse=True)
def _clear_connections() -> None:
    connection_manager.active_connections.clear()


def _app() -> FastAPI:
    app = FastAPI()
    register_websocket_routes(app)
    return app


def test_websocket_auth_required() -> None:
    app = _app()
    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws/v1/sync"),
    ):
        pass


def test_websocket_connect_disconnect_tracks_user_connections() -> None:
    app = _app()
    user_id = uuid.uuid4()
    token = create_access_token(user_id)

    with TestClient(app) as client, client.websocket_connect(f"/ws/v1/sync?token={token}"):
        assert connection_manager.connection_count(user_id) == 1

    assert connection_manager.connection_count(user_id) == 0


def test_websocket_broadcasts_to_other_devices_only() -> None:
    app = _app()
    user_id = uuid.uuid4()
    token = create_access_token(user_id)

    with (
        TestClient(app) as client,
        client.websocket_connect(f"/ws/v1/sync?token={token}") as ws_sender,
        client.websocket_connect(f"/ws/v1/sync?token={token}") as ws_receiver,
    ):
        ws_sender.send_json(
            {
                "type": "habit_checked_in",
                "data": {"habit_id": "abc123"},
            }
        )
        message = ws_receiver.receive_json()

    assert message["type"] == "habit_checked_in"
    assert message["data"]["habit_id"] == "abc123"

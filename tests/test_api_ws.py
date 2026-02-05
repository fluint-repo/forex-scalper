"""Tests for WebSocket endpoint."""

import sys
import json

sys.path.insert(0, ".")

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_engine_manager
from src.api.state import EngineManager


@pytest.fixture
def mgr():
    return EngineManager()


@pytest.fixture
def client(mgr):
    app.dependency_overrides[get_engine_manager] = lambda: mgr
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestWebSocket:
    def test_connect(self, client):
        with client.websocket_connect("/ws/stream") as ws:
            ws.send_text("ping")
            data = ws.receive_text()
            msg = json.loads(data)
            assert msg["type"] == "pong"

    def test_multiple_pings(self, client):
        with client.websocket_connect("/ws/stream") as ws:
            for _ in range(3):
                ws.send_text("ping")
                data = ws.receive_text()
                msg = json.loads(data)
                assert msg["type"] == "pong"

    def test_disconnect(self, client):
        """Test that disconnecting doesn't raise errors."""
        with client.websocket_connect("/ws/stream") as ws:
            ws.send_text("ping")
            ws.receive_text()
        # No exception = success

    def test_invalid_message(self, client):
        """Non-ping messages should not crash."""
        with client.websocket_connect("/ws/stream") as ws:
            ws.send_text("ping")
            ws.receive_text()  # pong

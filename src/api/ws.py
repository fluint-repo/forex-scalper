"""WebSocket endpoint for real-time streaming to the dashboard."""

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.deps import get_engine_manager
from src.utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        log.info("ws_connected", clients=len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)
        log.info("ws_disconnected", clients=len(self._connections))

    async def broadcast(self, message: dict) -> None:
        data = json.dumps(message, default=str)
        dead = []
        for ws in self._connections:
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def client_count(self) -> int:
        return len(self._connections)


ws_manager = ConnectionManager()

# Tick throttling: at most 1 tick broadcast per second
_last_tick_broadcast = 0.0
_TICK_THROTTLE_SECONDS = 1.0


def _on_engine_event(event_type: str, data: Any) -> None:
    """Sync callback from EventBus → schedules async broadcast."""
    global _last_tick_broadcast

    if ws_manager.client_count == 0:
        return

    # Throttle tick events
    if event_type == "tick":
        now = time.time()
        if now - _last_tick_broadcast < _TICK_THROTTLE_SECONDS:
            return
        _last_tick_broadcast = now

    message = {"type": event_type, "data": data}

    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(asyncio.ensure_future, ws_manager.broadcast(message))
    except RuntimeError:
        pass


def setup_event_bus_bridge() -> None:
    """Subscribe to engine events if event_bus is available."""
    mgr = get_engine_manager()
    if mgr.event_bus is not None:
        for evt in ("tick", "candle_closed", "signal", "order_filled",
                     "position_closed", "engine_started", "engine_stopped"):
            mgr.event_bus.subscribe(evt, _on_engine_event)


@router.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            # Keep connection alive; handle client pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


async def periodic_account_broadcast() -> None:
    """Background task: broadcasts account info + positions periodically."""
    from config.settings import WS_BROADCAST_INTERVAL

    while True:
        await asyncio.sleep(WS_BROADCAST_INTERVAL)
        if ws_manager.client_count == 0:
            continue

        mgr = get_engine_manager()
        if mgr.broker is None:
            continue

        try:
            account = mgr.broker.get_account_info()
            positions = mgr.broker.get_positions()
            await ws_manager.broadcast({
                "type": "account_update",
                "data": {
                    "account": account,
                    "positions": positions,
                },
            })
        except Exception:
            log.exception("periodic_broadcast_error")

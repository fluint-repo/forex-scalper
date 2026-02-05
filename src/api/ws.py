"""WebSocket endpoint for real-time streaming to the dashboard."""

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config.settings import API_KEY
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

# Track which event buses we've subscribed to
_subscribed_buses: set[int] = set()


def _make_event_handler(engine_id: str = ""):
    """Create event handler that includes engine_id in messages."""
    def _on_engine_event(event_type: str, data: Any) -> None:
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
        if engine_id:
            message["engine_id"] = engine_id

        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(asyncio.ensure_future, ws_manager.broadcast(message))
        except RuntimeError:
            pass

    return _on_engine_event


def setup_event_bus_bridge(engine_id: str = "") -> None:
    """Subscribe to engine events if event_bus is available."""
    mgr = get_engine_manager()

    # Multi-engine: subscribe to all event buses
    for inst in (mgr._engines.values() if hasattr(mgr, '_engines') else []):
        bus_id = id(inst.event_bus)
        if bus_id not in _subscribed_buses:
            handler = _make_event_handler(inst.engine_id)
            for evt in ("tick", "candle_closed", "signal", "order_filled",
                         "position_closed", "engine_started", "engine_stopped",
                         "circuit_breaker", "risk_blocked",
                         "llm_assessment", "llm_blocked"):
                inst.event_bus.subscribe(evt, handler)
            _subscribed_buses.add(bus_id)

    # Legacy fallback
    if mgr.event_bus is not None:
        bus_id = id(mgr.event_bus)
        if bus_id not in _subscribed_buses:
            handler = _make_event_handler(engine_id)
            for evt in ("tick", "candle_closed", "signal", "order_filled",
                         "position_closed", "engine_started", "engine_stopped",
                         "circuit_breaker", "risk_blocked",
                         "llm_assessment", "llm_blocked"):
                mgr.event_bus.subscribe(evt, handler)
            _subscribed_buses.add(bus_id)


@router.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    # Check API key if configured
    if API_KEY:
        key = ws.query_params.get("api_key", "")
        if key != API_KEY:
            await ws.close(code=4001, reason="Invalid API key")
            return

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

        # Subscribe to any new event buses
        setup_event_bus_bridge()

        if not mgr.is_running:
            continue

        try:
            account = mgr.get_aggregated_account()
            positions = mgr.get_all_positions()
            engines = mgr.list_engines()
            await ws_manager.broadcast({
                "type": "account_update",
                "data": {
                    "account": account,
                    "positions": positions,
                    "engines": engines,
                },
            })
        except Exception:
            log.exception("periodic_broadcast_error")

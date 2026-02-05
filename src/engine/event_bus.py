"""Lightweight thread-safe pub/sub event bus for engine→API communication."""

import threading
from collections import defaultdict
from typing import Any, Callable

from src.utils.logger import get_logger

log = get_logger(__name__)

EventHandler = Callable[[str, Any], None]


class EventBus:
    """Thread-safe publish/subscribe event bus.

    Event types: tick, candle_closed, signal, order_filled, position_closed,
                 engine_started, engine_stopped
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        with self._lock:
            handlers = self._handlers.get(event_type, [])
            try:
                handlers.remove(handler)
            except ValueError:
                pass

    def publish(self, event_type: str, data: Any = None) -> None:
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))
        for handler in handlers:
            try:
                handler(event_type, data)
            except Exception:
                log.exception("event_handler_error", event_type=event_type)

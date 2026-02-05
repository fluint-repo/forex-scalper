"""NotificationService — dispatches EventBus events to notification backends."""

import asyncio
from typing import Any

from src.engine.event_bus import EventBus
from src.notifications.base import NotificationBackend
from src.utils.logger import get_logger

log = get_logger(__name__)


class NotificationService:
    """Subscribes to EventBus events and sends formatted notifications."""

    def __init__(
        self,
        backends: list[NotificationBackend],
        event_types: list[str] | None = None,
    ) -> None:
        self.backends = backends
        self.event_types = event_types or [
            "order_filled", "position_closed", "circuit_breaker",
            "engine_started", "engine_stopped",
        ]

    def connect(self, event_bus: EventBus) -> None:
        """Subscribe to configured event types on the event bus."""
        for evt in self.event_types:
            event_bus.subscribe(evt, self._on_event)

    def _on_event(self, event_type: str, data: Any) -> None:
        """Sync callback from EventBus → schedules async sends."""
        if event_type not in self.event_types:
            return

        subject, body = self._format_message(event_type, data)

        try:
            loop = asyncio.get_running_loop()
            loop.call_soon_threadsafe(
                asyncio.ensure_future, self._dispatch(subject, body)
            )
        except RuntimeError:
            # No running event loop — run synchronously in new loop
            try:
                asyncio.run(self._dispatch(subject, body))
            except Exception:
                log.exception("notification_dispatch_failed")

    async def _dispatch(self, subject: str, body: str) -> None:
        """Send to all backends, catching individual failures."""
        for backend in self.backends:
            try:
                await backend.send(subject, body)
            except Exception:
                log.exception("notification_backend_failed", backend=backend.name)

    @staticmethod
    def _format_message(event_type: str, data: Any) -> tuple[str, str]:
        """Format event into human-readable subject/body."""
        data = data or {}

        if event_type == "order_filled":
            subject = f"Order Filled: {data.get('side', '')} {data.get('volume', '')}"
            body = (
                f"Side: {data.get('side', 'N/A')}\n"
                f"Price: {data.get('price', 'N/A')}\n"
                f"Volume: {data.get('volume', 'N/A')}\n"
                f"Order ID: {data.get('order_id', 'N/A')}"
            )
        elif event_type == "position_closed":
            subject = "Position Closed"
            body = f"Order ID: {data.get('order_id', 'N/A')}"
        elif event_type == "circuit_breaker":
            subject = "CIRCUIT BREAKER TRIGGERED"
            body = f"Reason: {data.get('reason', 'daily loss limit')}"
        elif event_type == "engine_started":
            subject = "Engine Started"
            body = (
                f"Symbol: {data.get('symbol', 'N/A')}\n"
                f"Strategy: {data.get('strategy', 'N/A')}"
            )
        elif event_type == "engine_stopped":
            subject = "Engine Stopped"
            body = "Trading engine has been stopped."
        elif event_type == "stream_disconnected":
            subject = "Stream Disconnected"
            body = f"Symbol: {data.get('symbol', 'N/A')}\nThe price stream has disconnected and is attempting to reconnect."
        elif event_type == "stream_dead":
            subject = "CRITICAL: Stream Dead"
            body = f"Symbol: {data.get('symbol', 'N/A')}\nThe price stream has died after exhausting all reconnection attempts. Manual intervention required."
        elif event_type == "engine_health_warning":
            subject = "Engine Health Warning"
            body = (
                f"Engine: {data.get('engine_id', 'N/A')}\n"
                f"Issue: {data.get('issue', 'N/A')}\n"
                f"Details: {data.get('details', 'N/A')}"
            )
        elif event_type == "llm_blocked":
            subject = "LLM Blocked Trade"
            body = (
                f"Side: {data.get('side', 'N/A')}\n"
                f"Mean Confidence: {data.get('mean_confidence', 'N/A')}%\n"
                f"Threshold: {data.get('threshold', 'N/A')}%"
            )
        elif event_type == "llm_assessment":
            subject = "LLM Assessment"
            approved = "Approved" if data.get("approved") else "Rejected"
            body = (
                f"Result: {approved}\n"
                f"Mean Confidence: {data.get('mean_confidence', 'N/A')}%\n"
                f"Threshold: {data.get('threshold', 'N/A')}%"
            )
        else:
            subject = f"Event: {event_type}"
            body = str(data)

        return subject, body

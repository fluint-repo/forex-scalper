"""Tests for NotificationService — Phase 5B."""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.engine.event_bus import EventBus
from src.notifications.base import NotificationBackend
from src.notifications.discord import DiscordBackend
from src.notifications.service import NotificationService
from src.notifications.telegram import TelegramBackend


class MockBackend(NotificationBackend):
    def __init__(self, name_: str = "mock"):
        self._name = name_
        self.sent: list[tuple[str, str]] = []
        self.should_fail = False

    @property
    def name(self) -> str:
        return self._name

    async def send(self, subject: str, body: str) -> None:
        if self.should_fail:
            raise RuntimeError("mock failure")
        self.sent.append((subject, body))


class TestTelegramBackend:
    @pytest.mark.asyncio
    async def test_telegram_send(self):
        with patch("src.notifications.telegram.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_resp
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            backend = TelegramBackend("fake-token", "12345")
            await backend.send("Test", "Hello")

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "fake-token" in call_args[0][0]
            assert call_args[1]["json"]["chat_id"] == "12345"


class TestDiscordBackend:
    @pytest.mark.asyncio
    async def test_discord_send(self):
        with patch("src.notifications.discord.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_resp
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            backend = DiscordBackend("https://discord.com/webhook/test")
            await backend.send("Test", "Hello")

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://discord.com/webhook/test"


class TestEmailBackend:
    @pytest.mark.asyncio
    async def test_email_send(self):
        with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
            from src.notifications.email import EmailBackend
            backend = EmailBackend("smtp.test.com", 587, "user", "pass", "from@test.com", "to@test.com")
            await backend.send("Test Subject", "Test Body")

            mock_send.assert_called_once()
            msg = mock_send.call_args[0][0]
            assert msg["Subject"] == "[Forex Scalper] Test Subject"
            assert msg["To"] == "to@test.com"


class TestNotificationService:
    @pytest.mark.asyncio
    async def test_service_dispatches_to_backends(self):
        b1 = MockBackend("b1")
        b2 = MockBackend("b2")
        svc = NotificationService([b1, b2])
        await svc._dispatch("Subject", "Body")
        assert len(b1.sent) == 1
        assert len(b2.sent) == 1
        assert b1.sent[0] == ("Subject", "Body")

    @pytest.mark.asyncio
    async def test_service_filters_event_types(self):
        b = MockBackend()
        svc = NotificationService([b], event_types=["order_filled"])
        bus = EventBus()
        svc.connect(bus)

        # This event is subscribed
        subject, body = svc._format_message("order_filled", {"side": "BUY", "price": 1.1})
        await svc._dispatch(subject, body)
        assert len(b.sent) == 1

    @pytest.mark.asyncio
    async def test_service_handles_backend_failure(self):
        b1 = MockBackend("fail")
        b1.should_fail = True
        b2 = MockBackend("ok")
        svc = NotificationService([b1, b2])
        # Should not raise, b2 should still receive
        await svc._dispatch("Test", "Body")
        assert len(b1.sent) == 0
        assert len(b2.sent) == 1

    def test_format_order_filled(self):
        subject, body = NotificationService._format_message(
            "order_filled", {"side": "BUY", "price": 1.1234, "volume": 0.5, "order_id": "P-001"}
        )
        assert "Order Filled" in subject
        assert "BUY" in subject
        assert "1.1234" in body
        assert "P-001" in body

    def test_format_circuit_breaker(self):
        subject, body = NotificationService._format_message(
            "circuit_breaker", {"reason": "daily_loss_limit"}
        )
        assert "CIRCUIT BREAKER" in subject
        assert "daily_loss_limit" in body

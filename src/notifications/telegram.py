"""Telegram notification backend."""

import httpx

from src.notifications.base import NotificationBackend
from src.utils.logger import get_logger

log = get_logger(__name__)


class TelegramBackend(NotificationBackend):
    """Send notifications via Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def name(self) -> str:
        return "telegram"

    async def send(self, subject: str, body: str) -> None:
        text = f"*{subject}*\n{body}"
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                })
                resp.raise_for_status()
        except Exception:
            log.exception("telegram_send_failed")

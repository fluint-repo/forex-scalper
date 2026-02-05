"""Discord webhook notification backend."""

import httpx

from src.notifications.base import NotificationBackend
from src.utils.logger import get_logger

log = get_logger(__name__)


class DiscordBackend(NotificationBackend):
    """Send notifications via Discord webhook."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    @property
    def name(self) -> str:
        return "discord"

    async def send(self, subject: str, body: str) -> None:
        content = f"**{subject}**\n{body}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.webhook_url, json={"content": content})
                resp.raise_for_status()
        except Exception:
            log.exception("discord_send_failed")

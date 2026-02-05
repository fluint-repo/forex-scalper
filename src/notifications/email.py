"""Email notification backend using aiosmtplib."""

from email.message import EmailMessage

from src.notifications.base import NotificationBackend
from src.utils.logger import get_logger

log = get_logger(__name__)


class EmailBackend(NotificationBackend):
    """Send notifications via SMTP email."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        from_addr: str,
        to_addr: str,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_addr = from_addr
        self.to_addr = to_addr

    @property
    def name(self) -> str:
        return "email"

    async def send(self, subject: str, body: str) -> None:
        try:
            import aiosmtplib

            msg = EmailMessage()
            msg["From"] = self.from_addr
            msg["To"] = self.to_addr
            msg["Subject"] = f"[Forex Scalper] {subject}"
            msg.set_content(body)

            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                start_tls=True,
            )
        except Exception:
            log.exception("email_send_failed")

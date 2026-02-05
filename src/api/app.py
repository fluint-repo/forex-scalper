"""FastAPI application factory."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from config.settings import CORS_ORIGINS
from src.api.auth import require_api_key
from src.api.deps import set_notification_service
from src.api.routes import account, candles, notifications, performance, positions, risk, strategy, trades
from src.api.ws import periodic_account_broadcast, router as ws_router


def _build_notification_service():
    """Create NotificationService from settings if backends configured."""
    if not settings.NOTIFY_BACKENDS:
        return None

    from src.notifications.service import NotificationService
    backends = []

    if "telegram" in settings.NOTIFY_BACKENDS and settings.TELEGRAM_BOT_TOKEN:
        from src.notifications.telegram import TelegramBackend
        backends.append(TelegramBackend(settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID))

    if "discord" in settings.NOTIFY_BACKENDS and settings.DISCORD_WEBHOOK_URL:
        from src.notifications.discord import DiscordBackend
        backends.append(DiscordBackend(settings.DISCORD_WEBHOOK_URL))

    if "email" in settings.NOTIFY_BACKENDS and settings.SMTP_HOST:
        from src.notifications.email import EmailBackend
        backends.append(EmailBackend(
            settings.SMTP_HOST, settings.SMTP_PORT,
            settings.SMTP_USER, settings.SMTP_PASSWORD,
            settings.SMTP_FROM, settings.SMTP_TO,
        ))

    if not backends:
        return None

    svc = NotificationService(backends, settings.NOTIFY_EVENTS)
    return svc


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build notification service
    svc = _build_notification_service()
    if svc is not None:
        set_notification_service(svc)

    task = asyncio.create_task(periodic_account_broadcast())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Forex Scalper API", version="0.5.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes (all protected by API key except /health)
_auth = [Depends(require_api_key)]
app.include_router(account.router, dependencies=_auth)
app.include_router(positions.router, dependencies=_auth)
app.include_router(trades.router, dependencies=_auth)
app.include_router(candles.router, dependencies=_auth)
app.include_router(strategy.router, dependencies=_auth)
app.include_router(risk.router, dependencies=_auth)
app.include_router(notifications.router, dependencies=_auth)
app.include_router(performance.router, dependencies=_auth)
app.include_router(ws_router)


@app.get("/health")
def health():
    return {"status": "ok"}

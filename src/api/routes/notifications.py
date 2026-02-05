"""Notification endpoints."""

import asyncio

from fastapi import APIRouter

from src.api.deps import get_notification_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/status")
def notification_status():
    svc = get_notification_service()
    if svc is None:
        return {"configured": False, "backends": []}
    return {
        "configured": True,
        "backends": [b.name for b in svc.backends],
        "event_types": svc.event_types,
    }


@router.post("/test")
async def send_test():
    svc = get_notification_service()
    if svc is None or not svc.backends:
        return {"status": "no_backends_configured"}
    await svc._dispatch("Test Notification", "This is a test from Forex Scalper.")
    return {"status": "sent", "backends": [b.name for b in svc.backends]}

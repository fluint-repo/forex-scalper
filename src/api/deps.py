"""Dependency injection for FastAPI routes."""

from src.api.state import EngineManager

_engine_manager = EngineManager()
_notification_service = None


def get_engine_manager() -> EngineManager:
    return _engine_manager


def get_notification_service():
    return _notification_service


def set_notification_service(svc):
    global _notification_service
    _notification_service = svc

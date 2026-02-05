"""Dependency injection for FastAPI routes."""

from src.api.state import EngineManager

_engine_manager = EngineManager()


def get_engine_manager() -> EngineManager:
    return _engine_manager

"""Abstract notification backend."""

from abc import ABC, abstractmethod


class NotificationBackend(ABC):
    """Base class for notification backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def send(self, subject: str, body: str) -> None:
        """Send a notification. Implementations should not raise on failure."""
        ...

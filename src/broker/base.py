"""Abstract broker interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: OrderSide
    price: float
    volume: float
    success: bool
    message: str = ""


class Broker(ABC):
    @abstractmethod
    def place_order(
        self, symbol: str, side: OrderSide, volume: float, sl: float, tp: float
    ) -> OrderResult:
        ...

    @abstractmethod
    def close_position(self, order_id: str, **kwargs) -> OrderResult:
        ...

    @abstractmethod
    def get_positions(self) -> list[dict]:
        ...

    @abstractmethod
    def get_account_info(self) -> dict:
        ...

    @abstractmethod
    def get_closed_trades(self) -> list[dict]:
        ...

    def update_price(self, symbol: str, bid: float, ask: float) -> None:
        """Update current market price. Override in brokers that need it."""
        pass

    @property
    def server_managed_sl_tp(self) -> bool:
        """Whether the broker manages SL/TP server-side."""
        return False

"""Abstract broker interface — to be implemented in Phase 3."""

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
    def close_position(self, order_id: str) -> OrderResult:
        ...

    @abstractmethod
    def get_positions(self) -> list[dict]:
        ...

    @abstractmethod
    def get_account_info(self) -> dict:
        ...

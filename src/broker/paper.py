"""PaperBroker — simulated order execution for paper trading."""

import threading
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from config.settings import (
    INITIAL_CAPITAL,
    MAX_OPEN_POSITIONS,
    PIP_VALUES,
    RISK_PER_TRADE,
    SLIPPAGE_PIPS,
    SPREAD_PIPS,
)
from src.broker.base import Broker, OrderResult, OrderSide
from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class PaperPosition:
    order_id: str
    symbol: str
    side: OrderSide
    entry_price: float
    volume: float
    sl: float
    tp: float
    entry_time: object


class PaperBroker(Broker):
    """Simulated broker for paper trading. Thread-safe."""

    def __init__(
        self,
        symbol: str = "EURUSD=X",
        capital: float = INITIAL_CAPITAL,
        spread_pips: float = SPREAD_PIPS,
        slippage_pips: float = SLIPPAGE_PIPS,
        risk_per_trade: float = RISK_PER_TRADE,
        max_positions: int = MAX_OPEN_POSITIONS,
    ) -> None:
        self.symbol = symbol
        self._capital = capital
        self._initial_capital = capital
        self._spread_pips = spread_pips
        self._slippage_pips = slippage_pips
        self._risk_per_trade = risk_per_trade
        self._max_positions = max_positions
        self._pip_value = PIP_VALUES.get(symbol, 0.0001)

        self._lock = threading.Lock()
        self._order_counter = 0
        self._positions: dict[str, PaperPosition] = {}
        self._closed_trades: list[dict] = []
        self._current_prices: dict[str, dict] = {}  # symbol -> {bid, ask}

    def update_price(self, symbol: str, bid: float, ask: float) -> None:
        """Update current market price for a symbol."""
        with self._lock:
            self._current_prices[symbol] = {"bid": bid, "ask": ask}

    def place_order(
        self, symbol: str, side: OrderSide, volume: float, sl: float, tp: float
    ) -> OrderResult:
        with self._lock:
            # Check max positions
            if len(self._positions) >= self._max_positions:
                return OrderResult(
                    order_id="",
                    symbol=symbol,
                    side=side,
                    price=0.0,
                    volume=0.0,
                    success=False,
                    message="Max positions reached",
                )

            # Check price availability
            prices = self._current_prices.get(symbol)
            if prices is None:
                return OrderResult(
                    order_id="",
                    symbol=symbol,
                    side=side,
                    price=0.0,
                    volume=0.0,
                    success=False,
                    message="No price available",
                )

            # Fill price with slippage
            slippage = self._slippage_pips * self._pip_value
            if side == OrderSide.BUY:
                fill_price = prices["ask"] + slippage
            else:
                fill_price = prices["bid"] - slippage

            # Risk-based volume sizing if volume=0
            if volume == 0:
                volume = self._calculate_volume(fill_price, sl, side)
                if volume <= 0:
                    return OrderResult(
                        order_id="",
                        symbol=symbol,
                        side=side,
                        price=fill_price,
                        volume=0.0,
                        success=False,
                        message="Risk sizing returned zero volume",
                    )

            # Generate order ID
            self._order_counter += 1
            order_id = f"PAPER-{self._order_counter:06d}"

            pos = PaperPosition(
                order_id=order_id,
                symbol=symbol,
                side=side,
                entry_price=fill_price,
                volume=volume,
                sl=sl,
                tp=tp,
                entry_time=pd.Timestamp.utcnow(),
            )
            self._positions[order_id] = pos

            log.info(
                "order_filled",
                order_id=order_id,
                side=side.value,
                price=round(fill_price, 5),
                volume=round(volume, 6),
                sl=round(sl, 5),
                tp=round(tp, 5),
            )

            return OrderResult(
                order_id=order_id,
                symbol=symbol,
                side=side,
                price=fill_price,
                volume=volume,
                success=True,
                message="Filled",
            )

    def close_position(
        self, order_id: str, exit_price: float | None = None, exit_reason: str = "MANUAL"
    ) -> OrderResult:
        with self._lock:
            pos = self._positions.get(order_id)
            if pos is None:
                return OrderResult(
                    order_id=order_id,
                    symbol="",
                    side=OrderSide.BUY,
                    price=0.0,
                    volume=0.0,
                    success=False,
                    message="Position not found",
                )

            # Determine exit price from market if not specified
            if exit_price is None:
                prices = self._current_prices.get(pos.symbol)
                if prices is None:
                    return OrderResult(
                        order_id=order_id,
                        symbol=pos.symbol,
                        side=pos.side,
                        price=0.0,
                        volume=0.0,
                        success=False,
                        message="No price available for close",
                    )
                if pos.side == OrderSide.BUY:
                    exit_price = prices["bid"]
                else:
                    exit_price = prices["ask"]

            pnl = self._calc_pnl(pos, exit_price)
            self._capital += pnl

            trade = {
                "strategy_name": "",
                "symbol": pos.symbol,
                "timeframe": "",
                "side": pos.side.value,
                "entry_time": pos.entry_time,
                "exit_time": pd.Timestamp.utcnow(),
                "entry_price": pos.entry_price,
                "exit_price": exit_price,
                "volume": pos.volume,
                "pnl": pnl,
                "sl": pos.sl,
                "tp": pos.tp,
                "exit_reason": exit_reason,
            }
            self._closed_trades.append(trade)
            del self._positions[order_id]

            log.info(
                "position_closed",
                order_id=order_id,
                exit_price=round(exit_price, 5),
                pnl=round(pnl, 2),
                reason=exit_reason,
            )

            return OrderResult(
                order_id=order_id,
                symbol=pos.symbol,
                side=pos.side,
                price=exit_price,
                volume=pos.volume,
                success=True,
                message=f"Closed: {exit_reason}",
            )

    def get_positions(self) -> list[dict]:
        with self._lock:
            result = []
            for pos in self._positions.values():
                prices = self._current_prices.get(pos.symbol)
                unrealized = 0.0
                if prices:
                    mark_price = prices["bid"] if pos.side == OrderSide.BUY else prices["ask"]
                    unrealized = self._calc_pnl(pos, mark_price)
                result.append({
                    "order_id": pos.order_id,
                    "symbol": pos.symbol,
                    "side": pos.side.value,
                    "entry_price": pos.entry_price,
                    "volume": pos.volume,
                    "sl": pos.sl,
                    "tp": pos.tp,
                    "entry_time": pos.entry_time,
                    "unrealized_pnl": unrealized,
                })
            return result

    def get_account_info(self) -> dict:
        with self._lock:
            equity = self._equity
            return {
                "balance": self._capital,
                "equity": equity,
                "open_positions": len(self._positions),
                "total_pnl": self._capital - self._initial_capital,
            }

    def get_closed_trades(self) -> list[dict]:
        with self._lock:
            return list(self._closed_trades)

    @property
    def _equity(self) -> float:
        """Mark-to-market equity: capital + sum of unrealized PnL."""
        unrealized = 0.0
        for pos in self._positions.values():
            prices = self._current_prices.get(pos.symbol)
            if prices:
                mark_price = prices["bid"] if pos.side == OrderSide.BUY else prices["ask"]
                unrealized += self._calc_pnl(pos, mark_price)
        return self._capital + unrealized

    def _calc_pnl(self, pos: PaperPosition, exit_price: float) -> float:
        """Calculate PnL — same formula as BacktestEngine."""
        if pos.side == OrderSide.BUY:
            return (exit_price - pos.entry_price) * pos.volume / self._pip_value
        else:
            return (pos.entry_price - exit_price) * pos.volume / self._pip_value

    def _calculate_volume(self, entry_price: float, sl_price: float, side: OrderSide) -> float:
        """Risk-based position sizing — same formula as BacktestEngine."""
        risk_amount = self._equity * self._risk_per_trade
        sl_distance = abs(entry_price - sl_price)
        if sl_distance == 0:
            return 0.0
        volume = risk_amount * self._pip_value / sl_distance
        return max(volume, 0.0)

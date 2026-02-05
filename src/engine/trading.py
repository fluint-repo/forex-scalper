"""TradingEngine — orchestrates feed, candle aggregation, strategy, and broker."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from config.settings import (
    CANDLE_HISTORY_SIZE,
    PIP_VALUES,
    TICK_LOG_INTERVAL,
)
from src.broker.base import Broker, OrderSide
from src.data.feed import DataFeed
from src.data.indicators import add_all_indicators
from src.database.repository import TradeRepository
from src.engine.candle_aggregator import CandleAggregator, TIMEFRAME_SECONDS
from src.engine.event_bus import EventBus
from src.strategy.base import Strategy
from src.utils.logger import get_logger

log = get_logger(__name__)


class TradingEngine:
    """Orchestrates live/paper trading: feed -> aggregation -> strategy -> broker."""

    def __init__(
        self,
        strategy: Strategy,
        feed: DataFeed,
        broker: Broker,
        symbol: str = "EURUSD=X",
        timeframe: str = "1h",
        save_trades: bool = False,
        event_bus: EventBus | None = None,
    ) -> None:
        self.strategy = strategy
        self.feed = feed
        self.broker = broker
        self.symbol = symbol
        self.timeframe = timeframe
        self.save_trades = save_trades
        self.event_bus = event_bus

        self._aggregator = CandleAggregator(timeframe)
        self._running = threading.Event()
        self._stream_thread: threading.Thread | None = None
        self._last_tick_log = 0.0
        self._tick_count = 0

    @property
    def is_running(self) -> bool:
        return self._running.is_set()

    @property
    def candle_history(self) -> pd.DataFrame:
        return self._aggregator.history_df

    def start(self) -> None:
        """Warm up with historical data, then start streaming in a daemon thread."""
        log.info(
            "engine_starting",
            strategy=self.strategy.name,
            symbol=self.symbol,
            timeframe=self.timeframe,
        )

        self._warmup()
        self._running.set()
        self._last_tick_log = time.time()

        self._stream_thread = threading.Thread(
            target=self._run_stream,
            daemon=True,
            name="price-stream",
        )
        self._stream_thread.start()
        log.info("engine_started")
        self._emit("engine_started", {"symbol": self.symbol, "strategy": self.strategy.name})

    def stop(self) -> None:
        """Stop engine: close all positions, persist trades."""
        if not self._running.is_set():
            return

        log.info("engine_stopping")
        self._running.clear()

        # Close all open positions
        positions = self.broker.get_positions()
        for pos in positions:
            self.broker.close_position(
                pos["order_id"], exit_reason="SHUTDOWN"
            )

        if self.save_trades:
            self._persist_trades()

        log.info("engine_stopped")
        self._emit("engine_stopped", {})

    def wait(self) -> None:
        """Block until the engine is stopped."""
        while self._running.is_set():
            time.sleep(0.5)

    def _emit(self, event_type: str, data: Any) -> None:
        """Publish an event to the event bus if present."""
        if self.event_bus is not None:
            self.event_bus.publish(event_type, data)

    def _warmup(self) -> None:
        """Fetch historical candles and seed the aggregator."""
        period_seconds = TIMEFRAME_SECONDS[self.timeframe]
        candles_needed = CANDLE_HISTORY_SIZE
        # Calculate days needed: candles * period / seconds_per_day, with margin
        seconds_needed = candles_needed * period_seconds
        days_needed = max(int(seconds_needed / 86400) + 5, 10)

        end = datetime.now(timezone.utc).replace(tzinfo=None)
        start = end - timedelta(days=days_needed)

        log.info("warmup_fetching", days=days_needed, candles_target=candles_needed)

        df = self.feed.get_historical(
            symbol=self.symbol,
            timeframe=self.timeframe,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
        )

        if df.empty:
            log.warning("warmup_no_data")
            return

        # Keep only the last CANDLE_HISTORY_SIZE rows
        if len(df) > CANDLE_HISTORY_SIZE:
            df = df.tail(CANDLE_HISTORY_SIZE).reset_index(drop=True)

        self._aggregator.seed_history(df)
        log.info("warmup_complete", candles_loaded=len(df))

    def _run_stream(self) -> None:
        """Run the price stream (called in daemon thread)."""
        try:
            self.feed.stream_prices(self.symbol, self._on_tick)
        except Exception:
            log.exception("stream_error")
            self._running.clear()

    def _on_tick(self, tick: dict) -> None:
        """Callback for each tick from the price stream."""
        if not self._running.is_set():
            return

        timestamp = tick["timestamp"]
        bid = tick["bid"]
        ask = tick["ask"]

        # Update broker price
        self.broker.update_price(self.symbol, bid, ask)

        # Check SL/TP on open positions (skip if broker manages SL/TP server-side)
        if not self.broker.server_managed_sl_tp:
            self._check_sl_tp(bid, ask)

        # Aggregate into candle
        completed = self._aggregator.on_tick(timestamp, bid, ask)
        if completed is not None:
            self._on_candle_close(completed)

        self._emit("tick", {"timestamp": str(timestamp), "bid": bid, "ask": ask})

        # Periodic tick log
        self._tick_count += 1
        now = time.time()
        if now - self._last_tick_log >= TICK_LOG_INTERVAL:
            mid = (bid + ask) / 2
            account = self.broker.get_account_info()
            log.info(
                "tick_summary",
                ticks=self._tick_count,
                price=round(mid, 5),
                equity=round(account["equity"], 2),
                open_positions=account["open_positions"],
            )
            self._last_tick_log = now
            self._tick_count = 0

    def _check_sl_tp(self, bid: float, ask: float) -> None:
        """Check SL/TP on all open positions. SL checked before TP (conservative)."""
        positions = self.broker.get_positions()
        for pos in positions:
            order_id = pos["order_id"]
            side = pos["side"]
            sl = pos["sl"]
            tp = pos["tp"]

            closed = False
            if side == "BUY":
                if bid <= sl:
                    self.broker.close_position(order_id, exit_price=sl, exit_reason="SL")
                    closed = True
                elif bid >= tp:
                    self.broker.close_position(order_id, exit_price=tp, exit_reason="TP")
                    closed = True
            else:  # SELL
                if ask >= sl:
                    self.broker.close_position(order_id, exit_price=sl, exit_reason="SL")
                    closed = True
                elif ask <= tp:
                    self.broker.close_position(order_id, exit_price=tp, exit_reason="TP")
                    closed = True

            if closed:
                self._emit("position_closed", {"order_id": order_id})

    def _on_candle_close(self, candle: dict) -> None:
        """Process a completed candle: compute indicators, generate signals, place orders."""
        log.info(
            "candle_closed",
            timestamp=str(candle["timestamp"]),
            open=round(candle["open"], 5),
            high=round(candle["high"], 5),
            low=round(candle["low"], 5),
            close=round(candle["close"], 5),
        )

        self._emit("candle_closed", candle)

        df = self._aggregator.history_df
        if len(df) < 200:
            log.debug("insufficient_history", candles=len(df), required=200)
            return

        # Add indicators
        df = add_all_indicators(df)
        df = df.dropna().reset_index(drop=True)

        if df.empty:
            return

        # Generate signals
        df = self.strategy.generate_signals(df)

        # Check last row only
        last = df.iloc[-1]
        signal = int(last.get("signal", 0))

        if signal == 0:
            return

        sl_price = last.get("sl")
        tp_price = last.get("tp")

        if pd.isna(sl_price) or pd.isna(tp_price):
            return

        side = OrderSide.BUY if signal == 1 else OrderSide.SELL

        log.info(
            "signal_detected",
            side=side.value,
            sl=round(sl_price, 5),
            tp=round(tp_price, 5),
        )

        self._emit("signal", {"side": side.value, "sl": sl_price, "tp": tp_price})

        result = self.broker.place_order(
            symbol=self.symbol,
            side=side,
            volume=0,  # triggers risk-based sizing
            sl=sl_price,
            tp=tp_price,
        )

        if result.success:
            self._emit("order_filled", {
                "order_id": result.order_id,
                "side": side.value,
                "price": result.price,
                "volume": result.volume,
            })
        else:
            log.warning("order_rejected", message=result.message)

    def _persist_trades(self) -> None:
        """Save closed trades to database."""
        trades = self.broker.get_closed_trades()
        if not trades:
            return

        # Fill in strategy/timeframe metadata
        for t in trades:
            t["strategy_name"] = self.strategy.name
            t["timeframe"] = self.timeframe

        df = pd.DataFrame(trades)
        try:
            repo = TradeRepository()
            count = repo.insert_trades(df)
            log.info("trades_persisted", count=count)
        except Exception:
            log.exception("persist_trades_failed")

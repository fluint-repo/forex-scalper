"""Tick-to-candle aggregation with time-aligned boundaries."""

from collections import deque
from dataclasses import dataclass, field

import pandas as pd

from config.settings import CANDLE_HISTORY_SIZE

TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


def _floor_timestamp(ts: pd.Timestamp, seconds: int) -> pd.Timestamp:
    """Floor a timestamp to the nearest candle boundary."""
    epoch = int(ts.timestamp())
    floored = (epoch // seconds) * seconds
    return pd.Timestamp(floored, unit="s")


@dataclass
class CandleBuilder:
    """Accumulates ticks into a single OHLCV candle."""

    timestamp: pd.Timestamp
    open: float = 0.0
    high: float = -float("inf")
    low: float = float("inf")
    close: float = 0.0
    volume: int = 0
    tick_count: int = 0

    def update(self, price: float) -> None:
        if self.tick_count == 0:
            self.open = price
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.tick_count += 1
        self.volume += 1

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class CandleAggregator:
    """Aggregates ticks into time-aligned candles."""

    def __init__(self, timeframe: str) -> None:
        if timeframe not in TIMEFRAME_SECONDS:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        self.timeframe = timeframe
        self._period_seconds = TIMEFRAME_SECONDS[timeframe]
        self._history: deque[dict] = deque(maxlen=CANDLE_HISTORY_SIZE)
        self._current: CandleBuilder | None = None

    def on_tick(self, timestamp: pd.Timestamp, bid: float, ask: float) -> dict | None:
        """Process a tick. Returns completed candle dict when a period boundary is crossed."""
        mid = (bid + ask) / 2
        candle_ts = _floor_timestamp(timestamp, self._period_seconds)

        if self._current is None:
            self._current = CandleBuilder(timestamp=candle_ts)
            self._current.update(mid)
            return None

        if candle_ts > self._current.timestamp:
            # New period — close the current candle and start a new one
            completed = self._current.to_dict()
            self._history.append(completed)
            self._current = CandleBuilder(timestamp=candle_ts)
            self._current.update(mid)
            return completed

        # Same period — update current candle
        self._current.update(mid)
        return None

    def seed_history(self, df: pd.DataFrame) -> None:
        """Pre-load historical candles from a DataFrame."""
        for _, row in df.iterrows():
            self._history.append({
                "timestamp": row["timestamp"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row.get("volume", 0),
            })

    @property
    def history_df(self) -> pd.DataFrame:
        """Return historical candles as a DataFrame."""
        if not self._history:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        return pd.DataFrame(list(self._history))

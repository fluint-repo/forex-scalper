import time
from typing import Callable

import numpy as np
import pandas as pd

from src.data.feed import DataFeed
from src.utils.logger import get_logger

log = get_logger(__name__)

TIMEFRAME_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
}

TIMEFRAME_FREQ = {
    "1m": "min",
    "5m": "5min",
    "15m": "15min",
    "1h": "h",
    "4h": "4h",
    "1d": "D",
}

# Realistic base prices for forex pairs
BASE_PRICES = {
    "EURUSD=X": 1.0850,
    "GBPUSD=X": 1.2650,
    "USDJPY=X": 149.50,
}
DEFAULT_BASE = 1.1000


def _try_yfinance(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
    """Attempt to fetch from yfinance; return empty DataFrame on failure."""
    try:
        import yfinance as yf

        df = yf.download(
            symbol, start=start, end=end, interval=interval,
            progress=False, auto_adjust=True,
        )
        if df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.rename(columns={
            "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume",
        })
        df.index.name = "timestamp"
        df = df[["open", "high", "low", "close", "volume"]].copy()
        if df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)
        return df
    except Exception as e:
        log.debug("yfinance_failed", error=str(e))
        return pd.DataFrame()


def _generate_synthetic(
    symbol: str, start: str, end: str, freq: str
) -> pd.DataFrame:
    """Generate realistic synthetic OHLCV data using geometric Brownian motion."""
    base_price = BASE_PRICES.get(symbol, DEFAULT_BASE)
    rng = np.random.default_rng(seed=hash(symbol) & 0xFFFFFFFF)

    idx = pd.date_range(start=start, end=end, freq=freq)
    # Filter to weekdays for forex (Mon-Fri)
    idx = idx[idx.weekday < 5]

    if len(idx) == 0:
        return pd.DataFrame()

    n = len(idx)
    # GBM parameters scaled by timeframe
    volatility = 0.0008 if base_price < 10 else 0.08
    returns = rng.normal(0, volatility, n)
    close = base_price * np.exp(np.cumsum(returns))

    high_offset = np.abs(rng.normal(0, volatility * 0.5, n))
    low_offset = np.abs(rng.normal(0, volatility * 0.5, n))
    high = close * (1 + high_offset)
    low = close * (1 - low_offset)
    open_ = low + rng.random(n) * (high - low)
    volume = rng.integers(100, 10000, size=n).astype(float)

    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=idx)
    df.index.name = "timestamp"
    return df


class DemoFeed(DataFeed):
    """Data feed for development: tries yfinance, falls back to synthetic data."""

    def get_historical(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        yf_interval = TIMEFRAME_MAP.get(timeframe, timeframe)
        freq = TIMEFRAME_FREQ.get(timeframe, "h")

        log.info(
            "fetching_historical",
            symbol=symbol, timeframe=timeframe, start=start, end=end,
        )

        # Try yfinance first
        df = _try_yfinance(symbol, start, end, yf_interval)
        if not df.empty:
            log.info("fetched_from_yfinance", count=len(df))
        else:
            log.info("yfinance_unavailable_using_synthetic", symbol=symbol)
            df = _generate_synthetic(symbol, start, end, freq)

        if df.empty:
            log.warning("no_data_generated", symbol=symbol)
            return pd.DataFrame()

        log.info("fetched_rows", count=len(df))
        return df.reset_index()

    def stream_prices(self, symbol: str, callback: Callable[[dict], None]) -> None:
        """Simulate a live price stream with synthetic tick data."""
        log.info("starting_demo_stream", symbol=symbol)
        base_price = BASE_PRICES.get(symbol, DEFAULT_BASE)
        rng = np.random.default_rng()
        price = base_price

        while True:
            price *= np.exp(rng.normal(0, 0.0001))
            spread = price * 0.00015
            callback({
                "timestamp": pd.Timestamp.utcnow(),
                "bid": price - spread / 2,
                "ask": price + spread / 2,
            })
            time.sleep(5)

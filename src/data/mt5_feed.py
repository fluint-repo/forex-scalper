"""MT5 data feed — functional on Windows with MetaTrader5 package installed.

This is a skeleton that implements the DataFeed interface.
On Linux, import will fail gracefully; use DemoFeed instead.
"""

from typing import Callable

import pandas as pd

from src.data.feed import DataFeed
from src.utils.logger import get_logger

log = get_logger(__name__)

try:
    import MetaTrader5 as mt5  # type: ignore[import-untyped]

    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    log.info("mt5_not_available", hint="MetaTrader5 package not installed; use DemoFeed")

TIMEFRAME_MAP = {
    "1m": "TIMEFRAME_M1",
    "5m": "TIMEFRAME_M5",
    "15m": "TIMEFRAME_M15",
    "1h": "TIMEFRAME_H1",
    "4h": "TIMEFRAME_H4",
    "1d": "TIMEFRAME_D1",
}


class MT5Feed(DataFeed):
    def __init__(self) -> None:
        if not MT5_AVAILABLE:
            raise RuntimeError("MetaTrader5 package is not installed")
        if not mt5.initialize():
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
        log.info("mt5_initialized")

    def get_historical(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        tf = getattr(mt5, TIMEFRAME_MAP[timeframe])
        rates = mt5.copy_rates_range(
            symbol,
            tf,
            pd.Timestamp(start),
            pd.Timestamp(end),
        )
        if rates is None or len(rates) == 0:
            log.warning("mt5_no_data", symbol=symbol, timeframe=timeframe)
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df["timestamp"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "tick_volume": "volume",
        })
        return df[["timestamp", "open", "high", "low", "close", "volume"]]

    def stream_prices(self, symbol: str, callback: Callable[[dict], None]) -> None:
        raise NotImplementedError("MT5 live streaming not yet implemented")

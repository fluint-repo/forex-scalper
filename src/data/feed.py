from abc import ABC, abstractmethod
from typing import Callable

import pandas as pd


class DataFeed(ABC):
    """Abstract base class for market data feeds."""

    @abstractmethod
    def get_historical(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV candles.

        Returns DataFrame with columns: timestamp, open, high, low, close, volume
        """

    @abstractmethod
    def stream_prices(self, symbol: str, callback: Callable[[dict], None]) -> None:
        """Stream real-time price updates. Calls callback with
        {'timestamp': ..., 'bid': ..., 'ask': ...} dicts.
        """

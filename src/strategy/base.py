"""Strategy abstract base class and configuration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class StrategyConfig:
    name: str
    version: str = "1.0"
    params: dict = field(default_factory=dict)


class Strategy(ABC):
    """Abstract base for all trading strategies.

    Contract:
        - generate_signals() receives a DataFrame with OHLCV + all indicator columns
        - Returns the same DataFrame with added columns: signal (1/-1/0), sl, tp
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate trading signals on a DataFrame with indicators.

        Args:
            df: DataFrame with OHLCV + indicator columns.

        Returns:
            DataFrame with added 'signal' (1=BUY, -1=SELL, 0=none),
            'sl' (stop-loss price), 'tp' (take-profit price) columns.
        """

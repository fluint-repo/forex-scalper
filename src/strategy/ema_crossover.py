"""EMA Crossover strategy with RSI filter."""

import numpy as np
import pandas as pd

from config.settings import (
    EMA_ATR_SL_MULT,
    EMA_ATR_TP_MULT,
    EMA_FAST_PERIOD,
    EMA_RSI_OVERBOUGHT,
    EMA_RSI_OVERSOLD,
    EMA_SLOW_PERIOD,
)
from src.strategy.base import Strategy, StrategyConfig


class EMACrossoverStrategy(Strategy):
    """Trend-following scalper: EMA fast/slow crossover with RSI filter.

    BUY:  EMA fast crosses above EMA slow + RSI < overbought
    SELL: EMA fast crosses below EMA slow + RSI > oversold
    SL/TP: ATR-based multiples from entry price
    """

    def __init__(self, config: StrategyConfig | None = None) -> None:
        if config is None:
            config = StrategyConfig(
                name="ema_crossover",
                params={
                    "fast_period": EMA_FAST_PERIOD,
                    "slow_period": EMA_SLOW_PERIOD,
                    "rsi_oversold": EMA_RSI_OVERSOLD,
                    "rsi_overbought": EMA_RSI_OVERBOUGHT,
                    "atr_sl_mult": EMA_ATR_SL_MULT,
                    "atr_tp_mult": EMA_ATR_TP_MULT,
                },
            )
        super().__init__(config)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        p = self.config.params
        fast_col = f"ema_{p['fast_period']}"
        slow_col = f"ema_{p['slow_period']}"

        for col in [fast_col, slow_col, "rsi", "atr"]:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        ema_fast = df[fast_col]
        ema_slow = df[slow_col]

        # Crossover detection
        cross_above = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
        cross_below = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))

        # RSI filter
        rsi_ok_buy = df["rsi"] < p["rsi_overbought"]
        rsi_ok_sell = df["rsi"] > p["rsi_oversold"]

        df["signal"] = 0
        df.loc[cross_above & rsi_ok_buy, "signal"] = 1
        df.loc[cross_below & rsi_ok_sell, "signal"] = -1

        # SL/TP based on ATR
        atr_sl = df["atr"] * p["atr_sl_mult"]
        atr_tp = df["atr"] * p["atr_tp_mult"]

        df["sl"] = np.nan
        df["tp"] = np.nan

        buy_mask = df["signal"] == 1
        sell_mask = df["signal"] == -1

        df.loc[buy_mask, "sl"] = df.loc[buy_mask, "close"] - atr_sl[buy_mask]
        df.loc[buy_mask, "tp"] = df.loc[buy_mask, "close"] + atr_tp[buy_mask]
        df.loc[sell_mask, "sl"] = df.loc[sell_mask, "close"] + atr_sl[sell_mask]
        df.loc[sell_mask, "tp"] = df.loc[sell_mask, "close"] - atr_tp[sell_mask]

        return df

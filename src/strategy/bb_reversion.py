"""Bollinger Band mean-reversion scalper."""

import numpy as np
import pandas as pd

from config.settings import BB_ATR_SL_MULT, BB_RSI_OVERBOUGHT, BB_RSI_OVERSOLD
from src.strategy.base import Strategy, StrategyConfig


class BBReversionStrategy(Strategy):
    """Mean-reversion scalper using Bollinger Bands + RSI filter.

    BUY:  close < bb_lower + RSI < oversold
    SELL: close > bb_upper + RSI > overbought
    SL: ATR-based beyond band
    TP: bb_middle (mean-reversion target)
    """

    def __init__(self, config: StrategyConfig | None = None) -> None:
        if config is None:
            config = StrategyConfig(
                name="bb_reversion",
                params={
                    "rsi_oversold": BB_RSI_OVERSOLD,
                    "rsi_overbought": BB_RSI_OVERBOUGHT,
                    "atr_sl_mult": BB_ATR_SL_MULT,
                },
            )
        super().__init__(config)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        p = self.config.params

        for col in ["bb_lower", "bb_upper", "bb_middle", "rsi", "atr"]:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        df["signal"] = 0
        df["sl"] = np.nan
        df["tp"] = np.nan

        buy_mask = (df["close"] < df["bb_lower"]) & (df["rsi"] < p["rsi_oversold"])
        sell_mask = (df["close"] > df["bb_upper"]) & (df["rsi"] > p["rsi_overbought"])

        atr_sl = df["atr"] * p["atr_sl_mult"]

        df.loc[buy_mask, "signal"] = 1
        df.loc[buy_mask, "sl"] = df.loc[buy_mask, "close"] - atr_sl[buy_mask]
        df.loc[buy_mask, "tp"] = df.loc[buy_mask, "bb_middle"]

        df.loc[sell_mask, "signal"] = -1
        df.loc[sell_mask, "sl"] = df.loc[sell_mask, "close"] + atr_sl[sell_mask]
        df.loc[sell_mask, "tp"] = df.loc[sell_mask, "bb_middle"]

        return df

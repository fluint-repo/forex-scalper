#!/usr/bin/env python3
"""Entry point — fetches historical data, computes indicators, stores results."""

import sys

sys.path.insert(0, ".")

from datetime import datetime, timedelta, timezone

from config.settings import (
    ATR_PERIOD,
    BB_PERIOD,
    BB_STD,
    DATA_FEED,
    DEFAULT_HISTORY_DAYS,
    EMA_PERIODS,
    MACD_FAST,
    MACD_SIGNAL,
    MACD_SLOW,
    RSI_PERIOD,
    SYMBOLS,
)
from src.data.demo_feed import DemoFeed
from src.data.indicators import add_all_indicators
from src.database.repository import CandleRepository
from src.utils.logger import get_logger, setup_logging


def create_feed():
    if DATA_FEED == "mt5":
        from src.data.mt5_feed import MT5Feed
        return MT5Feed()
    return DemoFeed()


def main() -> None:
    setup_logging()
    log = get_logger("main")

    log.info("starting_forex_scalper", feed_type=DATA_FEED)

    feed = create_feed()
    repo = CandleRepository()

    end = datetime.now(timezone.utc).replace(tzinfo=None)
    start = end - timedelta(days=DEFAULT_HISTORY_DAYS)

    for symbol in SYMBOLS:
        log.info("processing_symbol", symbol=symbol)

        df = feed.get_historical(
            symbol=symbol,
            timeframe="1h",
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
        )

        if df.empty:
            log.warning("no_data", symbol=symbol)
            continue

        repo.upsert_candles(df, symbol, "1h")

        df_indicators = add_all_indicators(
            df,
            rsi_period=RSI_PERIOD,
            macd_fast=MACD_FAST,
            macd_slow=MACD_SLOW,
            macd_signal=MACD_SIGNAL,
            bb_period=BB_PERIOD,
            bb_std=BB_STD,
            ema_periods=EMA_PERIODS,
            atr_period=ATR_PERIOD,
        )

        log.info(
            "indicators_computed",
            symbol=symbol,
            rows=len(df_indicators),
            columns=list(df_indicators.columns),
        )

    log.info("forex_scalper_phase1_complete")


if __name__ == "__main__":
    main()

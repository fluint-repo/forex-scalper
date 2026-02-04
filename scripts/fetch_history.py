#!/usr/bin/env python3
"""Backfill historical candle data into TimescaleDB."""

import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app" if sys.argv[0].startswith("/app") else ".")

from config.settings import DEFAULT_HISTORY_DAYS, SYMBOLS, TIMEFRAMES
from src.data.demo_feed import DemoFeed
from src.database.repository import CandleRepository
from src.utils.logger import get_logger, setup_logging

setup_logging()
log = get_logger(__name__)


def main() -> None:
    feed = DemoFeed()
    repo = CandleRepository()

    end = datetime.now(timezone.utc).replace(tzinfo=None)

    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            start = end - timedelta(days=DEFAULT_HISTORY_DAYS)

            log.info(
                "backfilling",
                symbol=symbol,
                timeframe=tf,
                start=start.isoformat(),
                end=end.isoformat(),
            )
            try:
                df = feed.get_historical(
                    symbol=symbol,
                    timeframe=tf,
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                )
                if not df.empty:
                    repo.upsert_candles(df, symbol, tf)
                else:
                    log.warning("empty_result", symbol=symbol, timeframe=tf)
            except Exception:
                log.exception("backfill_error", symbol=symbol, timeframe=tf)

    log.info("backfill_complete")


if __name__ == "__main__":
    main()

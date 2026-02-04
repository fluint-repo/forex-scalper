#!/usr/bin/env python3
"""CLI runner: load data -> strategy -> backtest -> report."""

import argparse
import sys

sys.path.insert(0, "/app" if sys.argv[0].startswith("/app") else ".")

from datetime import datetime, timedelta, timezone

from config.settings import DEFAULT_HISTORY_DAYS, INITIAL_CAPITAL
from src.backtest.engine import BacktestConfig, BacktestEngine
from src.backtest.metrics import calculate_metrics, format_metrics
from src.data.demo_feed import DemoFeed
from src.data.indicators import add_all_indicators
from src.database.repository import CandleRepository, TradeRepository
from src.strategy.bb_reversion import BBReversionStrategy
from src.strategy.ema_crossover import EMACrossoverStrategy
from src.utils.logger import get_logger, setup_logging

STRATEGIES = {
    "ema_crossover": EMACrossoverStrategy,
    "bb_reversion": BBReversionStrategy,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a backtest on forex data")
    parser.add_argument(
        "--strategy",
        choices=list(STRATEGIES.keys()),
        default="ema_crossover",
        help="Strategy to backtest",
    )
    parser.add_argument("--symbol", default="EURUSD=X", help="Symbol to backtest")
    parser.add_argument("--timeframe", default="1h", help="Timeframe for candles")
    parser.add_argument("--days", type=int, default=DEFAULT_HISTORY_DAYS, help="Days of history")
    parser.add_argument("--capital", type=float, default=INITIAL_CAPITAL, help="Initial capital")
    parser.add_argument("--from-db", action="store_true", help="Load candles from database")
    parser.add_argument("--save-trades", action="store_true", help="Save trades to database")
    return parser.parse_args()


def main() -> None:
    setup_logging()
    log = get_logger("backtest_runner")
    args = parse_args()

    log.info(
        "backtest_start",
        strategy=args.strategy,
        symbol=args.symbol,
        timeframe=args.timeframe,
        days=args.days,
    )

    # Load data
    if args.from_db:
        repo = CandleRepository()
        end = datetime.now(timezone.utc).replace(tzinfo=None)
        start = end - timedelta(days=args.days)
        df = repo.get_candles(args.symbol, args.timeframe, start=start, end=end, limit=100000)
        if df.empty:
            log.error("no_data_in_db", symbol=args.symbol, timeframe=args.timeframe)
            sys.exit(1)
    else:
        feed = DemoFeed()
        end = datetime.now(timezone.utc).replace(tzinfo=None)
        start = end - timedelta(days=args.days)
        df = feed.get_historical(
            symbol=args.symbol,
            timeframe=args.timeframe,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
        )
        if df.empty:
            log.error("no_data_generated", symbol=args.symbol)
            sys.exit(1)

    log.info("data_loaded", rows=len(df))

    # Add indicators
    df = add_all_indicators(df)
    df = df.dropna().reset_index(drop=True)
    log.info("indicators_added", rows=len(df))

    # Generate signals
    strategy = STRATEGIES[args.strategy]()
    df = strategy.generate_signals(df)

    signal_count = (df["signal"] != 0).sum()
    log.info("signals_generated", total_signals=int(signal_count))

    # Run backtest
    bt_config = BacktestConfig(capital=args.capital)
    engine = BacktestEngine(
        config=bt_config,
        symbol=args.symbol,
        timeframe=args.timeframe,
        strategy_name=strategy.name,
    )
    result = engine.run(df)

    # Calculate and print metrics
    metrics = calculate_metrics(result.trades, result.equity_curve, result.initial_capital)
    report = format_metrics(metrics)
    print(report)

    # Optionally save trades to DB
    if args.save_trades and not result.trades.empty:
        trade_repo = TradeRepository()
        count = trade_repo.insert_trades(result.trades)
        log.info("trades_saved", count=count)

    log.info("backtest_complete")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""CLI runner for live/paper trading."""

import argparse
import signal
import sys

sys.path.insert(0, "/app" if sys.argv[0].startswith("/app") else ".")

from config.settings import INITIAL_CAPITAL
from src.engine.trading import TradingEngine
from src.strategy.bb_reversion import BBReversionStrategy
from src.strategy.ema_crossover import EMACrossoverStrategy
from src.utils.logger import get_logger, setup_logging

STRATEGIES = {
    "ema_crossover": EMACrossoverStrategy,
    "bb_reversion": BBReversionStrategy,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live/paper trading")
    parser.add_argument(
        "--strategy",
        choices=list(STRATEGIES.keys()),
        default="ema_crossover",
        help="Strategy to run",
    )
    parser.add_argument("--symbol", default="EURUSD=X", help="Symbol to trade")
    parser.add_argument("--timeframe", default="1h", help="Candle timeframe")
    parser.add_argument("--capital", type=float, default=INITIAL_CAPITAL, help="Initial capital")
    parser.add_argument("--save-trades", action="store_true", help="Save trades to database on shutdown")
    parser.add_argument(
        "--broker",
        choices=["paper", "oanda"],
        default="paper",
        help="Broker to use (paper or oanda)",
    )
    return parser.parse_args()


def _create_broker_and_feed(args):
    if args.broker == "oanda":
        from src.broker.oanda import OandaBroker
        from src.data.oanda_feed import OandaFeed
        return OandaBroker(), OandaFeed()
    else:
        from src.broker.paper import PaperBroker
        from src.data.demo_feed import DemoFeed
        return PaperBroker(symbol=args.symbol, capital=args.capital), DemoFeed()


def main() -> None:
    setup_logging()
    log = get_logger("live_runner")
    args = parse_args()

    log.info(
        "trading_start",
        broker=args.broker,
        strategy=args.strategy,
        symbol=args.symbol,
        timeframe=args.timeframe,
        capital=args.capital,
    )

    strategy = STRATEGIES[args.strategy]()
    broker, feed = _create_broker_and_feed(args)

    engine = TradingEngine(
        strategy=strategy,
        feed=feed,
        broker=broker,
        symbol=args.symbol,
        timeframe=args.timeframe,
        save_trades=args.save_trades,
    )

    # Signal handlers for graceful shutdown
    def handle_signal(signum, frame):
        log.info("shutdown_signal_received", signal=signum)
        engine.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Start and wait
    engine.start()
    engine.wait()

    # Session summary
    account = broker.get_account_info()
    closed = broker.get_closed_trades()
    print("\n" + "=" * 60)
    print("SESSION SUMMARY")
    print("=" * 60)
    print(f"  Broker:          {args.broker}")
    print(f"  Strategy:        {strategy.name}")
    print(f"  Symbol:          {args.symbol}")
    print(f"  Timeframe:       {args.timeframe}")
    print(f"  Initial Capital: ${args.capital:,.2f}")
    print(f"  Final Capital:   ${account['balance']:,.2f}")
    print(f"  Total PnL:       ${account['total_pnl']:,.2f}")
    print(f"  Trades Closed:   {len(closed)}")
    if args.save_trades:
        print(f"  Trades Saved:    Yes")
    print("=" * 60)


if __name__ == "__main__":
    main()

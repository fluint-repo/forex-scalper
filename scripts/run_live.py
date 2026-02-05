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

    # Build LLM assessor if enabled
    llm_assessor = None
    from config import settings as _s
    if _s.LLM_ENABLED:
        from src.llm.assessor import LLMAssessor
        providers = []
        if _s.ANTHROPIC_API_KEY:
            from src.llm.anthropic import AnthropicProvider
            providers.append(AnthropicProvider(_s.ANTHROPIC_API_KEY, _s.LLM_ANTHROPIC_MODEL))
        if _s.OPENAI_API_KEY:
            from src.llm.openai import OpenAIProvider
            providers.append(OpenAIProvider(_s.OPENAI_API_KEY, _s.LLM_OPENAI_MODEL))
        if _s.XAI_API_KEY:
            from src.llm.grok import GrokProvider
            providers.append(GrokProvider(_s.XAI_API_KEY, _s.LLM_GROK_MODEL))
        llm_assessor = LLMAssessor(providers, _s.LLM_CONFIDENCE_THRESHOLD, _s.LLM_TIMEOUT)
        log.info("llm_assessor_created", providers=[p.name for p in providers])

    engine = TradingEngine(
        strategy=strategy,
        feed=feed,
        broker=broker,
        symbol=args.symbol,
        timeframe=args.timeframe,
        save_trades=args.save_trades,
        llm_assessor=llm_assessor,
    )

    # Signal handlers for graceful shutdown
    def handle_signal(signum, frame):
        log.info("shutdown_signal_received", signal=signum)
        engine.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Start and wait (blocks until engine stops or signal received)
    engine.start()
    engine.wait(timeout=None)

    # Join stream thread with timeout
    if engine._stream_thread is not None:
        engine._stream_thread.join(timeout=30)
        if engine._stream_thread.is_alive():
            log.warning("stream_thread_did_not_stop")

    # Session summary
    try:
        account = broker.get_account_info()
        closed = broker.get_closed_trades()
    except Exception:
        log.exception("session_summary_failed")
        return

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

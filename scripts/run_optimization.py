#!/usr/bin/env python3
"""CLI runner for strategy optimization."""

import argparse
import json
import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from config.settings import OPTIMIZATION_MAX_WORKERS, WALK_FORWARD_SPLITS, WALK_FORWARD_TRAIN_PCT, MONTE_CARLO_SIMULATIONS
from src.backtest.engine import BacktestConfig
from src.data.demo_feed import DemoFeed
from src.data.indicators import add_all_indicators
from src.strategy.ema_crossover import EMACrossoverStrategy
from src.strategy.bb_reversion import BBReversionStrategy

STRATEGIES = {
    "ema_crossover": EMACrossoverStrategy,
    "bb_reversion": BBReversionStrategy,
}

DEFAULT_PARAM_GRIDS = {
    "ema_crossover": {
        "fast_period": [5, 9, 12],
        "slow_period": [15, 21, 30],
        "rsi_overbought": [65, 70, 75],
        "rsi_oversold": [25, 30, 35],
        "atr_sl_mult": [1.0, 1.5, 2.0],
        "atr_tp_mult": [1.5, 2.0, 3.0],
    },
    "bb_reversion": {
        "rsi_overbought": [65, 70, 75],
        "rsi_oversold": [25, 30, 35],
        "atr_sl_mult": [1.0, 1.5, 2.0],
    },
}


def main():
    parser = argparse.ArgumentParser(description="Strategy optimization runner")
    parser.add_argument("--strategy", default="ema_crossover", choices=list(STRATEGIES.keys()))
    parser.add_argument("--symbol", default="EURUSD=X")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--method", default="grid", choices=["grid", "walk_forward", "monte_carlo"])
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--save-json", default=None, help="Save results to JSON file")
    args = parser.parse_args()

    # Load data
    print(f"Loading data for {args.symbol} {args.timeframe}...")
    feed = DemoFeed()
    end = args.end_date or datetime.utcnow().strftime("%Y-%m-%d")
    start = args.start_date or (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
    df = feed.get_historical(args.symbol, args.timeframe, start, end)

    if df.empty:
        print("No data available!")
        sys.exit(1)

    print(f"Loaded {len(df)} candles from {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")

    strategy_class = STRATEGIES[args.strategy]

    if args.method == "grid":
        from src.optimization.grid_search import GridSearch

        param_grid = DEFAULT_PARAM_GRIDS.get(args.strategy, {})
        gs = GridSearch(strategy_class, param_grid, symbol=args.symbol,
                        timeframe=args.timeframe, max_workers=OPTIMIZATION_MAX_WORKERS)
        results = gs.run(df)

        print(f"\n{'='*70}")
        print(f"  GRID SEARCH RESULTS — Top 10")
        print(f"{'='*70}")
        print(f"{'Rank':<6}{'Sharpe':>8}{'Return%':>10}{'MaxDD':>8}{'WinRate':>9}{'Trades':>8}  Params")
        print(f"{'-'*70}")
        for i, r in enumerate(results[:10], 1):
            print(f"{i:<6}{r.sharpe:>8.2f}{r.total_return:>9.1f}%{r.max_drawdown:>8.2%}{r.win_rate:>8.1%}{r.trade_count:>8}  {r.params}")

        if args.save_json:
            with open(args.save_json, "w") as f:
                json.dump([{"params": r.params, "sharpe": r.sharpe, "return": r.total_return,
                           "max_drawdown": r.max_drawdown, "win_rate": r.win_rate,
                           "trades": r.trade_count} for r in results], f, indent=2)
            print(f"\nResults saved to {args.save_json}")

    elif args.method == "walk_forward":
        from src.optimization.walk_forward import WalkForward

        param_grid = DEFAULT_PARAM_GRIDS.get(args.strategy, {})
        wf = WalkForward(strategy_class, param_grid,
                         n_splits=WALK_FORWARD_SPLITS,
                         train_pct=WALK_FORWARD_TRAIN_PCT,
                         symbol=args.symbol, timeframe=args.timeframe,
                         max_workers=1)
        result = wf.run(df)

        print(f"\n{'='*70}")
        print(f"  WALK-FORWARD ANALYSIS")
        print(f"{'='*70}")
        for s in result.splits:
            print(f"  Split {s.split_index}: IS Sharpe={s.in_sample_sharpe:.2f}  "
                  f"OOS Sharpe={s.out_of_sample_sharpe:.2f}  "
                  f"OOS Return={s.out_of_sample_return:.1f}%  "
                  f"Trades={s.out_of_sample_trades}")
            print(f"    Best params: {s.best_params}")
        print(f"{'-'*70}")
        print(f"  Avg IS Sharpe:     {result.avg_is_sharpe:.2f}")
        print(f"  Avg OOS Sharpe:    {result.avg_oos_sharpe:.2f}")
        print(f"  Overfitting Ratio: {result.overfitting_ratio:.2f}")
        print(f"  Total OOS Return:  {result.total_oos_return:.1f}%")
        print(f"{'='*70}")

    elif args.method == "monte_carlo":
        from src.optimization.monte_carlo import MonteCarlo

        # First run a backtest to get trade PnLs
        df = add_all_indicators(df)
        df = df.dropna().reset_index(drop=True)
        strategy = strategy_class()
        df = strategy.generate_signals(df)

        from src.backtest.engine import BacktestEngine
        engine = BacktestEngine(symbol=args.symbol, timeframe=args.timeframe,
                                strategy_name=args.strategy)
        result = engine.run(df)

        if result.trades.empty:
            print("No trades to simulate!")
            sys.exit(1)

        pnls = result.trades["pnl"].tolist()
        mc = MonteCarlo(pnls, n_simulations=MONTE_CARLO_SIMULATIONS)
        mc_result = mc.run()

        print(f"\n{'='*70}")
        print(f"  MONTE CARLO SIMULATION ({mc_result.n_simulations} runs, {mc_result.n_trades} trades)")
        print(f"{'='*70}")
        print(f"  Return Percentiles:")
        for k, v in mc_result.return_percentiles.items():
            print(f"    {k}: {v:.1f}%")
        print(f"  Max Drawdown Percentiles:")
        for k, v in mc_result.max_drawdown_percentiles.items():
            print(f"    {k}: {v:.2%}")
        print(f"  Sharpe Percentiles:")
        for k, v in mc_result.sharpe_percentiles.items():
            print(f"    {k}: {v:.2f}")
        print(f"  Probability of Ruin (>{mc.ruin_threshold:.0%} DD): {mc_result.probability_of_ruin:.1%}")
        print(f"{'='*70}")


if __name__ == "__main__":
    main()

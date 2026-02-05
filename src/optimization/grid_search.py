"""Grid search optimization over strategy parameters."""

import itertools
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.backtest.metrics import calculate_metrics
from src.data.indicators import add_all_indicators
from src.strategy.base import Strategy, StrategyConfig
from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class GridResult:
    params: dict
    total_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    trade_count: int


def _run_single_backtest(args: tuple) -> dict:
    """Run a single backtest for one parameter combination (picklable for multiprocessing)."""
    strategy_class_name, strategy_module, params, df_dict, backtest_config_dict, symbol, timeframe = args

    # Import strategy class dynamically
    import importlib
    module = importlib.import_module(strategy_module)
    strategy_class = getattr(module, strategy_class_name)

    config = StrategyConfig(name=strategy_class_name, params=params)
    strategy = strategy_class(config)

    df = pd.DataFrame(df_dict)
    df = add_all_indicators(df)
    df = df.dropna().reset_index(drop=True)

    if df.empty:
        return {"params": params, "total_return": 0, "sharpe": 0, "max_drawdown": 0, "win_rate": 0, "trade_count": 0}

    df = strategy.generate_signals(df)

    bt_config = BacktestConfig(**backtest_config_dict)
    engine = BacktestEngine(config=bt_config, symbol=symbol, timeframe=timeframe, strategy_name=strategy_class_name)
    result = engine.run(df)

    metrics = calculate_metrics(result.trades, result.equity_curve, result.initial_capital)

    return {
        "params": params,
        "total_return": metrics.return_pct,
        "sharpe": metrics.sharpe_ratio,
        "max_drawdown": metrics.max_drawdown,
        "win_rate": metrics.win_rate,
        "trade_count": metrics.total_trades,
    }


class GridSearch:
    """Grid search over strategy parameter combinations."""

    def __init__(
        self,
        strategy_class: type[Strategy],
        param_grid: dict[str, list],
        backtest_config: BacktestConfig | None = None,
        symbol: str = "EURUSD=X",
        timeframe: str = "1h",
        max_workers: int = 4,
    ) -> None:
        self.strategy_class = strategy_class
        self.param_grid = param_grid
        self.backtest_config = backtest_config or BacktestConfig()
        self.symbol = symbol
        self.timeframe = timeframe
        self.max_workers = max_workers

    def run(self, df: pd.DataFrame) -> list[GridResult]:
        """Run grid search over all parameter combinations."""
        # Generate all parameter combinations
        keys = list(self.param_grid.keys())
        values = list(self.param_grid.values())
        combos = [dict(zip(keys, v)) for v in itertools.product(*values)]

        log.info("grid_search_starting", combinations=len(combos))

        # Get strategy class info for serialization
        strategy_module = self.strategy_class.__module__
        strategy_class_name = self.strategy_class.__name__

        # Convert config to dict for pickling
        bt_config_dict = {
            "capital": self.backtest_config.capital,
            "spread_pips": self.backtest_config.spread_pips,
            "slippage_pips": self.backtest_config.slippage_pips,
            "risk_per_trade": self.backtest_config.risk_per_trade,
            "max_positions": self.backtest_config.max_positions,
            "use_risk_sizing": self.backtest_config.use_risk_sizing,
        }

        # Convert df to dict for pickling
        df_dict = df.to_dict(orient="list")

        results = []
        # Use sequential for small grids, parallel for large
        if len(combos) <= 4 or self.max_workers <= 1:
            for combo in combos:
                args = (strategy_class_name, strategy_module, combo,
                        df_dict, bt_config_dict, self.symbol, self.timeframe)
                r = _run_single_backtest(args)
                results.append(r)
        else:
            args_list = [
                (strategy_class_name, strategy_module, combo,
                 df_dict, bt_config_dict, self.symbol, self.timeframe)
                for combo in combos
            ]
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                results = list(executor.map(_run_single_backtest, args_list))

        # Convert to GridResult and sort by Sharpe
        grid_results = [
            GridResult(
                params=r["params"],
                total_return=r["total_return"],
                sharpe=r["sharpe"],
                max_drawdown=r["max_drawdown"],
                win_rate=r["win_rate"],
                trade_count=r["trade_count"],
            )
            for r in results
        ]
        grid_results.sort(key=lambda x: x.sharpe, reverse=True)

        log.info("grid_search_complete", best_sharpe=grid_results[0].sharpe if grid_results else 0)
        return grid_results

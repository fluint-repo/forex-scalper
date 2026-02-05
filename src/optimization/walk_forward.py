"""Walk-forward analysis with train/test splits."""

from dataclasses import dataclass, field

import pandas as pd

from src.backtest.engine import BacktestConfig
from src.optimization.grid_search import GridSearch, GridResult
from src.strategy.base import Strategy
from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class SplitResult:
    split_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    best_params: dict
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    out_of_sample_return: float
    out_of_sample_trades: int


@dataclass
class WalkForwardResult:
    splits: list[SplitResult]
    avg_oos_sharpe: float
    avg_is_sharpe: float
    overfitting_ratio: float  # IS Sharpe / OOS Sharpe
    total_oos_return: float


class WalkForward:
    """Walk-forward optimization with rolling train/test splits."""

    def __init__(
        self,
        strategy_class: type[Strategy],
        param_grid: dict[str, list],
        n_splits: int = 5,
        train_pct: float = 0.7,
        backtest_config: BacktestConfig | None = None,
        symbol: str = "EURUSD=X",
        timeframe: str = "1h",
        max_workers: int = 1,
    ) -> None:
        self.strategy_class = strategy_class
        self.param_grid = param_grid
        self.n_splits = n_splits
        self.train_pct = train_pct
        self.backtest_config = backtest_config or BacktestConfig()
        self.symbol = symbol
        self.timeframe = timeframe
        self.max_workers = max_workers

    def run(self, df: pd.DataFrame) -> WalkForwardResult:
        """Run walk-forward analysis."""
        n = len(df)
        window_size = n // self.n_splits
        train_size = int(window_size * self.train_pct)
        test_size = window_size - train_size

        splits: list[SplitResult] = []

        for i in range(self.n_splits):
            start = i * window_size
            train_end = start + train_size
            test_end = min(start + window_size, n)

            if train_end >= n or test_end > n:
                break

            train_df = df.iloc[start:train_end].reset_index(drop=True)
            test_df = df.iloc[train_end:test_end].reset_index(drop=True)

            if len(train_df) < 50 or len(test_df) < 10:
                continue

            log.info("walk_forward_split", split=i, train_rows=len(train_df), test_rows=len(test_df))

            # Grid search on train set
            gs = GridSearch(
                self.strategy_class, self.param_grid,
                self.backtest_config, self.symbol, self.timeframe,
                max_workers=self.max_workers,
            )
            train_results = gs.run(train_df)

            if not train_results:
                continue

            best = train_results[0]

            # Evaluate best params on test set
            gs_test = GridSearch(
                self.strategy_class, {k: [v] for k, v in best.params.items()},
                self.backtest_config, self.symbol, self.timeframe,
                max_workers=1,
            )
            test_results = gs_test.run(test_df)
            oos = test_results[0] if test_results else GridResult({}, 0, 0, 0, 0, 0)

            train_ts = train_df["timestamp"]
            test_ts = test_df["timestamp"]

            splits.append(SplitResult(
                split_index=i,
                train_start=str(train_ts.iloc[0]),
                train_end=str(train_ts.iloc[-1]),
                test_start=str(test_ts.iloc[0]),
                test_end=str(test_ts.iloc[-1]),
                best_params=best.params,
                in_sample_sharpe=best.sharpe,
                out_of_sample_sharpe=oos.sharpe,
                out_of_sample_return=oos.total_return,
                out_of_sample_trades=oos.trade_count,
            ))

        # Aggregate
        avg_is = sum(s.in_sample_sharpe for s in splits) / len(splits) if splits else 0
        avg_oos = sum(s.out_of_sample_sharpe for s in splits) / len(splits) if splits else 0
        overfitting = avg_is / avg_oos if avg_oos != 0 else float("inf")
        total_oos_return = sum(s.out_of_sample_return for s in splits)

        return WalkForwardResult(
            splits=splits,
            avg_oos_sharpe=avg_oos,
            avg_is_sharpe=avg_is,
            overfitting_ratio=overfitting,
            total_oos_return=total_oos_return,
        )

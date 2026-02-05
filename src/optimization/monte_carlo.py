"""Monte Carlo simulation for confidence intervals on trading performance."""

from dataclasses import dataclass

import numpy as np


@dataclass
class MonteCarloResult:
    n_simulations: int
    n_trades: int
    # Percentile confidence intervals (5th, 25th, 50th, 75th, 95th)
    return_percentiles: dict[str, float]
    max_drawdown_percentiles: dict[str, float]
    sharpe_percentiles: dict[str, float]
    probability_of_ruin: float  # P(max_drawdown > ruin_threshold)


class MonteCarlo:
    """Bootstrap resampling of trade returns for confidence intervals."""

    def __init__(
        self,
        trade_pnls: list[float],
        n_simulations: int = 1000,
        initial_capital: float = 10000,
        ruin_threshold: float = 0.5,  # 50% drawdown = ruin
    ) -> None:
        self.trade_pnls = np.array(trade_pnls)
        self.n_simulations = n_simulations
        self.initial_capital = initial_capital
        self.ruin_threshold = ruin_threshold

    def run(self) -> MonteCarloResult:
        """Run Monte Carlo simulation via bootstrap resampling."""
        n_trades = len(self.trade_pnls)

        if n_trades < 2:
            return MonteCarloResult(
                n_simulations=self.n_simulations,
                n_trades=n_trades,
                return_percentiles={"p5": 0, "p25": 0, "p50": 0, "p75": 0, "p95": 0},
                max_drawdown_percentiles={"p5": 0, "p25": 0, "p50": 0, "p75": 0, "p95": 0},
                sharpe_percentiles={"p5": 0, "p25": 0, "p50": 0, "p75": 0, "p95": 0},
                probability_of_ruin=0.0,
            )

        returns = []
        max_drawdowns = []
        sharpes = []
        ruin_count = 0

        for _ in range(self.n_simulations):
            # Bootstrap: resample trades with replacement
            indices = np.random.randint(0, n_trades, size=n_trades)
            sampled = self.trade_pnls[indices]

            # Build equity curve
            equity = np.cumsum(sampled) + self.initial_capital

            # Total return
            total_return = (equity[-1] - self.initial_capital) / self.initial_capital * 100
            returns.append(total_return)

            # Max drawdown
            running_max = np.maximum.accumulate(equity)
            drawdown = (equity - running_max) / running_max
            max_dd = abs(drawdown.min())
            max_drawdowns.append(max_dd)

            # Sharpe ratio
            if sampled.std() > 0:
                sharpe = (sampled.mean() / sampled.std()) * np.sqrt(252)
            else:
                sharpe = 0.0
            sharpes.append(sharpe)

            # Ruin check
            if max_dd >= self.ruin_threshold:
                ruin_count += 1

        returns = np.array(returns)
        max_drawdowns = np.array(max_drawdowns)
        sharpes = np.array(sharpes)

        percentiles = [5, 25, 50, 75, 95]
        pct_keys = ["p5", "p25", "p50", "p75", "p95"]

        return MonteCarloResult(
            n_simulations=self.n_simulations,
            n_trades=n_trades,
            return_percentiles=dict(zip(pct_keys, [round(float(np.percentile(returns, p)), 2) for p in percentiles])),
            max_drawdown_percentiles=dict(zip(pct_keys, [round(float(np.percentile(max_drawdowns, p)), 4) for p in percentiles])),
            sharpe_percentiles=dict(zip(pct_keys, [round(float(np.percentile(sharpes, p)), 2) for p in percentiles])),
            probability_of_ruin=round(ruin_count / self.n_simulations, 4),
        )

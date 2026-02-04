"""Backtest performance metrics calculation and formatting."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    return_pct: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    avg_trade_pnl: float
    expectancy: float
    avg_duration: pd.Timedelta | None
    best_trade: float
    worst_trade: float
    initial_capital: float
    final_capital: float


def calculate_metrics(
    trades_df: pd.DataFrame,
    equity_curve: pd.Series,
    initial_capital: float,
) -> BacktestMetrics:
    """Calculate backtest performance metrics from trades and equity curve."""
    if trades_df.empty:
        return BacktestMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            return_pct=0.0,
            profit_factor=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            avg_trade_pnl=0.0,
            expectancy=0.0,
            avg_duration=None,
            best_trade=0.0,
            worst_trade=0.0,
            initial_capital=initial_capital,
            final_capital=initial_capital,
        )

    pnl = trades_df["pnl"]
    total_trades = len(trades_df)
    winning = pnl[pnl > 0]
    losing = pnl[pnl < 0]
    winning_trades = len(winning)
    losing_trades = len(losing)

    win_rate = winning_trades / total_trades if total_trades > 0 else 0.0
    total_pnl = pnl.sum()
    final_capital = initial_capital + total_pnl
    return_pct = (total_pnl / initial_capital) * 100 if initial_capital > 0 else 0.0

    gross_profit = winning.sum() if len(winning) > 0 else 0.0
    gross_loss = abs(losing.sum()) if len(losing) > 0 else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

    # Sharpe ratio (annualized, assuming hourly bars -> ~252*24 periods/year)
    if len(pnl) > 1:
        pnl_std = pnl.std()
        if pnl_std > 0:
            sharpe_ratio = (pnl.mean() / pnl_std) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
    else:
        sharpe_ratio = 0.0

    # Max drawdown from equity curve
    if len(equity_curve) > 0:
        running_max = equity_curve.cummax()
        drawdown = (equity_curve - running_max) / running_max
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0.0
    else:
        max_drawdown = 0.0

    avg_trade_pnl = pnl.mean() if total_trades > 0 else 0.0

    # Expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)
    avg_win = winning.mean() if len(winning) > 0 else 0.0
    avg_loss = abs(losing.mean()) if len(losing) > 0 else 0.0
    loss_rate = losing_trades / total_trades if total_trades > 0 else 0.0
    expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

    # Average trade duration
    avg_duration = None
    if "entry_time" in trades_df.columns and "exit_time" in trades_df.columns:
        durations = pd.to_datetime(trades_df["exit_time"]) - pd.to_datetime(trades_df["entry_time"])
        avg_duration = durations.mean()

    best_trade = pnl.max() if total_trades > 0 else 0.0
    worst_trade = pnl.min() if total_trades > 0 else 0.0

    return BacktestMetrics(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        total_pnl=total_pnl,
        return_pct=return_pct,
        profit_factor=profit_factor,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        avg_trade_pnl=avg_trade_pnl,
        expectancy=expectancy,
        avg_duration=avg_duration,
        best_trade=best_trade,
        worst_trade=worst_trade,
        initial_capital=initial_capital,
        final_capital=final_capital,
    )


def format_metrics(m: BacktestMetrics) -> str:
    """Format metrics as a human-readable report string."""
    lines = [
        "=" * 50,
        "         BACKTEST REPORT",
        "=" * 50,
        f"  Total Trades:      {m.total_trades}",
        f"  Winning Trades:    {m.winning_trades}",
        f"  Losing Trades:     {m.losing_trades}",
        f"  Win Rate:          {m.win_rate:.1%}",
        "-" * 50,
        f"  Initial Capital:   ${m.initial_capital:,.2f}",
        f"  Final Capital:     ${m.final_capital:,.2f}",
        f"  Total PnL:         ${m.total_pnl:,.2f}",
        f"  Return:            {m.return_pct:,.2f}%",
        "-" * 50,
        f"  Profit Factor:     {m.profit_factor:.2f}",
        f"  Sharpe Ratio:      {m.sharpe_ratio:.2f}",
        f"  Max Drawdown:      {m.max_drawdown:.2%}",
        f"  Avg Trade PnL:     ${m.avg_trade_pnl:,.2f}",
        f"  Expectancy:        ${m.expectancy:,.2f}",
        f"  Best Trade:        ${m.best_trade:,.2f}",
        f"  Worst Trade:       ${m.worst_trade:,.2f}",
    ]
    if m.avg_duration is not None:
        lines.append(f"  Avg Duration:      {m.avg_duration}")
    lines.append("=" * 50)
    return "\n".join(lines)

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.backtest.metrics import BacktestMetrics, calculate_metrics, format_metrics


def _make_df(n=100, base=1.1, trend=0.0, seed=42):
    """Helper to create OHLCV DataFrame with signal columns."""
    np.random.seed(seed)
    close = base + np.cumsum(np.full(n, trend) + np.random.randn(n) * 0.0001)
    high = close + np.abs(np.random.randn(n) * 0.0003)
    low = close - np.abs(np.random.randn(n) * 0.0003)
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": close + np.random.randn(n) * 0.0001,
        "high": high,
        "low": low,
        "close": close,
        "volume": np.random.randint(100, 10000, size=n).astype(float),
        "signal": np.zeros(n, dtype=int),
        "sl": np.full(n, np.nan),
        "tp": np.full(n, np.nan),
    })


def _engine(symbol="EURUSD=X", use_risk_sizing=False, spread=0.0, slippage=0.0, max_pos=3):
    config = BacktestConfig(
        capital=10000,
        spread_pips=spread,
        slippage_pips=slippage,
        risk_per_trade=0.02,
        max_positions=max_pos,
        use_risk_sizing=use_risk_sizing,
    )
    return BacktestEngine(config=config, symbol=symbol, strategy_name="test")


class TestEngineBasics:
    def test_no_signals_no_trades(self):
        df = _make_df()
        engine = _engine()
        result = engine.run(df)
        assert result.trades.empty
        assert len(result.equity_curve) == len(df)

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"close": [1.0], "high": [1.1], "low": [0.9]})
        engine = _engine()
        with pytest.raises(ValueError, match="Missing required column"):
            engine.run(df)

    def test_equity_curve_length(self):
        df = _make_df(n=50)
        engine = _engine()
        result = engine.run(df)
        assert len(result.equity_curve) == 50


class TestTPHit:
    def test_tp_hit_in_rising_market(self):
        """BUY signal in a rising market should hit TP."""
        n = 100
        close = 1.1 + np.arange(n) * 0.001  # steady rise
        high = close + 0.0005
        low = close - 0.0002
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.ones(n) * 1000,
            "signal": np.zeros(n, dtype=int),
            "sl": np.full(n, np.nan),
            "tp": np.full(n, np.nan),
        })
        # Place BUY at bar 5
        df.loc[5, "signal"] = 1
        df.loc[5, "sl"] = close[5] - 0.005
        df.loc[5, "tp"] = close[5] + 0.005

        engine = _engine(spread=0.0, slippage=0.0)
        result = engine.run(df)
        assert len(result.trades) >= 1
        tp_trades = result.trades[result.trades["exit_reason"] == "TP"]
        assert len(tp_trades) >= 1
        assert tp_trades.iloc[0]["pnl"] > 0


class TestSLHit:
    def test_sl_hit_in_falling_market(self):
        """BUY signal in a falling market should hit SL."""
        n = 100
        close = 1.2 - np.arange(n) * 0.001  # steady fall
        high = close + 0.0002
        low = close - 0.0005
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.ones(n) * 1000,
            "signal": np.zeros(n, dtype=int),
            "sl": np.full(n, np.nan),
            "tp": np.full(n, np.nan),
        })
        # Place BUY at bar 5
        df.loc[5, "signal"] = 1
        df.loc[5, "sl"] = close[5] - 0.003
        df.loc[5, "tp"] = close[5] + 0.010

        engine = _engine(spread=0.0, slippage=0.0)
        result = engine.run(df)
        assert len(result.trades) >= 1
        sl_trades = result.trades[result.trades["exit_reason"] == "SL"]
        assert len(sl_trades) >= 1
        assert sl_trades.iloc[0]["pnl"] < 0


class TestShortTrade:
    def test_short_trade_profitable_in_falling_market(self):
        """SELL signal in falling market should be profitable."""
        n = 100
        close = 1.2 - np.arange(n) * 0.001
        high = close + 0.0002
        low = close - 0.0005
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.ones(n) * 1000,
            "signal": np.zeros(n, dtype=int),
            "sl": np.full(n, np.nan),
            "tp": np.full(n, np.nan),
        })
        df.loc[5, "signal"] = -1
        df.loc[5, "sl"] = close[5] + 0.010
        df.loc[5, "tp"] = close[5] - 0.005

        engine = _engine(spread=0.0, slippage=0.0)
        result = engine.run(df)
        assert len(result.trades) >= 1
        tp_trades = result.trades[result.trades["exit_reason"] == "TP"]
        assert len(tp_trades) >= 1
        assert tp_trades.iloc[0]["pnl"] > 0


class TestSpreadSlippage:
    def test_spread_slippage_reduces_pnl(self):
        """Spread and slippage should reduce trade PnL compared to no friction."""
        n = 100
        close = 1.1 + np.arange(n) * 0.001
        high = close + 0.0005
        low = close - 0.0002
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.ones(n) * 1000,
            "signal": np.zeros(n, dtype=int),
            "sl": np.full(n, np.nan),
            "tp": np.full(n, np.nan),
        })
        df.loc[5, "signal"] = 1
        df.loc[5, "sl"] = close[5] - 0.005
        df.loc[5, "tp"] = close[5] + 0.005

        # Without friction
        engine_clean = _engine(spread=0.0, slippage=0.0)
        result_clean = engine_clean.run(df)

        # With friction
        engine_friction = _engine(spread=1.5, slippage=0.5)
        result_friction = engine_friction.run(df)

        if not result_clean.trades.empty and not result_friction.trades.empty:
            clean_pnl = result_clean.trades["pnl"].sum()
            friction_pnl = result_friction.trades["pnl"].sum()
            assert friction_pnl < clean_pnl


class TestMaxPositions:
    def test_max_positions_respected(self):
        """Should not open more positions than max_positions."""
        n = 50
        close = np.full(n, 1.1)
        high = close + 0.0001
        low = close - 0.0001
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
            "open": close.copy(),
            "high": high,
            "low": low,
            "close": close.copy(),
            "volume": np.ones(n) * 1000,
            "signal": np.zeros(n, dtype=int),
            "sl": np.full(n, np.nan),
            "tp": np.full(n, np.nan),
        })
        # Place 5 BUY signals in a row (max_positions=2)
        for i in range(5, 10):
            df.loc[i, "signal"] = 1
            df.loc[i, "sl"] = 1.05
            df.loc[i, "tp"] = 1.15

        engine = _engine(max_pos=2, spread=0.0, slippage=0.0)
        result = engine.run(df)
        # Should have at most 2 trades (others rejected by max_positions)
        assert len(result.trades) <= 2


class TestRiskSizing:
    def test_risk_sizing_calculates_volume(self):
        """With risk sizing, volume should be proportional to risk."""
        n = 50
        close = 1.1 + np.arange(n) * 0.001
        high = close + 0.0005
        low = close - 0.0002
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.ones(n) * 1000,
            "signal": np.zeros(n, dtype=int),
            "sl": np.full(n, np.nan),
            "tp": np.full(n, np.nan),
        })
        df.loc[5, "signal"] = 1
        df.loc[5, "sl"] = close[5] - 0.005
        df.loc[5, "tp"] = close[5] + 0.010

        engine = _engine(use_risk_sizing=True, spread=0.0, slippage=0.0)
        result = engine.run(df)
        assert not result.trades.empty
        vol = result.trades.iloc[0]["volume"]
        assert vol > 0
        # Volume should not be 1.0 (the fixed default)
        assert vol != 1.0


class TestMetrics:
    def test_empty_trades(self):
        trades_df = pd.DataFrame()
        equity = pd.Series([10000.0])
        m = calculate_metrics(trades_df, equity, 10000)
        assert m.total_trades == 0
        assert m.win_rate == 0.0
        assert m.total_pnl == 0.0

    def test_all_winners(self):
        trades_df = pd.DataFrame({
            "pnl": [100.0, 50.0, 75.0],
            "entry_time": pd.date_range("2024-01-01", periods=3, freq="h"),
            "exit_time": pd.date_range("2024-01-01 01:00", periods=3, freq="h"),
        })
        equity = pd.Series([10000, 10100, 10150, 10225])
        m = calculate_metrics(trades_df, equity, 10000)
        assert m.total_trades == 3
        assert m.winning_trades == 3
        assert m.losing_trades == 0
        assert m.win_rate == 1.0
        assert m.total_pnl == 225.0

    def test_mixed_trades(self):
        trades_df = pd.DataFrame({
            "pnl": [100.0, -50.0, 75.0, -25.0],
            "entry_time": pd.date_range("2024-01-01", periods=4, freq="h"),
            "exit_time": pd.date_range("2024-01-01 01:00", periods=4, freq="h"),
        })
        equity = pd.Series([10000, 10100, 10050, 10125, 10100])
        m = calculate_metrics(trades_df, equity, 10000)
        assert m.total_trades == 4
        assert m.winning_trades == 2
        assert m.losing_trades == 2
        assert m.win_rate == 0.5
        assert m.total_pnl == 100.0
        assert m.profit_factor == pytest.approx(175.0 / 75.0, rel=1e-6)

    def test_drawdown_calculation(self):
        equity = pd.Series([10000, 10500, 10200, 9800, 10100])
        trades_df = pd.DataFrame({
            "pnl": [500, -300, -400, 300],
            "entry_time": pd.date_range("2024-01-01", periods=4, freq="h"),
            "exit_time": pd.date_range("2024-01-01 01:00", periods=4, freq="h"),
        })
        m = calculate_metrics(trades_df, equity, 10000)
        # Max drawdown: peak=10500, trough=9800, dd = 700/10500 ≈ 6.67%
        assert m.max_drawdown == pytest.approx(700 / 10500, rel=1e-3)

    def test_format_metrics_string(self):
        m = BacktestMetrics(
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=0.6,
            total_pnl=500.0,
            return_pct=5.0,
            profit_factor=2.5,
            sharpe_ratio=1.2,
            max_drawdown=0.05,
            avg_trade_pnl=50.0,
            expectancy=30.0,
            avg_duration=pd.Timedelta(hours=2),
            best_trade=200.0,
            worst_trade=-100.0,
            initial_capital=10000.0,
            final_capital=10500.0,
        )
        report = format_metrics(m)
        assert "BACKTEST REPORT" in report
        assert "Total Trades" in report
        assert "10" in report
        assert "Win Rate" in report

import numpy as np
import pandas as pd
import pytest

from src.data.indicators import add_all_indicators
from src.strategy.base import StrategyConfig
from src.strategy.bb_reversion import BBReversionStrategy
from src.strategy.ema_crossover import EMACrossoverStrategy


@pytest.fixture
def sample_df():
    """Generate synthetic OHLCV data with indicators."""
    np.random.seed(42)
    n = 300
    close = 1.1000 + np.cumsum(np.random.randn(n) * 0.001)
    high = close + np.abs(np.random.randn(n) * 0.0005)
    low = close - np.abs(np.random.randn(n) * 0.0005)
    open_ = close + np.random.randn(n) * 0.0003
    volume = np.random.randint(100, 10000, size=n).astype(float)

    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })
    df = add_all_indicators(df)
    df = df.dropna().reset_index(drop=True)
    return df


class TestEMACrossover:
    def test_output_columns(self, sample_df):
        strategy = EMACrossoverStrategy()
        result = strategy.generate_signals(sample_df)
        assert "signal" in result.columns
        assert "sl" in result.columns
        assert "tp" in result.columns

    def test_valid_signal_values(self, sample_df):
        strategy = EMACrossoverStrategy()
        result = strategy.generate_signals(sample_df)
        valid_values = {-1, 0, 1}
        actual = set(result["signal"].unique())
        assert actual.issubset(valid_values)

    def test_sl_tp_only_on_signals(self, sample_df):
        strategy = EMACrossoverStrategy()
        result = strategy.generate_signals(sample_df)
        no_signal = result[result["signal"] == 0]
        assert no_signal["sl"].isna().all()
        assert no_signal["tp"].isna().all()

    def test_buy_sl_below_close_tp_above(self, sample_df):
        strategy = EMACrossoverStrategy()
        result = strategy.generate_signals(sample_df)
        buys = result[result["signal"] == 1]
        if len(buys) > 0:
            assert (buys["sl"] < buys["close"]).all()
            assert (buys["tp"] > buys["close"]).all()

    def test_sell_sl_above_close_tp_below(self, sample_df):
        strategy = EMACrossoverStrategy()
        result = strategy.generate_signals(sample_df)
        sells = result[result["signal"] == -1]
        if len(sells) > 0:
            assert (sells["sl"] > sells["close"]).all()
            assert (sells["tp"] < sells["close"]).all()

    def test_does_not_modify_original(self, sample_df):
        original_cols = list(sample_df.columns)
        strategy = EMACrossoverStrategy()
        strategy.generate_signals(sample_df)
        assert list(sample_df.columns) == original_cols
        assert "signal" not in sample_df.columns

    def test_custom_config(self, sample_df):
        config = StrategyConfig(
            name="custom_ema",
            params={
                "fast_period": 9,
                "slow_period": 21,
                "rsi_oversold": 25,
                "rsi_overbought": 75,
                "atr_sl_mult": 2.0,
                "atr_tp_mult": 3.0,
            },
        )
        strategy = EMACrossoverStrategy(config)
        result = strategy.generate_signals(sample_df)
        assert strategy.name == "custom_ema"
        assert "signal" in result.columns


class TestBBReversion:
    def test_output_columns(self, sample_df):
        strategy = BBReversionStrategy()
        result = strategy.generate_signals(sample_df)
        assert "signal" in result.columns
        assert "sl" in result.columns
        assert "tp" in result.columns

    def test_valid_signal_values(self, sample_df):
        strategy = BBReversionStrategy()
        result = strategy.generate_signals(sample_df)
        valid_values = {-1, 0, 1}
        actual = set(result["signal"].unique())
        assert actual.issubset(valid_values)

    def test_sl_tp_only_on_signals(self, sample_df):
        strategy = BBReversionStrategy()
        result = strategy.generate_signals(sample_df)
        no_signal = result[result["signal"] == 0]
        assert no_signal["sl"].isna().all()
        assert no_signal["tp"].isna().all()

    def test_buy_sl_below_close(self, sample_df):
        strategy = BBReversionStrategy()
        result = strategy.generate_signals(sample_df)
        buys = result[result["signal"] == 1]
        if len(buys) > 0:
            assert (buys["sl"] < buys["close"]).all()

    def test_sell_sl_above_close(self, sample_df):
        strategy = BBReversionStrategy()
        result = strategy.generate_signals(sample_df)
        sells = result[result["signal"] == -1]
        if len(sells) > 0:
            assert (sells["sl"] > sells["close"]).all()

    def test_buy_tp_targets_bb_middle(self, sample_df):
        strategy = BBReversionStrategy()
        result = strategy.generate_signals(sample_df)
        buys = result[result["signal"] == 1]
        if len(buys) > 0:
            pd.testing.assert_series_equal(
                buys["tp"].reset_index(drop=True),
                buys["bb_middle"].reset_index(drop=True),
                check_names=False,
            )

    def test_sell_tp_targets_bb_middle(self, sample_df):
        strategy = BBReversionStrategy()
        result = strategy.generate_signals(sample_df)
        sells = result[result["signal"] == -1]
        if len(sells) > 0:
            pd.testing.assert_series_equal(
                sells["tp"].reset_index(drop=True),
                sells["bb_middle"].reset_index(drop=True),
                check_names=False,
            )

    def test_does_not_modify_original(self, sample_df):
        original_cols = list(sample_df.columns)
        strategy = BBReversionStrategy()
        strategy.generate_signals(sample_df)
        assert list(sample_df.columns) == original_cols

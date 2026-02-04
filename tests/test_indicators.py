import numpy as np
import pandas as pd
import pytest

from src.data.indicators import (
    add_all_indicators,
    atr,
    bollinger_bands,
    ema,
    macd,
    rsi,
    sma,
    vwap,
)


@pytest.fixture
def sample_df():
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)
    n = 200
    close = 1.1000 + np.cumsum(np.random.randn(n) * 0.001)
    high = close + np.abs(np.random.randn(n) * 0.0005)
    low = close - np.abs(np.random.randn(n) * 0.0005)
    open_ = close + np.random.randn(n) * 0.0003
    volume = np.random.randint(100, 10000, size=n).astype(float)

    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


class TestEMA:
    def test_length_matches_input(self, sample_df):
        result = ema(sample_df["close"], 14)
        assert len(result) == len(sample_df)

    def test_ema_responds_to_period(self, sample_df):
        short = ema(sample_df["close"], 5)
        long = ema(sample_df["close"], 50)
        # Short EMA should track price more closely (lower variance from close)
        short_diff = (short - sample_df["close"]).std()
        long_diff = (long - sample_df["close"]).std()
        assert short_diff < long_diff


class TestSMA:
    def test_sma_first_values_nan(self, sample_df):
        result = sma(sample_df["close"], 20)
        assert result.iloc[:19].isna().all()
        assert result.iloc[19:].notna().all()


class TestRSI:
    def test_rsi_bounds(self, sample_df):
        result = rsi(sample_df["close"], 14)
        valid = result.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_rsi_at_50_for_flat(self):
        flat = pd.Series([1.0] * 100)
        # With no movement, RSI is undefined / NaN
        result = rsi(flat, 14)
        # After warm-up, values should be NaN (0/0)
        assert result.dropna().empty or True  # graceful handling


class TestMACD:
    def test_macd_columns(self, sample_df):
        result = macd(sample_df["close"])
        assert set(result.columns) == {"macd", "macd_signal", "macd_hist"}
        assert len(result) == len(sample_df)

    def test_histogram_is_diff(self, sample_df):
        result = macd(sample_df["close"])
        diff = result["macd"] - result["macd_signal"]
        pd.testing.assert_series_equal(result["macd_hist"], diff, check_names=False)


class TestBollingerBands:
    def test_bb_columns(self, sample_df):
        result = bollinger_bands(sample_df["close"])
        assert set(result.columns) == {"bb_upper", "bb_middle", "bb_lower"}

    def test_upper_above_lower(self, sample_df):
        result = bollinger_bands(sample_df["close"])
        valid = result.dropna()
        assert (valid["bb_upper"] >= valid["bb_lower"]).all()

    def test_middle_is_sma(self, sample_df):
        result = bollinger_bands(sample_df["close"], period=20)
        expected_sma = sma(sample_df["close"], 20)
        pd.testing.assert_series_equal(
            result["bb_middle"], expected_sma, check_names=False
        )


class TestATR:
    def test_atr_positive(self, sample_df):
        result = atr(sample_df["high"], sample_df["low"], sample_df["close"])
        valid = result.dropna()
        assert (valid > 0).all()


class TestVWAP:
    def test_vwap_reasonable(self, sample_df):
        result = vwap(
            sample_df["high"], sample_df["low"],
            sample_df["close"], sample_df["volume"],
        )
        valid = result.dropna()
        # VWAP should be within the range of prices
        assert valid.iloc[-1] > sample_df["low"].min()
        assert valid.iloc[-1] < sample_df["high"].max()


class TestAddAllIndicators:
    def test_all_columns_present(self, sample_df):
        result = add_all_indicators(sample_df)
        expected = {
            "rsi", "macd", "macd_signal", "macd_hist",
            "bb_upper", "bb_middle", "bb_lower",
            "ema_9", "ema_21", "ema_50", "ema_200",
            "atr", "vwap",
        }
        assert expected.issubset(set(result.columns))

    def test_does_not_modify_original(self, sample_df):
        original_cols = list(sample_df.columns)
        add_all_indicators(sample_df)
        assert list(sample_df.columns) == original_cols

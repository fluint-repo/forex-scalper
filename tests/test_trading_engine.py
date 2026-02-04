"""Tests for CandleAggregator and TradingEngine."""

import sys
import threading
import time

sys.path.insert(0, ".")

import pandas as pd
import pytest

from src.broker.base import OrderSide
from src.broker.paper import PaperBroker
from src.engine.candle_aggregator import CandleAggregator, _floor_timestamp


# --- _floor_timestamp tests ---


class TestFloorTimestamp:
    def test_floor_to_hour(self):
        ts = pd.Timestamp("2024-01-15 14:37:22")
        result = _floor_timestamp(ts, 3600)
        assert result == pd.Timestamp("2024-01-15 14:00:00")

    def test_floor_to_5min(self):
        ts = pd.Timestamp("2024-01-15 14:37:22")
        result = _floor_timestamp(ts, 300)
        assert result == pd.Timestamp("2024-01-15 14:35:00")

    def test_on_boundary(self):
        ts = pd.Timestamp("2024-01-15 14:00:00")
        result = _floor_timestamp(ts, 3600)
        assert result == pd.Timestamp("2024-01-15 14:00:00")


# --- CandleAggregator tests ---


class TestCandleAggregator:
    def test_first_tick_returns_none(self):
        agg = CandleAggregator("1h")
        result = agg.on_tick(pd.Timestamp("2024-01-15 14:00:05"), 1.0850, 1.0852)
        assert result is None

    def test_candle_completes_on_boundary(self):
        agg = CandleAggregator("1h")
        # Tick in hour 14
        agg.on_tick(pd.Timestamp("2024-01-15 14:00:05"), 1.0850, 1.0852)
        agg.on_tick(pd.Timestamp("2024-01-15 14:30:00"), 1.0860, 1.0862)
        # Tick in hour 15 -> closes hour 14 candle
        completed = agg.on_tick(pd.Timestamp("2024-01-15 15:00:05"), 1.0870, 1.0872)
        assert completed is not None
        assert completed["timestamp"] == pd.Timestamp("2024-01-15 14:00:00")

    def test_ohlc_values_correct(self):
        agg = CandleAggregator("1h")
        # Three ticks in same hour
        agg.on_tick(pd.Timestamp("2024-01-15 14:00:05"), 1.0850, 1.0852)  # mid=1.0851
        agg.on_tick(pd.Timestamp("2024-01-15 14:15:00"), 1.0870, 1.0872)  # mid=1.0871 (high)
        agg.on_tick(pd.Timestamp("2024-01-15 14:30:00"), 1.0840, 1.0842)  # mid=1.0841 (low)
        # Close candle
        completed = agg.on_tick(pd.Timestamp("2024-01-15 15:00:05"), 1.0860, 1.0862)
        assert completed["open"] == pytest.approx(1.0851, abs=1e-5)
        assert completed["high"] == pytest.approx(1.0871, abs=1e-5)
        assert completed["low"] == pytest.approx(1.0841, abs=1e-5)
        assert completed["close"] == pytest.approx(1.0841, abs=1e-5)

    def test_history_accumulates(self):
        agg = CandleAggregator("1h")
        # Build and close 2 candles
        agg.on_tick(pd.Timestamp("2024-01-15 14:00:05"), 1.0850, 1.0852)
        agg.on_tick(pd.Timestamp("2024-01-15 15:00:05"), 1.0860, 1.0862)  # closes candle 1
        agg.on_tick(pd.Timestamp("2024-01-15 16:00:05"), 1.0870, 1.0872)  # closes candle 2
        df = agg.history_df
        assert len(df) == 2

    def test_max_history_size_respected(self):
        agg = CandleAggregator("1m")
        # Generate more candles than CANDLE_HISTORY_SIZE
        base = pd.Timestamp("2024-01-15 00:00:00")
        for i in range(260):
            ts = base + pd.Timedelta(minutes=i, seconds=5)
            agg.on_tick(ts, 1.0850 + i * 0.0001, 1.0852 + i * 0.0001)
        df = agg.history_df
        assert len(df) <= 250

    def test_seed_history(self):
        agg = CandleAggregator("1h")
        seed_df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-15", periods=5, freq="h"),
            "open": [1.0] * 5,
            "high": [1.1] * 5,
            "low": [0.9] * 5,
            "close": [1.05] * 5,
            "volume": [100] * 5,
        })
        agg.seed_history(seed_df)
        df = agg.history_df
        assert len(df) == 5

    def test_history_df_returns_dataframe(self):
        agg = CandleAggregator("1h")
        df = agg.history_df
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]


# --- TradingEngine SL/TP tests ---


class TestSLTPMonitor:
    """Test the SL/TP checking logic via the TradingEngine._check_sl_tp method."""

    def _make_engine(self):
        from src.data.demo_feed import DemoFeed
        from src.engine.trading import TradingEngine
        from src.strategy.ema_crossover import EMACrossoverStrategy

        strategy = EMACrossoverStrategy()
        feed = DemoFeed()
        broker = PaperBroker(symbol="EURUSD=X", capital=10000, max_positions=5)
        engine = TradingEngine(
            strategy=strategy, feed=feed, broker=broker,
            symbol="EURUSD=X", timeframe="1h",
        )
        return engine, broker

    def test_buy_sl_hit(self):
        engine, broker = self._make_engine()
        broker.update_price("EURUSD=X", bid=1.0850, ask=1.0852)
        r = broker.place_order("EURUSD=X", OrderSide.BUY, 0.0001, sl=1.0800, tp=1.0900)
        assert r.success
        # Price drops below SL
        broker.update_price("EURUSD=X", bid=1.0799, ask=1.0801)
        engine._check_sl_tp(1.0799, 1.0801)
        assert len(broker.get_positions()) == 0
        trades = broker.get_closed_trades()
        assert trades[-1]["exit_reason"] == "SL"

    def test_buy_tp_hit(self):
        engine, broker = self._make_engine()
        broker.update_price("EURUSD=X", bid=1.0850, ask=1.0852)
        r = broker.place_order("EURUSD=X", OrderSide.BUY, 0.0001, sl=1.0800, tp=1.0900)
        assert r.success
        # Price rises above TP
        broker.update_price("EURUSD=X", bid=1.0901, ask=1.0903)
        engine._check_sl_tp(1.0901, 1.0903)
        assert len(broker.get_positions()) == 0
        trades = broker.get_closed_trades()
        assert trades[-1]["exit_reason"] == "TP"

    def test_sell_sl_hit(self):
        engine, broker = self._make_engine()
        broker.update_price("EURUSD=X", bid=1.0850, ask=1.0852)
        r = broker.place_order("EURUSD=X", OrderSide.SELL, 0.0001, sl=1.0900, tp=1.0800)
        assert r.success
        # Price rises above SL (ask >= sl)
        broker.update_price("EURUSD=X", bid=1.0899, ask=1.0901)
        engine._check_sl_tp(1.0899, 1.0901)
        assert len(broker.get_positions()) == 0
        trades = broker.get_closed_trades()
        assert trades[-1]["exit_reason"] == "SL"

    def test_sell_tp_hit(self):
        engine, broker = self._make_engine()
        broker.update_price("EURUSD=X", bid=1.0850, ask=1.0852)
        r = broker.place_order("EURUSD=X", OrderSide.SELL, 0.0001, sl=1.0900, tp=1.0800)
        assert r.success
        # Price drops below TP (ask <= tp)
        broker.update_price("EURUSD=X", bid=1.0798, ask=1.0800)
        engine._check_sl_tp(1.0798, 1.0800)
        assert len(broker.get_positions()) == 0
        trades = broker.get_closed_trades()
        assert trades[-1]["exit_reason"] == "TP"


# --- Engine lifecycle tests ---


class TestEngineLifecycle:
    def _make_engine(self):
        from src.data.demo_feed import DemoFeed
        from src.engine.trading import TradingEngine
        from src.strategy.ema_crossover import EMACrossoverStrategy

        strategy = EMACrossoverStrategy()
        feed = DemoFeed()
        broker = PaperBroker(symbol="EURUSD=X", capital=10000, max_positions=5)
        engine = TradingEngine(
            strategy=strategy, feed=feed, broker=broker,
            symbol="EURUSD=X", timeframe="1h",
        )
        return engine, broker

    def test_stop_closes_positions(self):
        engine, broker = self._make_engine()
        broker.update_price("EURUSD=X", bid=1.0850, ask=1.0852)
        broker.place_order("EURUSD=X", OrderSide.BUY, 0.0001, sl=1.0800, tp=1.0900)
        broker.place_order("EURUSD=X", OrderSide.SELL, 0.0001, sl=1.0900, tp=1.0800)
        assert len(broker.get_positions()) == 2
        # Simulate engine running state
        engine._running.set()
        engine.stop()
        assert len(broker.get_positions()) == 0
        trades = broker.get_closed_trades()
        assert all(t["exit_reason"] == "SHUTDOWN" for t in trades)

    def test_is_running_flag(self):
        engine, broker = self._make_engine()
        assert not engine.is_running
        engine._running.set()
        assert engine.is_running
        engine._running.clear()
        assert not engine.is_running

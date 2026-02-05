"""Tests for EngineManager."""

import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

import pytest

from src.api.state import EngineManager
from src.broker.paper import PaperBroker
from src.data.demo_feed import DemoFeed
from src.strategy.ema_crossover import EMACrossoverStrategy


class TestEngineManager:
    def test_initial_state(self):
        mgr = EngineManager()
        assert not mgr.is_running
        assert mgr.engine is None
        assert mgr.broker is None

    @patch("src.engine.trading.TradingEngine.start")
    def test_start_engine(self, mock_start):
        mgr = EngineManager()
        strategy = EMACrossoverStrategy()
        feed = DemoFeed()
        broker = PaperBroker()

        mgr.start_engine(strategy, feed, broker, "EURUSD=X", "1h")
        assert mgr.engine is not None
        assert mgr.broker is broker
        assert mgr.strategy is strategy
        assert mgr.event_bus is not None
        assert mgr.symbol == "EURUSD=X"
        assert mgr.timeframe == "1h"
        mock_start.assert_called_once()

    @patch("src.engine.trading.TradingEngine.start")
    def test_double_start_raises(self, mock_start):
        mgr = EngineManager()
        strategy = EMACrossoverStrategy()
        feed = DemoFeed()
        broker = PaperBroker()

        mgr.start_engine(strategy, feed, broker, "EURUSD=X", "1h")
        # Simulate engine running
        mgr.engine._running.set()

        with pytest.raises(RuntimeError, match="already running"):
            mgr.start_engine(strategy, feed, broker, "EURUSD=X", "1h")

    @patch("src.engine.trading.TradingEngine.start")
    @patch("src.engine.trading.TradingEngine.stop")
    def test_stop_engine(self, mock_stop, mock_start):
        mgr = EngineManager()
        strategy = EMACrossoverStrategy()
        feed = DemoFeed()
        broker = PaperBroker()

        mgr.start_engine(strategy, feed, broker, "EURUSD=X", "1h")
        mgr.engine._running.set()
        mgr.stop_engine()
        mock_stop.assert_called_once()

    def test_stop_when_not_running(self):
        mgr = EngineManager()
        # Should not raise
        mgr.stop_engine()

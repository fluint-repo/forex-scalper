"""Tests for EngineManager."""

import sys
from unittest.mock import MagicMock, PropertyMock, patch

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

        eid = mgr.start_engine(strategy, feed, broker, "EURUSD=X", "1h")
        assert mgr.engine is not None
        assert mgr.broker is broker
        assert mgr.strategy is strategy
        assert mgr.event_bus is not None
        assert mgr.symbol == "EURUSD=X"
        assert mgr.timeframe == "1h"
        assert isinstance(eid, str)
        mock_start.assert_called_once()

    @patch("src.engine.trading.TradingEngine.start")
    def test_double_start_raises(self, mock_start):
        mgr = EngineManager()
        strategy = EMACrossoverStrategy()
        feed = DemoFeed()
        broker = PaperBroker()

        eid = mgr.start_engine(strategy, feed, broker, "EURUSD=X", "1h")
        # Simulate engine running
        mgr.engine._running.set()

        with pytest.raises(RuntimeError, match="already running"):
            mgr.start_engine(strategy, feed, broker, "EURUSD=X", "1h", engine_id=eid)

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

    @patch("src.engine.trading.TradingEngine.start")
    def test_broker_error_in_positions(self, mock_start):
        """get_all_positions should handle broker errors gracefully."""
        mgr = EngineManager()
        strategy = EMACrossoverStrategy()
        feed = DemoFeed()
        broker = MagicMock()
        broker.get_account_info.return_value = {"balance": 10000, "equity": 10000, "open_positions": 0}
        broker.get_positions.side_effect = Exception("broker down")

        eid = mgr.start_engine(strategy, feed, broker, "EURUSD=X", "1h")
        mgr._engines[eid].engine._running.set()

        # Should not raise
        positions = mgr.get_all_positions()
        assert positions == []

    @patch("src.engine.trading.TradingEngine.start")
    def test_broker_error_in_account(self, mock_start):
        """get_aggregated_account should handle broker errors gracefully."""
        mgr = EngineManager()
        strategy = EMACrossoverStrategy()
        feed = DemoFeed()
        broker = MagicMock()
        # Allow startup to succeed, then fail
        broker.get_account_info.return_value = {"balance": 10000, "equity": 10000, "open_positions": 0}

        eid = mgr.start_engine(strategy, feed, broker, "EURUSD=X", "1h")
        mgr._engines[eid].engine._running.set()

        # Now make broker fail
        broker.get_account_info.side_effect = Exception("broker down")

        # Should not raise, returns zeros
        account = mgr.get_aggregated_account()
        assert account["balance"] == 0.0
        assert account["equity"] == 0.0

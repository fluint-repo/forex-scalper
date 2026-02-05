"""Tests for enhanced database operations — Phase 5C."""

import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch, call

from src.database.repository import TradeRepository


class MockSession:
    """Mock SQLAlchemy session for testing."""

    def __init__(self):
        self.executed = []
        self._return_rows = []
        self.committed = False

    def execute(self, stmt, params=None):
        self.executed.append((stmt, params))
        result = MagicMock()
        if self._return_rows:
            result.fetchone.return_value = self._return_rows.pop(0)
            result.fetchall.return_value = self._return_rows
        else:
            result.fetchone.return_value = (1,)
            result.fetchall.return_value = []
        return result

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestCreateAndCloseRun:
    @patch("src.database.repository.SessionLocal")
    def test_create_run(self, mock_session_cls):
        session = MockSession()
        mock_session_cls.return_value = session

        repo = TradeRepository()
        run_id = repo.create_run("ema_crossover", "EURUSD=X", "1h", "paper", 10000.0)

        assert run_id == 1
        assert session.committed
        assert len(session.executed) == 1

    @patch("src.database.repository.SessionLocal")
    def test_close_run(self, mock_session_cls):
        session = MockSession()
        mock_session_cls.return_value = session

        repo = TradeRepository()
        repo.close_run(1, 10500.0, 15)

        assert session.committed
        assert len(session.executed) == 1


class TestInsertTrade:
    @patch("src.database.repository.SessionLocal")
    def test_insert_trade_with_run_id(self, mock_session_cls):
        session = MockSession()
        mock_session_cls.return_value = session

        repo = TradeRepository()
        trade = {
            "strategy_name": "ema_crossover",
            "symbol": "EURUSD=X",
            "timeframe": "1h",
            "side": "BUY",
            "entry_time": datetime(2024, 1, 1, 10, 0),
            "exit_time": datetime(2024, 1, 1, 11, 0),
            "entry_price": 1.1000,
            "exit_price": 1.1050,
            "volume": 0.1,
            "pnl": 50.0,
            "sl": 1.0950,
            "tp": 1.1050,
            "exit_reason": "TP",
        }
        trade_id = repo.insert_trade(trade, run_id=5)
        assert trade_id == 1
        assert session.committed
        params = session.executed[0][1]
        assert params["run_id"] == 5
        assert params["strategy_name"] == "ema_crossover"


class TestPerformanceSummary:
    @patch("src.database.repository.engine")
    def test_get_performance_summary(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        # total, total_pnl, wins, losses, avg_pnl, best, worst, gross_profit, gross_loss
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (10, 500.0, 7, 3, 50.0, 200.0, -100.0, 800.0, 300.0)
        mock_conn.execute.return_value = mock_result

        repo = TradeRepository()
        summary = repo.get_performance_summary(1)

        assert summary["total_trades"] == 10
        assert summary["total_pnl"] == 500.0
        assert summary["winning_trades"] == 7
        assert summary["losing_trades"] == 3
        assert summary["win_rate"] == 0.7
        assert summary["profit_factor"] == 2.67  # 800/300

    @patch("src.database.repository.engine")
    def test_empty_run_summary(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.fetchone.return_value = (0, 0, 0, 0, 0, 0, 0, 0, 0)
        mock_conn.execute.return_value = mock_result

        repo = TradeRepository()
        summary = repo.get_performance_summary(999)

        assert summary["total_trades"] == 0
        assert summary["total_pnl"] == 0
        assert summary["win_rate"] == 0


class TestDailySummaries:
    @patch("src.database.repository.engine")
    def test_get_daily_summaries(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (date(2024, 1, 1), 100.0, 5, 3, 0.02),
            (date(2024, 1, 2), -50.0, 3, 1, 0.05),
        ]
        mock_conn.execute.return_value = mock_result

        repo = TradeRepository()
        summaries = repo.get_daily_summaries(1)

        assert len(summaries) == 2
        assert summaries[0]["realized_pnl"] == 100.0
        assert summaries[1]["trade_count"] == 3

    @patch("src.database.repository.SessionLocal")
    def test_update_daily_summary_upsert(self, mock_session_cls):
        session = MockSession()
        mock_session_cls.return_value = session

        repo = TradeRepository()
        repo.update_daily_summary(1, date(2024, 1, 1), 50.0, True)

        assert session.committed
        params = session.executed[0][1]
        assert params["run_id"] == 1
        assert params["pnl"] == 50.0
        assert params["win"] == 1


class TestTradeHistory:
    @patch("src.database.repository.engine")
    def test_get_trade_history_pagination(self, mock_engine):
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            (1, "ema", "EURUSD=X", "1h", "BUY", datetime(2024, 1, 1), datetime(2024, 1, 1, 1),
             1.1, 1.105, 0.1, 50.0, 1.09, 1.11, "TP", datetime(2024, 1, 1)),
        ]
        mock_conn.execute.return_value = mock_result

        repo = TradeRepository()
        trades = repo.get_trade_history(1, limit=10, offset=0)

        assert len(trades) == 1
        assert trades[0]["symbol"] == "EURUSD=X"
        assert trades[0]["pnl"] == 50.0


class TestAutoPersist:
    def test_auto_persist_on_position_close(self):
        """Integration test: TradingEngine auto-persists via repository."""
        from unittest.mock import MagicMock
        from src.engine.trading import TradingEngine
        from src.engine.event_bus import EventBus

        broker = MagicMock()
        broker.get_positions.return_value = []
        broker.get_closed_trades.return_value = [
            {"order_id": "P-001", "symbol": "EURUSD=X", "side": "BUY",
             "entry_price": 1.1, "exit_price": 1.105, "volume": 0.1,
             "pnl": 50.0, "sl": 1.09, "tp": 1.11, "exit_reason": "TP",
             "entry_time": "2024-01-01", "exit_time": "2024-01-01"}
        ]
        broker.server_managed_sl_tp = False

        repo = MagicMock()
        strategy = MagicMock()
        strategy.name = "ema_crossover"
        feed = MagicMock()
        bus = EventBus()

        engine = TradingEngine(
            strategy=strategy, feed=feed, broker=broker,
            symbol="EURUSD=X", timeframe="1h", event_bus=bus,
            repository=repo, run_id=1,
        )
        engine._on_position_closed("P-001")

        repo.insert_trade.assert_called_once()
        call_args = repo.insert_trade.call_args
        assert call_args[0][1] == 1  # run_id

    def test_run_id_assigned_on_engine_start(self):
        """TradingEngine accepts run_id parameter."""
        from src.engine.trading import TradingEngine

        broker = MagicMock()
        strategy = MagicMock()
        feed = MagicMock()

        engine = TradingEngine(
            strategy=strategy, feed=feed, broker=broker,
            run_id=42, repository=MagicMock(),
        )
        assert engine.run_id == 42

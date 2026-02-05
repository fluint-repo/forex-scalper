"""Tests for multi-engine EngineManager — Phase 5D."""

import pytest
from unittest.mock import MagicMock, patch

from src.api.state import EngineManager, EngineInstance
from src.engine.event_bus import EventBus


def _mock_engine(running=True):
    engine = MagicMock()
    engine.is_running = running
    engine.candle_history = MagicMock()
    return engine


def _mock_strategy(name="ema_crossover"):
    strategy = MagicMock()
    strategy.name = name
    return strategy


def _mock_broker(balance=10000, equity=10000, positions=None):
    broker = MagicMock()
    broker.get_account_info.return_value = {
        "balance": balance, "equity": equity, "open_positions": 0, "total_pnl": 0,
    }
    broker.get_positions.return_value = positions or []
    broker.get_closed_trades.return_value = []
    return broker


def _mock_feed():
    feed = MagicMock()
    feed.get_historical.return_value = MagicMock(empty=True)
    return feed


class TestMultiEngine:
    def test_start_multiple_engines(self):
        mgr = EngineManager()

        # Manually add engine instances to avoid actual start()
        for i, (sym, strat_name) in enumerate([
            ("EURUSD=X", "ema_crossover"),
            ("GBPUSD=X", "bb_reversion"),
        ]):
            engine = _mock_engine()
            strategy = _mock_strategy(strat_name)
            broker = _mock_broker()
            bus = EventBus()
            eid = f"{strat_name}_{sym}_1h"

            inst = EngineInstance(
                engine_id=eid, engine=engine, broker=broker,
                feed=_mock_feed(), strategy=strategy, event_bus=bus,
                symbol=sym, timeframe="1h", broker_type="paper",
            )
            mgr._engines[eid] = inst
            mgr._last_started = eid

        assert mgr.is_running
        engines = mgr.list_engines()
        assert len(engines) == 2

    def test_stop_single_engine(self):
        mgr = EngineManager()
        engine = _mock_engine()
        inst = EngineInstance(
            engine_id="test_1", engine=engine, broker=_mock_broker(),
            feed=_mock_feed(), strategy=_mock_strategy(), event_bus=EventBus(),
            symbol="EURUSD=X", timeframe="1h", broker_type="paper",
        )
        mgr._engines["test_1"] = inst
        mgr._last_started = "test_1"

        mgr.stop_engine("test_1")
        engine.stop.assert_called_once()

    def test_stop_all_engines(self):
        mgr = EngineManager()
        engines = {}
        for eid in ["eng_1", "eng_2", "eng_3"]:
            eng = _mock_engine()
            inst = EngineInstance(
                engine_id=eid, engine=eng, broker=_mock_broker(),
                feed=_mock_feed(), strategy=_mock_strategy(), event_bus=EventBus(),
                symbol="EURUSD=X", timeframe="1h", broker_type="paper",
            )
            mgr._engines[eid] = inst

        mgr.stop_all()
        for inst in mgr._engines.values():
            inst.engine.stop.assert_called_once()

    def test_list_engines(self):
        mgr = EngineManager()
        for eid, sym in [("e1", "EURUSD=X"), ("e2", "GBPUSD=X")]:
            inst = EngineInstance(
                engine_id=eid, engine=_mock_engine(), broker=_mock_broker(),
                feed=_mock_feed(), strategy=_mock_strategy(), event_bus=EventBus(),
                symbol=sym, timeframe="1h", broker_type="paper",
            )
            mgr._engines[eid] = inst

        engines = mgr.list_engines()
        assert len(engines) == 2
        symbols = {e["symbol"] for e in engines}
        assert "EURUSD=X" in symbols
        assert "GBPUSD=X" in symbols

    def test_shared_risk_manager(self):
        mgr = EngineManager()
        broker1 = _mock_broker()
        broker2 = _mock_broker()

        # Add engines with shared risk
        from src.risk.manager import RiskManager
        rm = RiskManager(broker1)
        mgr._shared_risk_manager = rm

        inst1 = EngineInstance(
            engine_id="e1", engine=_mock_engine(), broker=broker1,
            feed=_mock_feed(), strategy=_mock_strategy(), event_bus=EventBus(),
            risk_manager=rm, symbol="EURUSD=X", timeframe="1h",
        )
        inst2 = EngineInstance(
            engine_id="e2", engine=_mock_engine(), broker=broker2,
            feed=_mock_feed(), strategy=_mock_strategy("bb_reversion"),
            event_bus=EventBus(), risk_manager=rm, symbol="GBPUSD=X", timeframe="1h",
        )
        mgr._engines = {"e1": inst1, "e2": inst2}

        # Both share same risk manager
        assert mgr._engines["e1"].risk_manager is mgr._engines["e2"].risk_manager

    def test_engine_id_generation(self):
        mgr = EngineManager()
        eid1 = mgr._generate_engine_id("ema_crossover", "EURUSD=X", "1h")
        assert eid1 == "ema_crossover_EURUSD=X_1h"

        # Add a dummy to trigger suffix
        mgr._engines[eid1] = MagicMock()
        eid2 = mgr._generate_engine_id("ema_crossover", "EURUSD=X", "1h")
        assert eid2 == "ema_crossover_EURUSD=X_1h_2"

    def test_duplicate_engine_id_rejected(self):
        mgr = EngineManager()
        engine = _mock_engine(running=True)
        inst = EngineInstance(
            engine_id="dup_id", engine=engine, broker=_mock_broker(),
            feed=_mock_feed(), strategy=_mock_strategy(), event_bus=EventBus(),
            symbol="EURUSD=X", timeframe="1h", broker_type="paper",
        )
        mgr._engines["dup_id"] = inst

        with pytest.raises(RuntimeError, match="already running"):
            mgr.start_engine(
                strategy=_mock_strategy(), feed=_mock_feed(),
                broker=_mock_broker(), symbol="EURUSD=X", timeframe="1h",
                engine_id="dup_id",
            )

    def test_portfolio_risk_across_engines(self):
        mgr = EngineManager()
        positions1 = [{"order_id": "1", "symbol": "EURUSD=X", "side": "BUY",
                        "entry_price": 1.1, "volume": 0.1, "sl": 1.09, "tp": 1.12,
                        "unrealized_pnl": 50}]
        positions2 = [{"order_id": "2", "symbol": "GBPUSD=X", "side": "SELL",
                        "entry_price": 1.3, "volume": 0.1, "sl": 1.31, "tp": 1.28,
                        "unrealized_pnl": -20}]

        broker1 = _mock_broker(positions=positions1)
        broker2 = _mock_broker(positions=positions2)

        inst1 = EngineInstance(
            engine_id="e1", engine=_mock_engine(), broker=broker1,
            feed=_mock_feed(), strategy=_mock_strategy(), event_bus=EventBus(),
            symbol="EURUSD=X", timeframe="1h",
        )
        inst2 = EngineInstance(
            engine_id="e2", engine=_mock_engine(), broker=broker2,
            feed=_mock_feed(), strategy=_mock_strategy(), event_bus=EventBus(),
            symbol="GBPUSD=X", timeframe="1h",
        )
        mgr._engines = {"e1": inst1, "e2": inst2}

        all_pos = mgr.get_all_positions()
        assert len(all_pos) == 2

    def test_get_engine(self):
        mgr = EngineManager()
        inst = EngineInstance(
            engine_id="my_engine", engine=_mock_engine(), broker=_mock_broker(),
            feed=_mock_feed(), strategy=_mock_strategy(), event_bus=EventBus(),
            symbol="EURUSD=X", timeframe="1h",
        )
        mgr._engines["my_engine"] = inst

        assert mgr.get_engine("my_engine") is inst
        assert mgr.get_engine("nonexistent") is None

    def test_aggregated_account(self):
        mgr = EngineManager()
        broker1 = _mock_broker(balance=10000, equity=10500)
        broker1.get_account_info.return_value = {
            "balance": 10000, "equity": 10500, "open_positions": 1, "total_pnl": 500,
        }
        broker2 = _mock_broker(balance=5000, equity=4800)
        broker2.get_account_info.return_value = {
            "balance": 5000, "equity": 4800, "open_positions": 2, "total_pnl": -200,
        }

        inst1 = EngineInstance(
            engine_id="e1", engine=_mock_engine(), broker=broker1,
            feed=_mock_feed(), strategy=_mock_strategy(), event_bus=EventBus(),
        )
        inst2 = EngineInstance(
            engine_id="e2", engine=_mock_engine(), broker=broker2,
            feed=_mock_feed(), strategy=_mock_strategy(), event_bus=EventBus(),
        )
        mgr._engines = {"e1": inst1, "e2": inst2}

        account = mgr.get_aggregated_account()
        assert account["balance"] == 15000
        assert account["equity"] == 15300
        assert account["open_positions"] == 3
        assert account["total_pnl"] == 300

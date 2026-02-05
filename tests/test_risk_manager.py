"""Tests for RiskManager — Phase 5A."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.risk.manager import RiskManager


def _make_broker(
    balance=10000, equity=10000, positions=None, closed_trades=None
):
    broker = MagicMock()
    broker.get_account_info.return_value = {
        "balance": balance,
        "equity": equity,
        "open_positions": len(positions or []),
    }
    broker.get_positions.return_value = positions or []
    broker.get_closed_trades.return_value = closed_trades or []
    return broker


class TestDailyLossCheck:
    def test_daily_loss_check_passes(self):
        broker = _make_broker(equity=9800)
        rm = RiskManager(broker, max_daily_loss_pct=5.0)
        rm.reset_daily()
        # Equity at 9800, started at 9800 → 0% loss → passes
        assert rm.check_daily_loss() is True

    def test_daily_loss_check_fails(self):
        broker = _make_broker(equity=10000)
        rm = RiskManager(broker, max_daily_loss_pct=5.0)
        rm.reset_daily()
        # Now equity drops to 9400 (6% loss)
        broker.get_account_info.return_value = {"equity": 9400, "balance": 9400, "open_positions": 0}
        assert rm.check_daily_loss() is False
        assert rm.circuit_breaker_active is True


class TestPositionLimits:
    def test_position_limit_check_passes(self):
        broker = _make_broker(positions=[])
        rm = RiskManager(broker, max_open_positions=3)
        assert rm.check_position_limits("EURUSD=X", "BUY") is True

    def test_position_limit_check_fails(self):
        positions = [
            {"order_id": "1", "symbol": "EURUSD=X", "side": "BUY", "entry_price": 1.1, "volume": 0.1, "sl": 1.09, "tp": 1.12},
            {"order_id": "2", "symbol": "GBPUSD=X", "side": "BUY", "entry_price": 1.3, "volume": 0.1, "sl": 1.29, "tp": 1.32},
            {"order_id": "3", "symbol": "USDJPY=X", "side": "SELL", "entry_price": 150, "volume": 0.1, "sl": 151, "tp": 149},
        ]
        broker = _make_broker(positions=positions)
        rm = RiskManager(broker, max_open_positions=3)
        assert rm.check_position_limits("EURUSD=X", "SELL") is False

    def test_correlated_exposure_limit(self):
        positions = [
            {"order_id": "1", "symbol": "EURUSD=X", "side": "SELL", "entry_price": 1.1, "volume": 0.1, "sl": 1.11, "tp": 1.08},
            {"order_id": "2", "symbol": "GBPUSD=X", "side": "SELL", "entry_price": 1.3, "volume": 0.1, "sl": 1.31, "tp": 1.28},
        ]
        broker = _make_broker(positions=positions)
        rm = RiskManager(broker, max_open_positions=5, max_correlated_exposure=2)
        # USDJPY BUY is in same USD_LONG group as EURUSD SELL + GBPUSD SELL
        assert rm.check_position_limits("USDJPY=X", "BUY") is False
        # But a USD_SHORT position should be OK
        assert rm.check_position_limits("EURUSD=X", "BUY") is True


class TestPortfolioRisk:
    def test_portfolio_risk_check_passes(self):
        positions = [
            {"order_id": "1", "symbol": "EURUSD=X", "side": "BUY", "entry_price": 1.1000, "volume": 0.0001, "sl": 1.0990, "tp": 1.1020},
        ]
        broker = _make_broker(equity=10000, positions=positions)
        rm = RiskManager(broker, max_portfolio_risk_pct=10.0)
        assert rm.check_portfolio_risk() is True

    def test_portfolio_risk_check_fails(self):
        # risk per pos = sl_dist * volume / pip_value
        # 0.0200 * 5.0 / 0.0001 = 1000 per pos → 2000 total → 20% of 10000
        positions = [
            {"order_id": "1", "symbol": "EURUSD=X", "side": "BUY", "entry_price": 1.1000, "volume": 5.0, "sl": 1.0800, "tp": 1.1200},
            {"order_id": "2", "symbol": "GBPUSD=X", "side": "SELL", "entry_price": 1.3000, "volume": 5.0, "sl": 1.3200, "tp": 1.2800},
        ]
        broker = _make_broker(equity=10000, positions=positions)
        rm = RiskManager(broker, max_portfolio_risk_pct=10.0)
        assert rm.check_portfolio_risk() is False


class TestPositionSizing:
    def test_fixed_risk_sizing(self):
        broker = _make_broker()
        rm = RiskManager(broker, position_size_method="fixed_risk", risk_per_trade=0.02)
        # equity=10000, risk=200, sl_distance=0.0010, pip_value=0.0001
        size = rm.calculate_position_size(10000, 0.0010, "EURUSD=X")
        expected = 200 * 0.0001 / 0.0010  # = 0.02
        assert abs(size - expected) < 1e-6

    def test_kelly_sizing(self):
        broker = _make_broker()
        rm = RiskManager(broker, position_size_method="kelly", kelly_fraction=0.5)
        # Seed with enough trades for Kelly
        for _ in range(8):
            rm.record_trade(100)  # wins
        for _ in range(4):
            rm.record_trade(-50)  # losses (12 total trades)

        size = rm.calculate_position_size(10000, 0.0010, "EURUSD=X")
        assert size > 0

    def test_zero_sl_distance(self):
        broker = _make_broker()
        rm = RiskManager(broker)
        assert rm.calculate_position_size(10000, 0.0, "EURUSD=X") == 0.0


class TestCircuitBreaker:
    def test_circuit_breaker_blocks_orders(self):
        broker = _make_broker(equity=10000)
        rm = RiskManager(broker, max_daily_loss_pct=5.0)
        rm.reset_daily()

        # Trigger circuit breaker
        broker.get_account_info.return_value = {"equity": 9400, "balance": 9400, "open_positions": 0}
        rm.check_daily_loss()

        assert rm.circuit_breaker_active is True
        # Subsequent check should also fail
        assert rm.check_daily_loss() is False

    def test_reset_daily(self):
        broker = _make_broker(equity=10000)
        rm = RiskManager(broker, max_daily_loss_pct=5.0)
        rm.reset_daily()

        # Trigger circuit breaker
        broker.get_account_info.return_value = {"equity": 9400, "balance": 9400, "open_positions": 0}
        rm.check_daily_loss()
        assert rm.circuit_breaker_active is True

        # Reset
        broker.get_account_info.return_value = {"equity": 9400, "balance": 9400, "open_positions": 0}
        rm.reset_daily()
        assert rm.circuit_breaker_active is False
        assert rm.check_daily_loss() is True  # Should pass now with new baseline


class TestUTCDateHandling:
    def test_daily_reset_uses_utc(self):
        broker = _make_broker(equity=10000)
        rm = RiskManager(broker, max_daily_loss_pct=5.0)
        rm.reset_daily()
        # The stored date should match UTC date
        expected_date = datetime.now(timezone.utc).date()
        assert rm._daily_date == expected_date

"""Tests for PaperBroker — simulated order execution."""

import sys

sys.path.insert(0, ".")

import pytest

from src.broker.base import OrderSide
from src.broker.paper import PaperBroker


@pytest.fixture
def broker():
    b = PaperBroker(symbol="EURUSD=X", capital=10000, slippage_pips=0.5)
    b.update_price("EURUSD=X", bid=1.0850, ask=1.0852)
    return b


class TestOrderFills:
    def test_buy_fills_at_ask_plus_slippage(self, broker):
        result = broker.place_order("EURUSD=X", OrderSide.BUY, 1.0, sl=1.0800, tp=1.0900)
        assert result.success
        expected = 1.0852 + 0.5 * 0.0001  # ask + slippage
        assert result.price == pytest.approx(expected, abs=1e-6)

    def test_sell_fills_at_bid_minus_slippage(self, broker):
        result = broker.place_order("EURUSD=X", OrderSide.SELL, 1.0, sl=1.0900, tp=1.0800)
        assert result.success
        expected = 1.0850 - 0.5 * 0.0001  # bid - slippage
        assert result.price == pytest.approx(expected, abs=1e-6)

    def test_slippage_applied_correctly(self, broker):
        # Zero-slippage broker
        b = PaperBroker(symbol="EURUSD=X", capital=10000, slippage_pips=0.0)
        b.update_price("EURUSD=X", bid=1.0850, ask=1.0852)
        result = b.place_order("EURUSD=X", OrderSide.BUY, 1.0, sl=1.0800, tp=1.0900)
        assert result.price == pytest.approx(1.0852, abs=1e-6)


class TestNoPriceAvailable:
    def test_no_price_returns_failure(self):
        b = PaperBroker(symbol="EURUSD=X", capital=10000)
        result = b.place_order("EURUSD=X", OrderSide.BUY, 1.0, sl=1.0800, tp=1.0900)
        assert not result.success
        assert "No price" in result.message


class TestOrderIDs:
    def test_sequential_unique_ids(self, broker):
        r1 = broker.place_order("EURUSD=X", OrderSide.BUY, 1.0, sl=1.0800, tp=1.0900)
        r2 = broker.place_order("EURUSD=X", OrderSide.BUY, 1.0, sl=1.0800, tp=1.0900)
        assert r1.order_id == "PAPER-000001"
        assert r2.order_id == "PAPER-000002"
        assert r1.order_id != r2.order_id


class TestMaxPositions:
    def test_max_positions_blocks_new_orders(self):
        b = PaperBroker(symbol="EURUSD=X", capital=10000, max_positions=2)
        b.update_price("EURUSD=X", bid=1.0850, ask=1.0852)
        b.place_order("EURUSD=X", OrderSide.BUY, 1.0, sl=1.0800, tp=1.0900)
        b.place_order("EURUSD=X", OrderSide.SELL, 1.0, sl=1.0900, tp=1.0800)
        r3 = b.place_order("EURUSD=X", OrderSide.BUY, 1.0, sl=1.0800, tp=1.0900)
        assert not r3.success
        assert "Max positions" in r3.message


class TestClosePosition:
    def test_close_at_specified_price(self, broker):
        r = broker.place_order("EURUSD=X", OrderSide.BUY, 1.0, sl=1.0800, tp=1.0900)
        close_r = broker.close_position(r.order_id, exit_price=1.0900, exit_reason="TP")
        assert close_r.success
        assert close_r.price == pytest.approx(1.0900, abs=1e-6)

    def test_close_removes_position(self, broker):
        r = broker.place_order("EURUSD=X", OrderSide.BUY, 1.0, sl=1.0800, tp=1.0900)
        broker.close_position(r.order_id, exit_price=1.0900)
        assert len(broker.get_positions()) == 0

    def test_close_nonexistent_fails(self, broker):
        r = broker.close_position("FAKE-000001")
        assert not r.success
        assert "not found" in r.message


class TestGetPositions:
    def test_returns_dicts_with_required_keys(self, broker):
        broker.place_order("EURUSD=X", OrderSide.BUY, 1.0, sl=1.0800, tp=1.0900)
        positions = broker.get_positions()
        assert len(positions) == 1
        pos = positions[0]
        required_keys = {"order_id", "symbol", "side", "entry_price", "volume", "sl", "tp", "unrealized_pnl"}
        assert required_keys.issubset(pos.keys())


class TestAccountInfo:
    def test_initial_state(self):
        b = PaperBroker(symbol="EURUSD=X", capital=10000)
        info = b.get_account_info()
        assert info["balance"] == 10000
        assert info["equity"] == 10000
        assert info["open_positions"] == 0
        assert info["total_pnl"] == 0

    def test_after_profit(self, broker):
        r = broker.place_order("EURUSD=X", OrderSide.BUY, 0.0001, sl=1.0800, tp=1.0900)
        entry = r.price
        exit_price = entry + 0.0050  # 50 pips up
        broker.close_position(r.order_id, exit_price=exit_price)
        info = broker.get_account_info()
        assert info["total_pnl"] > 0

    def test_after_loss(self, broker):
        r = broker.place_order("EURUSD=X", OrderSide.BUY, 0.0001, sl=1.0800, tp=1.0900)
        entry = r.price
        exit_price = entry - 0.0050  # 50 pips down
        broker.close_position(r.order_id, exit_price=exit_price)
        info = broker.get_account_info()
        assert info["total_pnl"] < 0


class TestRiskSizing:
    def test_risk_sizing_calculates_volume(self, broker):
        """Volume=0 triggers risk-based sizing and should produce a non-default value."""
        result = broker.place_order("EURUSD=X", OrderSide.BUY, 0, sl=1.0800, tp=1.0900)
        assert result.success
        assert result.volume > 0
        assert result.volume != 1.0  # not a fixed default

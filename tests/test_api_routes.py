"""Tests for FastAPI REST routes."""

import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, ".")

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_engine_manager
from src.api.state import EngineManager
from src.broker.paper import PaperBroker
from src.broker.base import OrderSide
from src.data.demo_feed import DemoFeed
from src.strategy.ema_crossover import EMACrossoverStrategy


@pytest.fixture
def mgr():
    return EngineManager()


@pytest.fixture
def client(mgr):
    app.dependency_overrides[get_engine_manager] = lambda: mgr
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAccountRoute:
    def test_no_broker(self, client):
        resp = client.get("/api/account")
        assert resp.status_code == 400

    def test_with_broker(self, client, mgr):
        broker = PaperBroker()
        mgr.broker = broker
        resp = client.get("/api/account")
        assert resp.status_code == 200
        data = resp.json()
        assert "balance" in data
        assert "equity" in data


class TestPositionsRoute:
    def test_no_broker(self, client):
        resp = client.get("/api/positions")
        assert resp.status_code == 400

    def test_empty_positions(self, client, mgr):
        mgr.broker = PaperBroker()
        resp = client.get("/api/positions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_close_position(self, client, mgr):
        broker = PaperBroker()
        broker.update_price("EURUSD=X", 1.085, 1.0852)
        broker.place_order("EURUSD=X", OrderSide.BUY, 0.001, sl=1.08, tp=1.09)
        mgr.broker = broker

        positions = broker.get_positions()
        order_id = positions[0]["order_id"]
        resp = client.post(f"/api/positions/{order_id}/close")
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"


class TestTradesRoute:
    def test_no_broker(self, client):
        resp = client.get("/api/trades")
        assert resp.status_code == 400

    def test_empty_trades(self, client, mgr):
        mgr.broker = PaperBroker()
        resp = client.get("/api/trades")
        assert resp.status_code == 200
        assert resp.json() == []


class TestCandlesRoute:
    def test_no_engine(self, client):
        resp = client.get("/api/candles")
        assert resp.status_code == 400


class TestStrategyRoute:
    @patch("src.engine.trading.TradingEngine.start")
    def test_start_stop(self, mock_start, client, mgr):
        resp = client.post("/api/strategy/start", json={
            "strategy": "ema_crossover",
            "symbol": "EURUSD=X",
            "timeframe": "1h",
            "broker": "paper",
            "capital": 10000,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"

        # Check status
        resp = client.get("/api/strategy/status")
        assert resp.status_code == 200
        status = resp.json()
        assert status["strategy"] == "ema_crossover"

    def test_start_unknown_strategy(self, client, mgr):
        resp = client.post("/api/strategy/start", json={
            "strategy": "nonexistent",
        })
        assert resp.status_code == 400

    def test_status_when_idle(self, client, mgr):
        resp = client.get("/api/strategy/status")
        assert resp.status_code == 200
        assert resp.json()["running"] is False

    @patch("src.engine.trading.TradingEngine.start")
    def test_update_params(self, mock_start, client, mgr):
        # Start first
        client.post("/api/strategy/start", json={
            "strategy": "ema_crossover",
            "symbol": "EURUSD=X",
            "timeframe": "1h",
            "broker": "paper",
        })
        resp = client.put("/api/strategy/params", json={"params": {"ema_fast": 5}})
        assert resp.status_code == 200
        assert resp.json()["params"]["ema_fast"] == 5

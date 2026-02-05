"""Tests for OandaBroker — mocked HTTP calls."""

import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

import pytest
import requests as req_lib

from src.broker.base import OrderSide
from src.broker.oanda import OandaBroker


def _make_broker():
    return OandaBroker(
        account_id="101-001-1234",
        api_token="test-token",
        environment="practice",
    )


class TestOandaBrokerProperties:
    def test_server_managed_sl_tp(self):
        broker = _make_broker()
        assert broker.server_managed_sl_tp is True


class TestPlaceOrder:
    @patch("src.broker.oanda.requests.request")
    def test_market_order_buy(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "orderFillTransaction": {
                "price": "1.08500",
                "tradeOpened": {"tradeID": "12345", "units": "10000"},
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_req.return_value = mock_resp

        broker = _make_broker()
        result = broker.place_order("EURUSD=X", OrderSide.BUY, 0.1, sl=1.0800, tp=1.0900)
        assert result.success
        assert result.order_id == "12345"
        assert result.price == 1.085

    @patch("src.broker.oanda.requests.request")
    def test_market_order_sell_units_negative(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "orderFillTransaction": {
                "price": "1.08500",
                "tradeOpened": {"tradeID": "12346", "units": "-10000"},
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_req.return_value = mock_resp

        broker = _make_broker()
        result = broker.place_order("EURUSD=X", OrderSide.SELL, 0.1, sl=1.0900, tp=1.0800)
        assert result.success
        # Check that the POST sent negative units
        call_args = mock_req.call_args
        body = call_args.kwargs.get("json") or call_args[1].get("json")
        units_sent = int(body["order"]["units"])
        assert units_sent < 0

    @patch("src.broker.oanda.requests.request")
    def test_order_rejection(self, mock_req):
        mock_resp = MagicMock()
        mock_error_resp = MagicMock()
        mock_error_resp.status_code = 400
        mock_error_resp.json.return_value = {"errorMessage": "Insufficient margin"}
        mock_resp.raise_for_status.side_effect = req_lib.exceptions.HTTPError(
            response=mock_error_resp
        )
        mock_req.return_value = mock_resp

        broker = _make_broker()
        result = broker.place_order("EURUSD=X", OrderSide.BUY, 0.1, sl=1.0800, tp=1.0900)
        assert not result.success
        assert "Insufficient margin" in result.message


class TestClosePosition:
    @patch("src.broker.oanda.requests.request")
    def test_close_success(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "orderFillTransaction": {
                "price": "1.08600",
                "units": "-10000",
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_req.return_value = mock_resp

        broker = _make_broker()
        result = broker.close_position("12345")
        assert result.success
        assert result.price == 1.086


class TestGetPositions:
    @patch("src.broker.oanda.requests.request")
    def test_returns_positions(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "trades": [
                {
                    "id": "100",
                    "instrument": "EUR_USD",
                    "currentUnits": "10000",
                    "price": "1.08500",
                    "stopLossOrder": {"price": "1.08000"},
                    "takeProfitOrder": {"price": "1.09000"},
                    "unrealizedPL": "5.00",
                    "openTime": "2024-01-15T10:00:00Z",
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_req.return_value = mock_resp

        broker = _make_broker()
        positions = broker.get_positions()
        assert len(positions) == 1
        assert positions[0]["side"] == "BUY"
        assert positions[0]["order_id"] == "100"


class TestGetAccountInfo:
    @patch("src.broker.oanda.requests.request")
    def test_returns_account(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "account": {
                "balance": "10000.00",
                "NAV": "10050.00",
                "openTradeCount": "1",
                "pl": "50.00",
                "marginUsed": "100.00",
                "marginAvailable": "9900.00",
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_req.return_value = mock_resp

        broker = _make_broker()
        info = broker.get_account_info()
        assert info["balance"] == 10000.0
        assert info["equity"] == 10050.0


class TestGetClosedTrades:
    @patch("src.broker.oanda.requests.request")
    def test_returns_closed(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "trades": [
                {
                    "id": "200",
                    "instrument": "EUR_USD",
                    "initialUnits": "10000",
                    "price": "1.08500",
                    "averageClosePrice": "1.08600",
                    "realizedPL": "10.00",
                    "openTime": "2024-01-15T10:00:00Z",
                    "closeTime": "2024-01-15T11:00:00Z",
                }
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_req.return_value = mock_resp

        broker = _make_broker()
        trades = broker.get_closed_trades()
        assert len(trades) == 1
        assert trades[0]["pnl"] == 10.0
        assert trades[0]["side"] == "BUY"


class TestRetryLogic:
    @patch("src.broker.oanda.time.sleep")
    @patch("src.broker.oanda.requests.request")
    def test_retry_on_connection_error(self, mock_req, mock_sleep):
        """Should retry on ConnectionError and succeed on second attempt."""
        mock_resp_ok = MagicMock()
        mock_resp_ok.json.return_value = {"account": {"balance": "10000", "NAV": "10000"}}
        mock_resp_ok.raise_for_status = MagicMock()

        mock_req.side_effect = [
            req_lib.exceptions.ConnectionError("Connection refused"),
            mock_resp_ok,
        ]

        broker = _make_broker()
        info = broker.get_account_info()
        assert info["balance"] == 10000.0
        assert mock_req.call_count == 2
        mock_sleep.assert_called_once_with(1)  # 2^0 = 1

    @patch("src.broker.oanda.time.sleep")
    @patch("src.broker.oanda.requests.request")
    def test_retry_on_5xx(self, mock_req, mock_sleep):
        """Should retry on 5xx server errors."""
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        http_err = req_lib.exceptions.HTTPError(response=mock_resp_500)
        mock_resp_500.raise_for_status.side_effect = http_err

        mock_resp_ok = MagicMock()
        mock_resp_ok.json.return_value = {"account": {"balance": "10000", "NAV": "10000"}}
        mock_resp_ok.raise_for_status = MagicMock()

        mock_req.side_effect = [mock_resp_500, mock_resp_ok]

        broker = _make_broker()
        info = broker.get_account_info()
        assert info["balance"] == 10000.0
        assert mock_req.call_count == 2

    @patch("src.broker.oanda.time.sleep")
    @patch("src.broker.oanda.requests.request")
    def test_no_retry_on_4xx(self, mock_req, mock_sleep):
        """Should NOT retry on 4xx client errors."""
        mock_resp_401 = MagicMock()
        mock_resp_401.status_code = 401
        http_err = req_lib.exceptions.HTTPError(response=mock_resp_401)
        mock_resp_401.raise_for_status.side_effect = http_err

        mock_req.return_value = mock_resp_401

        broker = _make_broker()
        with pytest.raises(req_lib.exceptions.HTTPError):
            broker._api("GET", "/summary")
        assert mock_req.call_count == 1
        mock_sleep.assert_not_called()

    @patch("src.broker.oanda.time.sleep")
    @patch("src.broker.oanda.requests.request")
    def test_max_retries_exhausted(self, mock_req, mock_sleep):
        """Should raise after exhausting max retries."""
        mock_req.side_effect = req_lib.exceptions.ConnectionError("Connection refused")

        broker = _make_broker()
        with pytest.raises(req_lib.exceptions.ConnectionError):
            broker._api("GET", "/summary")
        assert mock_req.call_count == 3  # default max_retries=3

    @patch("src.broker.oanda.time.sleep")
    @patch("src.broker.oanda.requests.request")
    def test_place_order_catches_request_exception(self, mock_req, mock_sleep):
        """place_order should catch RequestException (not just HTTPError)."""
        mock_req.side_effect = req_lib.exceptions.ConnectionError("Connection refused")

        broker = _make_broker()
        result = broker.place_order("EURUSD=X", OrderSide.BUY, 0.1, sl=1.0800, tp=1.0900)
        assert not result.success
        assert "Connection refused" in result.message

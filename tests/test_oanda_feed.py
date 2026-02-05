"""Tests for OandaFeed — mocked HTTP calls."""

import sys
import threading
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, ".")

import pytest
import pandas as pd
import requests as req_lib

from src.data.oanda_feed import OandaFeed


def _make_feed():
    return OandaFeed(
        account_id="101-001-1234",
        api_token="test-token",
        environment="practice",
    )


class TestGetHistorical:
    @patch("src.data.oanda_feed.requests.get")
    def test_returns_dataframe(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "candles": [
                {
                    "complete": True,
                    "time": "2024-01-15T10:00:00.000000000Z",
                    "mid": {"o": "1.08500", "h": "1.08600", "l": "1.08400", "c": "1.08550"},
                    "volume": 100,
                },
                {
                    "complete": True,
                    "time": "2024-01-15T11:00:00.000000000Z",
                    "mid": {"o": "1.08550", "h": "1.08700", "l": "1.08500", "c": "1.08650"},
                    "volume": 150,
                },
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        feed = _make_feed()
        df = feed.get_historical("EURUSD=X", "1h", "2024-01-15", "2024-01-16")
        assert len(df) == 2
        assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
        assert df["open"].iloc[0] == 1.085

    @patch("src.data.oanda_feed.requests.get")
    def test_skips_incomplete_candles(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "candles": [
                {
                    "complete": True,
                    "time": "2024-01-15T10:00:00.000000000Z",
                    "mid": {"o": "1.08500", "h": "1.08600", "l": "1.08400", "c": "1.08550"},
                    "volume": 100,
                },
                {
                    "complete": False,
                    "time": "2024-01-15T11:00:00.000000000Z",
                    "mid": {"o": "1.08550", "h": "1.08700", "l": "1.08500", "c": "1.08650"},
                    "volume": 50,
                },
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        feed = _make_feed()
        df = feed.get_historical("EURUSD=X", "1h", "2024-01-15", "2024-01-16")
        assert len(df) == 1

    @patch("src.data.oanda_feed.requests.get")
    def test_empty_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"candles": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        feed = _make_feed()
        df = feed.get_historical("EURUSD=X", "1h", "2024-01-15", "2024-01-16")
        assert df.empty

    @patch("src.data.oanda_feed.requests.get")
    def test_symbol_mapping(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"candles": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        feed = _make_feed()
        feed.get_historical("EURUSD=X", "1h", "2024-01-15", "2024-01-16")
        url_called = mock_get.call_args[0][0]
        assert "EUR_USD" in url_called


class TestStreamPrices:
    @patch("src.data.oanda_feed.requests.get")
    def test_parses_price_events(self, mock_get):
        """Test that stream_prices calls callback with parsed tick data."""
        lines = [
            b'{"type":"PRICE","time":"2024-01-15T10:00:00Z","bids":[{"price":"1.08500"}],"asks":[{"price":"1.08520"}]}',
            b'{"type":"HEARTBEAT","time":"2024-01-15T10:00:05Z"}',
            b'{"type":"PRICE","time":"2024-01-15T10:00:10Z","bids":[{"price":"1.08510"}],"asks":[{"price":"1.08530"}]}',
        ]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_lines.return_value = iter(lines)
        mock_get.return_value = mock_resp

        feed = _make_feed()
        received = []

        def cb(tick):
            received.append(tick)
            if len(received) >= 2:
                feed.request_stop()

        feed.stream_prices("EURUSD=X", cb)

        assert len(received) == 2
        assert received[0]["bid"] == 1.085
        assert received[1]["ask"] == 1.0853

    @patch("src.data.oanda_feed.requests.get")
    def test_skips_heartbeats(self, mock_get):
        lines = [
            b'{"type":"HEARTBEAT","time":"2024-01-15T10:00:00Z"}',
        ]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.iter_lines.return_value = iter(lines)
        mock_get.return_value = mock_resp

        feed = _make_feed()
        feed._max_reconnect_attempts = 1  # Don't loop forever
        received = []

        feed.stream_prices("EURUSD=X", lambda t: received.append(t))

        assert len(received) == 0


class TestStreamReconnection:
    @patch("src.data.oanda_feed.requests.get")
    def test_exponential_backoff(self, mock_get):
        """Should use exponential backoff between reconnection attempts."""
        feed = _make_feed()
        feed._max_reconnect_attempts = 3
        feed._base_backoff = 1.0
        feed._max_backoff = 60.0

        mock_get.side_effect = req_lib.exceptions.ConnectionError("Connection refused")

        # Track backoff waits
        waits = []
        orig_wait = feed._stop_event.wait
        def track_wait(timeout):
            waits.append(timeout)
            return False  # not stopped
        feed._stop_event.wait = track_wait

        feed.stream_prices("EURUSD=X", lambda t: None)

        assert mock_get.call_count == 3
        # Backoffs: 1.0, 2.0 (only 2 waits before 3rd attempt fails)
        assert len(waits) == 2
        assert waits[0] == 1.0
        assert waits[1] == 2.0

    @patch("src.data.oanda_feed.requests.get")
    def test_auth_error_no_retry(self, mock_get):
        """4xx errors should stop immediately without retrying."""
        feed = _make_feed()
        feed._max_reconnect_attempts = 5

        mock_resp_401 = MagicMock()
        mock_resp_401.status_code = 401
        http_err = req_lib.exceptions.HTTPError(response=mock_resp_401)
        mock_resp_401.raise_for_status.side_effect = http_err
        mock_get.return_value = mock_resp_401

        feed.stream_prices("EURUSD=X", lambda t: None)

        assert mock_get.call_count == 1  # Only one attempt

    @patch("src.data.oanda_feed.requests.get")
    def test_backoff_resets_on_success(self, mock_get):
        """Backoff should reset after a successful connection."""
        feed = _make_feed()
        feed._max_reconnect_attempts = 5
        feed._base_backoff = 1.0

        # First call: fails with network error
        # Second call: succeeds but stream eventually fails
        # Third call: fails again
        lines = [
            b'{"type":"PRICE","time":"2024-01-15T10:00:00Z","bids":[{"price":"1.08500"}],"asks":[{"price":"1.08520"}]}',
        ]

        mock_resp_ok = MagicMock()
        mock_resp_ok.raise_for_status = MagicMock()
        mock_resp_ok.iter_lines.return_value = iter(lines)

        call_count = [0]
        waits = []

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise req_lib.exceptions.ConnectionError("fail")
            elif call_count[0] == 2:
                return mock_resp_ok
            else:
                # After stream ends (lines exhausted), next reconnect fails
                raise req_lib.exceptions.ConnectionError("fail again")

        mock_get.side_effect = side_effect

        def track_wait(timeout):
            waits.append(timeout)
            if len(waits) >= 3:
                feed._stop_event.set()
                return True
            return False
        feed._stop_event.wait = track_wait

        feed.stream_prices("EURUSD=X", lambda t: None)

        # After successful connection (call 2), backoff should reset
        # So wait after call 3 should be base_backoff again (1.0)
        assert waits[0] == 1.0  # first failure
        assert waits[1] == 1.0  # after success+disconnect, backoff reset

    @patch("src.data.oanda_feed.requests.get")
    def test_stop_event_interrupts(self, mock_get):
        """request_stop() should interrupt the reconnection loop."""
        feed = _make_feed()
        feed._max_reconnect_attempts = 100

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 2:
                feed.request_stop()
            raise req_lib.exceptions.ConnectionError("fail")

        mock_get.side_effect = side_effect

        # Make wait return True immediately when stop is set
        orig_wait = feed._stop_event.wait
        feed.stream_prices("EURUSD=X", lambda t: None)

        # Should have stopped after a few calls, not 100
        assert call_count[0] < 10

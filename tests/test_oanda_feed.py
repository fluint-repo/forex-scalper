"""Tests for OandaFeed — mocked HTTP calls."""

import sys
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, ".")

import pytest
import pandas as pd

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
                raise StopIteration  # break out

        try:
            feed.stream_prices("EURUSD=X", cb)
        except StopIteration:
            pass

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
        received = []

        try:
            feed.stream_prices("EURUSD=X", lambda t: received.append(t))
        except StopIteration:
            pass

        assert len(received) == 0

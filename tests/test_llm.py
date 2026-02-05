"""Tests for LLM Trade Confidence Assessment System."""

import json
import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.llm.anthropic import AnthropicProvider
from src.llm.assessor import AssessmentResult, LLMAssessor
from src.llm.base import LLMAssessment, LLMProvider
from src.llm.grok import GrokProvider
from src.llm.openai import OpenAIProvider


# --- Mock Provider ---

class MockLLMProvider(LLMProvider):
    """Configurable mock for orchestrator tests."""

    def __init__(self, name_: str = "mock", confidence: float = 80.0,
                 reasoning: str = "looks good", should_fail: bool = False,
                 delay: float = 0.0):
        self._name = name_
        self._confidence = confidence
        self._reasoning = reasoning
        self._should_fail = should_fail
        self._delay = delay

    @property
    def name(self) -> str:
        return self._name

    def assess(self, prompt: str, timeout: float = 10.0) -> LLMAssessment:
        if self._delay:
            time.sleep(self._delay)
        if self._should_fail:
            return LLMAssessment(
                provider=self._name, confidence=0, reasoning="",
                success=False, error="mock failure",
            )
        return LLMAssessment(
            provider=self._name, confidence=self._confidence,
            reasoning=self._reasoning, success=True,
        )


# --- JSON Parsing Tests ---

class TestParseJsonResponse:
    def test_clean_json(self):
        text = '{"confidence": 85, "reasoning": "strong trend"}'
        result = LLMProvider.parse_json_response(text)
        assert result["confidence"] == 85
        assert result["reasoning"] == "strong trend"

    def test_markdown_wrapped_json(self):
        text = '```json\n{"confidence": 72, "reasoning": "moderate"}\n```'
        result = LLMProvider.parse_json_response(text)
        assert result["confidence"] == 72

    def test_markdown_no_lang_tag(self):
        text = '```\n{"confidence": 60, "reasoning": "weak"}\n```'
        result = LLMProvider.parse_json_response(text)
        assert result["confidence"] == 60

    def test_clamp_above_100(self):
        text = '{"confidence": 150, "reasoning": "over"}'
        result = LLMProvider.parse_json_response(text)
        assert result["confidence"] == 100.0

    def test_clamp_below_0(self):
        text = '{"confidence": -20, "reasoning": "under"}'
        result = LLMProvider.parse_json_response(text)
        assert result["confidence"] == 0.0

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            LLMProvider.parse_json_response("not json at all")


# --- Orchestrator Tests ---

class TestLLMAssessor:
    def test_all_above_threshold_approves(self):
        providers = [
            MockLLMProvider("a", confidence=80),
            MockLLMProvider("b", confidence=90),
        ]
        assessor = LLMAssessor(providers, threshold=70)
        result = assessor.assess_trade({"side": "BUY", "sl": 1.0, "tp": 1.1, "entry_price": 1.05})
        assert result.approved is True
        assert result.mean_confidence == 85.0
        assert len(result.assessments) == 2

    def test_below_threshold_blocks(self):
        providers = [
            MockLLMProvider("a", confidence=50),
            MockLLMProvider("b", confidence=60),
        ]
        assessor = LLMAssessor(providers, threshold=70)
        result = assessor.assess_trade({"side": "BUY", "sl": 1.0, "tp": 1.1, "entry_price": 1.05})
        assert result.approved is False
        assert result.mean_confidence == 55.0

    def test_partial_failure_uses_remaining(self):
        providers = [
            MockLLMProvider("a", confidence=80),
            MockLLMProvider("b", should_fail=True),
        ]
        assessor = LLMAssessor(providers, threshold=70)
        result = assessor.assess_trade({"side": "BUY", "sl": 1.0, "tp": 1.1, "entry_price": 1.05})
        assert result.approved is True
        assert result.mean_confidence == 80.0
        assert result.all_failed is False

    def test_all_fail_allows_trade(self):
        providers = [
            MockLLMProvider("a", should_fail=True),
            MockLLMProvider("b", should_fail=True),
        ]
        assessor = LLMAssessor(providers, threshold=70)
        result = assessor.assess_trade({"side": "BUY", "sl": 1.0, "tp": 1.1, "entry_price": 1.05})
        assert result.approved is True
        assert result.all_failed is True

    def test_no_providers_auto_approves(self):
        assessor = LLMAssessor([], threshold=70)
        result = assessor.assess_trade({"side": "BUY", "sl": 1.0, "tp": 1.1, "entry_price": 1.05})
        assert result.approved is True
        assert result.mean_confidence == 100.0

    def test_configurable_threshold(self):
        providers = [MockLLMProvider("a", confidence=55)]
        # Low threshold: approve
        assessor = LLMAssessor(providers, threshold=50)
        result = assessor.assess_trade({"side": "BUY"})
        assert result.approved is True
        # High threshold: block
        assessor = LLMAssessor(providers, threshold=60)
        result = assessor.assess_trade({"side": "BUY"})
        assert result.approved is False

    def test_prompt_contains_signal_info(self):
        """Verify the prompt includes key signal data."""
        signal = {"side": "SELL", "entry_price": 1.2345, "sl": 1.2400, "tp": 1.2200}
        prompt = LLMAssessor._build_prompt(signal)
        assert "SELL" in prompt
        assert "1.2345" in prompt
        assert "1.24" in prompt
        assert "1.22" in prompt
        assert "Risk/Reward" in prompt

    def test_prompt_includes_indicators(self):
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="h"),
            "open": [1.1, 1.2, 1.3, 1.4, 1.5],
            "high": [1.15, 1.25, 1.35, 1.45, 1.55],
            "low": [1.05, 1.15, 1.25, 1.35, 1.45],
            "close": [1.12, 1.22, 1.32, 1.42, 1.52],
            "volume": [100, 200, 300, 400, 500],
            "rsi": [30, 40, 50, 60, 70],
            "atr": [0.01, 0.02, 0.03, 0.04, 0.05],
        })
        prompt = LLMAssessor._build_prompt({"side": "BUY"}, df=df)
        assert "rsi:" in prompt
        assert "atr:" in prompt
        assert "Recent Candles" in prompt

    def test_prompt_includes_account(self):
        account = {"balance": 10000, "equity": 10500, "open_positions": 2}
        prompt = LLMAssessor._build_prompt({"side": "BUY"}, account=account)
        assert "10000" in prompt
        assert "10500" in prompt

    def test_parallel_execution(self):
        """Verify providers are called in parallel (total time < sum of delays)."""
        providers = [
            MockLLMProvider("a", confidence=80, delay=0.2),
            MockLLMProvider("b", confidence=80, delay=0.2),
            MockLLMProvider("c", confidence=80, delay=0.2),
        ]
        assessor = LLMAssessor(providers, threshold=70)
        start = time.time()
        result = assessor.assess_trade({"side": "BUY"})
        elapsed = time.time() - start
        assert result.approved is True
        # If sequential, would take >= 0.6s. Parallel should take ~0.2s
        assert elapsed < 0.5

    def test_threshold_stored_in_result(self):
        assessor = LLMAssessor([MockLLMProvider("a", confidence=80)], threshold=65)
        result = assessor.assess_trade({"side": "BUY"})
        assert result.threshold == 65


# --- Provider Tests (mocked requests) ---

def _mock_response(status_code=200, json_data=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


class TestAnthropicProvider:
    def test_missing_api_key(self):
        provider = AnthropicProvider(api_key="")
        result = provider.assess("test prompt")
        assert result.success is False
        assert "Missing" in result.error

    @patch("src.llm.anthropic.requests.post")
    def test_successful_assessment(self, mock_post):
        mock_post.return_value = _mock_response(200, {
            "content": [{"text": '{"confidence": 75, "reasoning": "decent setup"}'}]
        })
        provider = AnthropicProvider(api_key="test-key")
        result = provider.assess("test prompt")
        assert result.success is True
        assert result.confidence == 75
        assert result.reasoning == "decent setup"
        assert result.provider == "anthropic"

    @patch("src.llm.anthropic.requests.post")
    def test_http_error(self, mock_post):
        mock_post.return_value = _mock_response(500, {})
        provider = AnthropicProvider(api_key="test-key")
        result = provider.assess("test prompt")
        assert result.success is False

    @patch("src.llm.anthropic.requests.post")
    def test_timeout(self, mock_post):
        mock_post.side_effect = Exception("Connection timed out")
        provider = AnthropicProvider(api_key="test-key")
        result = provider.assess("test prompt")
        assert result.success is False
        assert "timed out" in result.error


class TestOpenAIProvider:
    def test_missing_api_key(self):
        provider = OpenAIProvider(api_key="")
        result = provider.assess("test prompt")
        assert result.success is False

    @patch("src.llm.openai.requests.post")
    def test_successful_assessment(self, mock_post):
        mock_post.return_value = _mock_response(200, {
            "choices": [{"message": {"content": '{"confidence": 82, "reasoning": "good momentum"}'}}]
        })
        provider = OpenAIProvider(api_key="test-key")
        result = provider.assess("test prompt")
        assert result.success is True
        assert result.confidence == 82
        assert result.provider == "openai"

    @patch("src.llm.openai.requests.post")
    def test_http_error(self, mock_post):
        mock_post.return_value = _mock_response(401, {})
        provider = OpenAIProvider(api_key="test-key")
        result = provider.assess("test prompt")
        assert result.success is False


class TestGrokProvider:
    def test_missing_api_key(self):
        provider = GrokProvider(api_key="")
        result = provider.assess("test prompt")
        assert result.success is False

    @patch("src.llm.grok.requests.post")
    def test_successful_assessment(self, mock_post):
        mock_post.return_value = _mock_response(200, {
            "choices": [{"message": {"content": '{"confidence": 68, "reasoning": "risky"}'}}]
        })
        provider = GrokProvider(api_key="test-key")
        result = provider.assess("test prompt")
        assert result.success is True
        assert result.confidence == 68
        assert result.provider == "grok"

    @patch("src.llm.grok.requests.post")
    def test_markdown_wrapped_response(self, mock_post):
        mock_post.return_value = _mock_response(200, {
            "choices": [{"message": {"content": '```json\n{"confidence": 90, "reasoning": "strong"}\n```'}}]
        })
        provider = GrokProvider(api_key="test-key")
        result = provider.assess("test prompt")
        assert result.success is True
        assert result.confidence == 90


# --- TradingEngine Integration Tests ---

class TestTradingEngineIntegration:
    """Test that TradingEngine correctly uses llm_assessor."""

    def _make_engine(self, llm_assessor=None):
        """Create a minimal TradingEngine with mocks."""
        from src.engine.trading import TradingEngine

        strategy = MagicMock()
        strategy.name = "test_strat"
        feed = MagicMock()
        feed.get_historical.return_value = pd.DataFrame()
        broker = MagicMock()
        broker.server_managed_sl_tp = False
        broker.get_positions.return_value = []

        engine = TradingEngine(
            strategy=strategy,
            feed=feed,
            broker=broker,
            symbol="EURUSD=X",
            timeframe="1h",
            llm_assessor=llm_assessor,
        )
        return engine

    def test_no_assessor_backward_compat(self):
        """Engine with llm_assessor=None should work fine."""
        engine = self._make_engine(llm_assessor=None)
        assert engine.llm_assessor is None

    def test_assessor_stored(self):
        assessor = LLMAssessor([MockLLMProvider("a", confidence=80)], threshold=70)
        engine = self._make_engine(llm_assessor=assessor)
        assert engine.llm_assessor is assessor

    @staticmethod
    def _make_varied_df(n=250):
        """Create a DataFrame with varying prices so indicators compute non-NaN."""
        import numpy as np
        np.random.seed(42)
        base = 1.1
        close = base + np.cumsum(np.random.randn(n) * 0.001)
        return pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
            "open": close - 0.0005,
            "high": close + 0.002,
            "low": close - 0.002,
            "close": close,
            "volume": [100] * n,
        })

    def test_llm_blocks_trade(self):
        """When LLM confidence is below threshold, trade should be blocked."""
        assessor = LLMAssessor(
            [MockLLMProvider("a", confidence=30)], threshold=70,
        )
        engine = self._make_engine(llm_assessor=assessor)
        engine._running.set()

        df = self._make_varied_df()
        engine._aggregator.seed_history(df)

        # Strategy returns a BUY signal
        def gen_signals(d):
            d["signal"] = 0
            d.iloc[-1, d.columns.get_loc("signal")] = 1
            d["sl"] = d["close"] - 0.005
            d["tp"] = d["close"] + 0.01
            return d

        engine.strategy.generate_signals.side_effect = gen_signals

        candle = {"timestamp": "2024-01-10", "open": 1.1, "high": 1.15, "low": 1.05, "close": 1.12}
        engine._on_candle_close(candle)

        # Trade should NOT have been placed
        engine.broker.place_order.assert_not_called()

    def test_llm_allows_trade(self):
        """When LLM confidence is above threshold, trade should proceed."""
        assessor = LLMAssessor(
            [MockLLMProvider("a", confidence=90)], threshold=70,
        )
        engine = self._make_engine(llm_assessor=assessor)
        engine._running.set()

        df = self._make_varied_df()
        engine._aggregator.seed_history(df)

        def gen_signals(d):
            d["signal"] = 0
            d.iloc[-1, d.columns.get_loc("signal")] = 1
            d["sl"] = d["close"] - 0.005
            d["tp"] = d["close"] + 0.01
            return d

        engine.strategy.generate_signals.side_effect = gen_signals
        engine.broker.place_order.return_value = MagicMock(success=True, order_id="123", price=1.12, volume=1000)

        candle = {"timestamp": "2024-01-10", "open": 1.1, "high": 1.15, "low": 1.05, "close": 1.12}
        engine._on_candle_close(candle)

        # Trade should have been placed
        engine.broker.place_order.assert_called_once()

"""Anthropic Claude LLM provider for trade confidence assessment."""

from __future__ import annotations

import requests

from src.llm.base import LLMAssessment, LLMProvider
from src.utils.logger import get_logger

log = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    """Calls Anthropic Messages API for trade assessment."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return "anthropic"

    def assess(self, prompt: str, timeout: float = 10.0) -> LLMAssessment:
        if not self._api_key:
            return LLMAssessment(
                provider=self.name, confidence=0, reasoning="",
                success=False, error="Missing ANTHROPIC_API_KEY",
            )

        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 256,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=timeout,
            )
            resp.raise_for_status()

            data = resp.json()
            text = data["content"][0]["text"]
            parsed = self.parse_json_response(text)

            return LLMAssessment(
                provider=self.name,
                confidence=parsed.get("confidence", 0),
                reasoning=parsed.get("reasoning", ""),
                success=True,
            )
        except Exception as e:
            log.warning("anthropic_assess_failed", error=str(e))
            return LLMAssessment(
                provider=self.name, confidence=0, reasoning="",
                success=False, error=str(e),
            )

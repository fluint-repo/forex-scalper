"""xAI Grok LLM provider for trade confidence assessment."""

from __future__ import annotations

import requests

from src.llm.base import LLMAssessment, LLMProvider
from src.utils.logger import get_logger

log = get_logger(__name__)


class GrokProvider(LLMProvider):
    """Calls xAI Grok API (OpenAI-compatible) for trade assessment."""

    def __init__(self, api_key: str, model: str = "grok-3") -> None:
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return "grok"

    def assess(self, prompt: str, timeout: float = 10.0) -> LLMAssessment:
        if not self._api_key:
            return LLMAssessment(
                provider=self.name, confidence=0, reasoning="",
                success=False, error="Missing XAI_API_KEY",
            )

        try:
            resp = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 256,
                    "messages": [
                        {"role": "system", "content": "Respond only with valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=timeout,
            )
            resp.raise_for_status()

            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            parsed = self.parse_json_response(text)

            return LLMAssessment(
                provider=self.name,
                confidence=parsed.get("confidence", 0),
                reasoning=parsed.get("reasoning", ""),
                success=True,
            )
        except Exception as e:
            log.warning("grok_assess_failed", error=str(e))
            return LLMAssessment(
                provider=self.name, confidence=0, reasoning="",
                success=False, error=str(e),
            )

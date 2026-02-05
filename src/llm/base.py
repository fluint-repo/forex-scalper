"""Abstract LLM provider and shared types for trade confidence assessment."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMAssessment:
    provider: str
    confidence: float
    reasoning: str
    success: bool
    error: str = ""


class LLMProvider(ABC):
    """Base class for LLM trade confidence providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def assess(self, prompt: str, timeout: float = 10.0) -> LLMAssessment:
        """Assess a trade signal. Must not raise — returns success=False on error."""
        ...

    @staticmethod
    def parse_json_response(text: str) -> dict:
        """Extract JSON from LLM response, handling markdown code fences."""
        # Strip markdown code fences if present
        stripped = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
        stripped = re.sub(r"\n?```\s*$", "", stripped)

        data = json.loads(stripped)

        # Clamp confidence to 0-100
        if "confidence" in data:
            data["confidence"] = max(0.0, min(100.0, float(data["confidence"])))

        return data

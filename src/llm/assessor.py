"""LLMAssessor — orchestrates parallel LLM trade confidence assessment."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import pandas as pd

from src.llm.base import LLMAssessment, LLMProvider
from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class AssessmentResult:
    assessments: list[LLMAssessment] = field(default_factory=list)
    mean_confidence: float = 0.0
    approved: bool = True
    all_failed: bool = False
    threshold: float = 70.0


class LLMAssessor:
    """Calls multiple LLM providers in parallel and aggregates confidence scores."""

    def __init__(
        self,
        providers: list[LLMProvider],
        threshold: float = 70.0,
        timeout: float = 10.0,
    ) -> None:
        self.providers = providers
        self.threshold = threshold
        self.timeout = timeout

    def assess_trade(
        self,
        signal: dict,
        df: pd.DataFrame | None = None,
        account: dict | None = None,
    ) -> AssessmentResult:
        """Assess a trade signal using all configured providers in parallel."""
        if not self.providers:
            return AssessmentResult(
                mean_confidence=100.0, approved=True, threshold=self.threshold,
            )

        prompt = self._build_prompt(signal, df, account)

        # Call all providers in parallel
        assessments: list[LLMAssessment] = []
        with ThreadPoolExecutor(max_workers=len(self.providers)) as pool:
            futures = {
                pool.submit(p.assess, prompt, self.timeout): p
                for p in self.providers
            }
            for future in as_completed(futures):
                try:
                    assessments.append(future.result())
                except Exception as e:
                    provider = futures[future]
                    assessments.append(LLMAssessment(
                        provider=provider.name, confidence=0, reasoning="",
                        success=False, error=str(e),
                    ))

        # Aggregate results
        successful = [a for a in assessments if a.success]
        all_failed = len(successful) == 0

        if all_failed:
            # Fail-open: allow trade if all providers failed
            log.warning("llm_all_providers_failed", count=len(assessments))
            return AssessmentResult(
                assessments=assessments,
                mean_confidence=0.0,
                approved=True,
                all_failed=True,
                threshold=self.threshold,
            )

        mean_confidence = sum(a.confidence for a in successful) / len(successful)
        approved = mean_confidence >= self.threshold

        log.info(
            "llm_assessment_complete",
            mean_confidence=round(mean_confidence, 1),
            approved=approved,
            providers_ok=len(successful),
            providers_failed=len(assessments) - len(successful),
        )

        return AssessmentResult(
            assessments=assessments,
            mean_confidence=mean_confidence,
            approved=approved,
            all_failed=False,
            threshold=self.threshold,
        )

    @staticmethod
    def _build_prompt(
        signal: dict,
        df: pd.DataFrame | None = None,
        account: dict | None = None,
    ) -> str:
        """Build the assessment prompt with signal context, indicators, and price action."""
        parts = [
            "You are a forex trading risk assessor. Evaluate the following trade signal "
            "and respond with ONLY a JSON object: {\"confidence\": <0-100>, \"reasoning\": \"<1-2 sentences>\"}",
            "",
            "## Trade Signal",
            f"Direction: {signal.get('side', 'N/A')}",
            f"Entry Price: {signal.get('entry_price', 'N/A')}",
            f"Stop Loss: {signal.get('sl', 'N/A')}",
            f"Take Profit: {signal.get('tp', 'N/A')}",
        ]

        # Risk/reward ratio
        sl = signal.get("sl")
        tp = signal.get("tp")
        entry = signal.get("entry_price")
        if sl is not None and tp is not None and entry is not None:
            sl_dist = abs(entry - sl)
            tp_dist = abs(tp - entry)
            rr = round(tp_dist / sl_dist, 2) if sl_dist > 0 else 0
            parts.append(f"Risk/Reward Ratio: {rr}")

        # Indicators from the last row of the DataFrame
        if df is not None and not df.empty:
            last = df.iloc[-1]
            parts.append("")
            parts.append("## Indicators")
            for col in ("rsi", "macd", "macd_signal", "macd_hist",
                         "bb_upper", "bb_middle", "bb_lower",
                         "ema_9", "ema_21", "ema_50", "ema_200", "atr"):
                if col in last.index and pd.notna(last[col]):
                    parts.append(f"{col}: {round(float(last[col]), 5)}")

            # Last 10 candles for trend context
            recent = df.tail(10)
            parts.append("")
            parts.append("## Recent Candles (last 10)")
            for _, row in recent.iterrows():
                ts = row.get("timestamp", "")
                parts.append(
                    f"  {ts} O={round(float(row['open']),5)} H={round(float(row['high']),5)} "
                    f"L={round(float(row['low']),5)} C={round(float(row['close']),5)} "
                    f"V={row.get('volume', 0)}"
                )

        if account:
            parts.append("")
            parts.append("## Account")
            parts.append(f"Balance: {account.get('balance', 'N/A')}")
            parts.append(f"Equity: {account.get('equity', 'N/A')}")
            parts.append(f"Open Positions: {account.get('open_positions', 'N/A')}")

        return "\n".join(parts)

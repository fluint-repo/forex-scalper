"""Pydantic request/response models for the API."""

from pydantic import BaseModel


class AccountResponse(BaseModel):
    balance: float
    equity: float
    open_positions: int
    total_pnl: float
    margin_used: float = 0.0
    margin_available: float = 0.0


class PositionResponse(BaseModel):
    order_id: str
    symbol: str
    side: str
    entry_price: float
    volume: float
    sl: float
    tp: float
    entry_time: str
    unrealized_pnl: float


class TradeResponse(BaseModel):
    strategy_name: str = ""
    symbol: str
    timeframe: str = ""
    side: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    volume: float
    pnl: float
    sl: float = 0.0
    tp: float = 0.0
    exit_reason: str = ""


class CandleResponse(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class StrategyStartRequest(BaseModel):
    strategy: str = "ema_crossover"
    symbol: str = "EURUSD=X"
    timeframe: str = "1h"
    broker: str = "paper"
    capital: float = 10000.0


class StrategyStatusResponse(BaseModel):
    running: bool
    strategy: str = ""
    symbol: str = ""
    timeframe: str = ""
    broker: str = ""


class StrategyParamsUpdate(BaseModel):
    params: dict


class LLMProviderAssessment(BaseModel):
    provider: str
    confidence: float
    reasoning: str
    success: bool
    error: str = ""


class LLMAssessmentResponse(BaseModel):
    mean_confidence: float
    approved: bool
    threshold: float
    all_failed: bool
    assessments: list[LLMProviderAssessment]


class LLMStatusResponse(BaseModel):
    enabled: bool
    threshold: float
    timeout: float
    providers: list[str]

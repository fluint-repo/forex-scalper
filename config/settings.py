import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "forex")
DB_PASSWORD = os.getenv("DB_PASSWORD", "forex_dev_123")
DB_NAME = os.getenv("DB_NAME", "forex_scalper")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

DATA_FEED = os.getenv("DATA_FEED", "demo")

SYMBOLS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X"]
TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d"]
DEFAULT_HISTORY_DAYS = 60

# Indicator parameters
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2.0
EMA_PERIODS = [9, 21, 50, 200]
ATR_PERIOD = 14

# --- Phase 2: Strategy & Backtest Settings ---

# EMA Crossover strategy
EMA_FAST_PERIOD = 9
EMA_SLOW_PERIOD = 21
EMA_RSI_OVERSOLD = 30
EMA_RSI_OVERBOUGHT = 70
EMA_ATR_SL_MULT = 1.5
EMA_ATR_TP_MULT = 2.0

# Bollinger Band Reversion strategy
BB_RSI_OVERSOLD = 30
BB_RSI_OVERBOUGHT = 70
BB_ATR_SL_MULT = 1.5

# Backtest settings
INITIAL_CAPITAL = 10000
SPREAD_PIPS = 1.5
SLIPPAGE_PIPS = 0.5
RISK_PER_TRADE = 0.02
MAX_OPEN_POSITIONS = 3

# Pip values per symbol
PIP_VALUES = {
    "EURUSD=X": 0.0001,
    "GBPUSD=X": 0.0001,
    "USDJPY=X": 0.01,
}

# --- Phase 3: Live/Paper Trading Settings ---
CANDLE_HISTORY_SIZE = int(os.getenv("CANDLE_HISTORY_SIZE", "250"))
TICK_LOG_INTERVAL = int(os.getenv("TICK_LOG_INTERVAL", "60"))

# --- Phase 4: OANDA + API Settings ---

# OANDA v20 API
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
OANDA_API_TOKEN = os.getenv("OANDA_API_TOKEN", "")
OANDA_ENVIRONMENT = os.getenv("OANDA_ENVIRONMENT", "practice")  # practice or live

OANDA_BASE_URL = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}

OANDA_STREAM_URL = {
    "practice": "https://stream-fxpractice.oanda.com",
    "live": "https://stream-fxtrade.oanda.com",
}

# Map our symbols to OANDA instrument names
OANDA_SYMBOL_MAP = {
    "EURUSD=X": "EUR_USD",
    "GBPUSD=X": "GBP_USD",
    "USDJPY=X": "USD_JPY",
}

# OANDA granularity mapping
OANDA_GRANULARITY_MAP = {
    "1m": "M1",
    "5m": "M5",
    "15m": "M15",
    "1h": "H1",
    "4h": "H4",
    "1d": "D",
}

# FastAPI / WebSocket
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
WS_BROADCAST_INTERVAL = float(os.getenv("WS_BROADCAST_INTERVAL", "2.0"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

# --- Phase 5A: Risk Management ---
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "5.0"))
MAX_PORTFOLIO_RISK_PCT = float(os.getenv("MAX_PORTFOLIO_RISK_PCT", "10.0"))
MAX_CORRELATED_EXPOSURE = int(os.getenv("MAX_CORRELATED_EXPOSURE", "2"))
POSITION_SIZE_METHOD = os.getenv("POSITION_SIZE_METHOD", "fixed_risk")  # fixed_risk | kelly
KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.5"))
CORRELATION_GROUPS = {
    "USD_LONG": ["EURUSD=X_SELL", "GBPUSD=X_SELL", "USDJPY=X_BUY"],
    "USD_SHORT": ["EURUSD=X_BUY", "GBPUSD=X_BUY", "USDJPY=X_SELL"],
}

# --- Phase 5B: Notifications ---
NOTIFY_BACKENDS = [b for b in os.getenv("NOTIFY_BACKENDS", "").split(",") if b]
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SMTP_TO = os.getenv("SMTP_TO", "")
NOTIFY_EVENTS = os.getenv("NOTIFY_EVENTS", "order_filled,position_closed,circuit_breaker,engine_started,engine_stopped,stream_disconnected,stream_dead").split(",")

# --- Live Trading Readiness ---
API_KEY = os.getenv("API_KEY", "")
FEED_MAX_RECONNECT_ATTEMPTS = int(os.getenv("FEED_MAX_RECONNECT_ATTEMPTS", "20"))
FEED_BASE_BACKOFF = float(os.getenv("FEED_BASE_BACKOFF", "2.0"))
FEED_MAX_BACKOFF = float(os.getenv("FEED_MAX_BACKOFF", "60.0"))

# --- Phase 5E: Optimization ---
OPTIMIZATION_MAX_WORKERS = int(os.getenv("OPTIMIZATION_MAX_WORKERS", "4"))
WALK_FORWARD_SPLITS = int(os.getenv("WALK_FORWARD_SPLITS", "5"))
WALK_FORWARD_TRAIN_PCT = float(os.getenv("WALK_FORWARD_TRAIN_PCT", "0.7"))
MONTE_CARLO_SIMULATIONS = int(os.getenv("MONTE_CARLO_SIMULATIONS", "1000"))

# --- LLM Trade Confidence Assessment ---
LLM_ENABLED = os.getenv("LLM_ENABLED", "false").lower() in ("true", "1", "yes")
LLM_CONFIDENCE_THRESHOLD = float(os.getenv("LLM_CONFIDENCE_THRESHOLD", "70.0"))
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "10.0"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
LLM_ANTHROPIC_MODEL = os.getenv("LLM_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
LLM_OPENAI_MODEL = os.getenv("LLM_OPENAI_MODEL", "gpt-4o")
LLM_GROK_MODEL = os.getenv("LLM_GROK_MODEL", "grok-3")

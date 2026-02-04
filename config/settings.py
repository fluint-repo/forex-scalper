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

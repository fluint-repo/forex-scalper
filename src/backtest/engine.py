"""Backtesting engine with SL/TP, position tracking, spread/slippage."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from config.settings import (
    INITIAL_CAPITAL,
    MAX_OPEN_POSITIONS,
    PIP_VALUES,
    RISK_PER_TRADE,
    SLIPPAGE_PIPS,
    SPREAD_PIPS,
)


@dataclass
class BacktestConfig:
    capital: float = INITIAL_CAPITAL
    spread_pips: float = SPREAD_PIPS
    slippage_pips: float = SLIPPAGE_PIPS
    risk_per_trade: float = RISK_PER_TRADE
    max_positions: int = MAX_OPEN_POSITIONS
    use_risk_sizing: bool = True


@dataclass
class Position:
    side: str  # "BUY" or "SELL"
    entry_time: object
    entry_price: float
    volume: float
    sl: float
    tp: float
    bar_index: int


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity_curve: pd.Series
    initial_capital: float


class BacktestEngine:
    """Bar-by-bar backtesting engine with SL/TP management."""

    def __init__(
        self,
        config: BacktestConfig | None = None,
        symbol: str = "EURUSD=X",
        timeframe: str = "1h",
        strategy_name: str = "unknown",
    ) -> None:
        self.config = config or BacktestConfig()
        self.symbol = symbol
        self.timeframe = timeframe
        self.strategy_name = strategy_name
        self.pip_value = PIP_VALUES.get(symbol, 0.0001)

    def run(self, df: pd.DataFrame) -> BacktestResult:
        """Run backtest on a DataFrame with signal, sl, tp columns."""
        required = {"close", "high", "low", "signal", "sl", "tp"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        if "timestamp" not in df.columns:
            raise ValueError("Missing required column: timestamp")

        df = df.reset_index(drop=True)

        # Pre-extract numpy arrays for speed
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        signal = df["signal"].values
        sl_arr = df["sl"].values
        tp_arr = df["tp"].values
        timestamps = df["timestamp"].values

        equity = self.config.capital
        open_positions: list[Position] = []
        closed_trades: list[dict] = []
        equity_curve: list[float] = []

        n = len(df)
        for i in range(n):
            # Phase A: Check SL/TP on open positions
            # SL checked before TP (conservative)
            remaining = []
            for pos in open_positions:
                hit = self._check_exit(pos, high[i], low[i], close[i], timestamps[i])
                if hit is not None:
                    hit["strategy_name"] = self.strategy_name
                    hit["symbol"] = self.symbol
                    hit["timeframe"] = self.timeframe
                    equity += hit["pnl"]
                    closed_trades.append(hit)
                else:
                    remaining.append(pos)
            open_positions = remaining

            # Phase B: Process new signals
            sig = int(signal[i]) if not np.isnan(signal[i]) else 0
            if sig != 0 and len(open_positions) < self.config.max_positions:
                sl_price = sl_arr[i]
                tp_price = tp_arr[i]
                if not np.isnan(sl_price) and not np.isnan(tp_price):
                    side = "BUY" if sig == 1 else "SELL"
                    entry_price = self._apply_spread_slippage(close[i], side)
                    volume = self._calculate_volume(equity, entry_price, sl_price, side)
                    if volume > 0:
                        open_positions.append(Position(
                            side=side,
                            entry_time=timestamps[i],
                            entry_price=entry_price,
                            volume=volume,
                            sl=sl_price,
                            tp=tp_price,
                            bar_index=i,
                        ))

            # Phase C: Record mark-to-market equity
            mtm = equity
            for pos in open_positions:
                mtm += self._unrealized_pnl(pos, close[i])
            equity_curve.append(mtm)

        # End: close remaining positions at last close
        for pos in open_positions:
            exit_price = close[-1]
            pnl = self._calc_pnl(pos, exit_price)
            closed_trades.append({
                "strategy_name": self.strategy_name,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "side": pos.side,
                "entry_time": pos.entry_time,
                "exit_time": timestamps[-1],
                "entry_price": pos.entry_price,
                "exit_price": exit_price,
                "volume": pos.volume,
                "pnl": pnl,
                "sl": pos.sl,
                "tp": pos.tp,
                "exit_reason": "END",
            })

        trades_df = pd.DataFrame(closed_trades) if closed_trades else pd.DataFrame(
            columns=["strategy_name", "symbol", "timeframe", "side",
                     "entry_time", "exit_time", "entry_price", "exit_price",
                     "volume", "pnl", "sl", "tp", "exit_reason"]
        )

        return BacktestResult(
            trades=trades_df,
            equity_curve=pd.Series(equity_curve, index=df.index),
            initial_capital=self.config.capital,
        )

    def _check_exit(
        self,
        pos: Position,
        bar_high: float,
        bar_low: float,
        bar_close: float,
        timestamp: object,
    ) -> dict | None:
        """Check if SL or TP is hit. SL checked first (conservative)."""
        if pos.side == "BUY":
            # SL hit if low touches SL
            if bar_low <= pos.sl:
                return self._build_trade(pos, pos.sl, timestamp, "SL")
            # TP hit if high touches TP
            if bar_high >= pos.tp:
                return self._build_trade(pos, pos.tp, timestamp, "TP")
        else:  # SELL
            # SL hit if high touches SL
            if bar_high >= pos.sl:
                return self._build_trade(pos, pos.sl, timestamp, "SL")
            # TP hit if low touches TP
            if bar_low <= pos.tp:
                return self._build_trade(pos, pos.tp, timestamp, "TP")
        return None

    def _build_trade(
        self,
        pos: Position,
        exit_price: float,
        timestamp: object,
        reason: str,
    ) -> dict:
        pnl = self._calc_pnl(pos, exit_price)
        return {
            "side": pos.side,
            "entry_time": pos.entry_time,
            "exit_time": timestamp,
            "entry_price": pos.entry_price,
            "exit_price": exit_price,
            "volume": pos.volume,
            "pnl": pnl,
            "sl": pos.sl,
            "tp": pos.tp,
            "exit_reason": reason,
        }

    def _calc_pnl(self, pos: Position, exit_price: float) -> float:
        if pos.side == "BUY":
            return (exit_price - pos.entry_price) * pos.volume / self.pip_value
        else:
            return (pos.entry_price - exit_price) * pos.volume / self.pip_value

    def _unrealized_pnl(self, pos: Position, current_price: float) -> float:
        return self._calc_pnl(pos, current_price)

    def _apply_spread_slippage(self, price: float, side: str) -> float:
        """Apply adverse spread and slippage to entry price."""
        total_pips = self.config.spread_pips + self.config.slippage_pips
        adjustment = total_pips * self.pip_value
        if side == "BUY":
            return price + adjustment  # buy at higher price
        else:
            return price - adjustment  # sell at lower price

    def _calculate_volume(
        self,
        equity: float,
        entry_price: float,
        sl_price: float,
        side: str,
    ) -> float:
        """Calculate position volume based on risk sizing."""
        if not self.config.use_risk_sizing:
            return 1.0

        risk_amount = equity * self.config.risk_per_trade
        sl_distance = abs(entry_price - sl_price)

        if sl_distance == 0:
            return 0.0

        # Volume in units such that PnL = (price_move / pip_value) * volume
        volume = risk_amount * self.pip_value / sl_distance
        return max(volume, 0.0)

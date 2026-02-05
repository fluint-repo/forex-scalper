"""RiskManager — enforces position limits, drawdown circuit breakers, and position sizing."""

import threading
from datetime import date, datetime, timezone
from typing import Any

from config.settings import (
    CORRELATION_GROUPS,
    KELLY_FRACTION,
    MAX_CORRELATED_EXPOSURE,
    MAX_DAILY_LOSS_PCT,
    MAX_OPEN_POSITIONS,
    MAX_PORTFOLIO_RISK_PCT,
    POSITION_SIZE_METHOD,
    RISK_PER_TRADE,
    PIP_VALUES,
)
from src.broker.base import Broker
from src.utils.logger import get_logger

log = get_logger(__name__)


class RiskManager:
    """Thread-safe risk management: daily loss limits, position limits, sizing."""

    def __init__(
        self,
        broker: Broker,
        max_daily_loss_pct: float = MAX_DAILY_LOSS_PCT,
        max_portfolio_risk_pct: float = MAX_PORTFOLIO_RISK_PCT,
        max_correlated_exposure: int = MAX_CORRELATED_EXPOSURE,
        max_open_positions: int = MAX_OPEN_POSITIONS,
        position_size_method: str = POSITION_SIZE_METHOD,
        kelly_fraction: float = KELLY_FRACTION,
        risk_per_trade: float = RISK_PER_TRADE,
        correlation_groups: dict[str, list[str]] | None = None,
    ) -> None:
        self.broker = broker
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_portfolio_risk_pct = max_portfolio_risk_pct
        self.max_correlated_exposure = max_correlated_exposure
        self.max_open_positions = max_open_positions
        self.position_size_method = position_size_method
        self.kelly_fraction = kelly_fraction
        self.risk_per_trade = risk_per_trade
        self.correlation_groups = correlation_groups or CORRELATION_GROUPS

        self._lock = threading.Lock()
        self._circuit_breaker_active = False
        self._daily_date: date | None = None
        self._daily_starting_equity: float = 0.0
        self._daily_realized_pnl: float = 0.0

        # For Kelly calculation
        self._win_count: int = 0
        self._loss_count: int = 0
        self._total_wins: float = 0.0
        self._total_losses: float = 0.0

    def check_daily_loss(self) -> bool:
        """Check if daily loss limit is breached. Returns True if OK, False if breached."""
        with self._lock:
            if self._circuit_breaker_active:
                return False

            self._ensure_daily_reset()

            account = self.broker.get_account_info()
            equity = account.get("equity", 0.0)
            # Unrealized + realized daily PnL
            daily_pnl = (equity - self._daily_starting_equity)

            if self._daily_starting_equity > 0:
                loss_pct = abs(min(daily_pnl, 0)) / self._daily_starting_equity * 100
                if loss_pct >= self.max_daily_loss_pct:
                    self._circuit_breaker_active = True
                    log.warning(
                        "circuit_breaker_triggered",
                        daily_loss_pct=round(loss_pct, 2),
                        limit=self.max_daily_loss_pct,
                    )
                    return False
            return True

    def check_position_limits(self, symbol: str, side: str) -> bool:
        """Check position count and correlated exposure. Returns True if OK."""
        with self._lock:
            positions = self.broker.get_positions()

            # Max open positions
            if len(positions) >= self.max_open_positions:
                log.warning("position_limit_reached", current=len(positions), max=self.max_open_positions)
                return False

            # Correlated exposure
            new_key = f"{symbol}_{side}"
            for group_name, group_keys in self.correlation_groups.items():
                if new_key in group_keys:
                    count = 0
                    for pos in positions:
                        pos_key = f"{pos['symbol']}_{pos['side']}"
                        if pos_key in group_keys:
                            count += 1
                    if count >= self.max_correlated_exposure:
                        log.warning(
                            "correlated_exposure_limit",
                            group=group_name,
                            count=count,
                            max=self.max_correlated_exposure,
                        )
                        return False

            return True

    def check_portfolio_risk(self) -> bool:
        """Check total portfolio risk vs cap. Returns True if OK."""
        with self._lock:
            account = self.broker.get_account_info()
            equity = account.get("equity", 0.0)
            if equity <= 0:
                return False

            positions = self.broker.get_positions()
            total_risk = 0.0
            for pos in positions:
                # Risk per position = distance to SL * volume
                sl = pos.get("sl", 0)
                entry = pos.get("entry_price", 0)
                volume = pos.get("volume", 0)
                symbol = pos.get("symbol", "EURUSD=X")
                pip_value = PIP_VALUES.get(symbol, 0.0001)
                if sl > 0 and entry > 0 and pip_value > 0:
                    sl_distance = abs(entry - sl)
                    risk = sl_distance * volume / pip_value
                    total_risk += risk

            risk_pct = (total_risk / equity) * 100 if equity > 0 else 0
            if risk_pct >= self.max_portfolio_risk_pct:
                log.warning("portfolio_risk_limit", risk_pct=round(risk_pct, 2), max=self.max_portfolio_risk_pct)
                return False
            return True

    def calculate_position_size(
        self, account_equity: float, sl_distance: float, symbol: str
    ) -> float:
        """Calculate position size using configured method."""
        if sl_distance <= 0:
            return 0.0

        pip_value = PIP_VALUES.get(symbol, 0.0001)

        if self.position_size_method == "kelly":
            fraction = self._kelly_size()
            risk_amount = account_equity * fraction
        else:
            risk_amount = account_equity * self.risk_per_trade

        volume = risk_amount * pip_value / sl_distance
        return max(volume, 0.0)

    def _kelly_size(self) -> float:
        """Kelly criterion: f* = (p*b - q) / b, clamped to kelly_fraction."""
        total = self._win_count + self._loss_count
        if total < 10:
            # Not enough data, fall back to fixed risk
            return self.risk_per_trade

        p = self._win_count / total  # win rate
        q = 1 - p
        avg_win = self._total_wins / self._win_count if self._win_count > 0 else 0
        avg_loss = self._total_losses / self._loss_count if self._loss_count > 0 else 1

        b = avg_win / avg_loss if avg_loss > 0 else 0  # win/loss ratio

        if b <= 0:
            return self.risk_per_trade

        kelly = (p * b - q) / b
        kelly = max(kelly, 0.0)
        # Clamp to fraction of full Kelly
        kelly = min(kelly, self.kelly_fraction)
        return kelly

    def record_trade(self, pnl: float) -> None:
        """Record a completed trade for Kelly calculations and daily P&L."""
        with self._lock:
            self._daily_realized_pnl += pnl
            if pnl > 0:
                self._win_count += 1
                self._total_wins += pnl
            elif pnl < 0:
                self._loss_count += 1
                self._total_losses += abs(pnl)

    def reset_daily(self) -> None:
        """Reset daily P&L tracking and circuit breaker."""
        with self._lock:
            self._circuit_breaker_active = False
            self._daily_realized_pnl = 0.0
            account = self.broker.get_account_info()
            self._daily_starting_equity = account.get("equity", 0.0)
            self._daily_date = datetime.now(timezone.utc).date()
            log.info("risk_daily_reset", starting_equity=self._daily_starting_equity)

    def _ensure_daily_reset(self) -> None:
        """Auto-reset if the date has changed (UTC)."""
        today = datetime.now(timezone.utc).date()
        if self._daily_date != today:
            self._circuit_breaker_active = False
            self._daily_realized_pnl = 0.0
            account = self.broker.get_account_info()
            self._daily_starting_equity = account.get("equity", 0.0)
            self._daily_date = today

    @property
    def circuit_breaker_active(self) -> bool:
        with self._lock:
            return self._circuit_breaker_active

    def get_status(self) -> dict[str, Any]:
        """Get current risk status for API."""
        with self._lock:
            account = self.broker.get_account_info()
            equity = account.get("equity", 0.0)
            daily_pnl = equity - self._daily_starting_equity if self._daily_starting_equity > 0 else 0.0
            daily_pnl_pct = (daily_pnl / self._daily_starting_equity * 100) if self._daily_starting_equity > 0 else 0.0

            return {
                "circuit_breaker_active": self._circuit_breaker_active,
                "daily_pnl": round(daily_pnl, 2),
                "daily_pnl_pct": round(daily_pnl_pct, 2),
                "daily_loss_limit_pct": self.max_daily_loss_pct,
                "max_portfolio_risk_pct": self.max_portfolio_risk_pct,
                "position_size_method": self.position_size_method,
                "open_positions": len(self.broker.get_positions()),
                "max_open_positions": self.max_open_positions,
                "win_count": self._win_count,
                "loss_count": self._loss_count,
            }

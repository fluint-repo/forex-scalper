"""OandaBroker — live order execution via OANDA v20 REST API."""

import requests

from config.settings import (
    INITIAL_CAPITAL,
    OANDA_ACCOUNT_ID,
    OANDA_API_TOKEN,
    OANDA_BASE_URL,
    OANDA_ENVIRONMENT,
    OANDA_SYMBOL_MAP,
    PIP_VALUES,
    RISK_PER_TRADE,
)
from src.broker.base import Broker, OrderResult, OrderSide
from src.utils.logger import get_logger

log = get_logger(__name__)

LOTS_TO_UNITS = 100_000


class OandaBroker(Broker):
    """Live broker using OANDA v20 REST API."""

    def __init__(
        self,
        account_id: str = OANDA_ACCOUNT_ID,
        api_token: str = OANDA_API_TOKEN,
        environment: str = OANDA_ENVIRONMENT,
        risk_per_trade: float = RISK_PER_TRADE,
    ) -> None:
        self._account_id = account_id
        self._api_token = api_token
        self._base_url = OANDA_BASE_URL[environment]
        self._risk_per_trade = risk_per_trade
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    @property
    def server_managed_sl_tp(self) -> bool:
        return True

    def _instrument(self, symbol: str) -> str:
        return OANDA_SYMBOL_MAP.get(symbol, symbol)

    def _api(self, method: str, path: str, json_data: dict | None = None) -> dict:
        url = f"{self._base_url}/v3/accounts/{self._account_id}{path}"
        resp = requests.request(
            method, url, headers=self._headers, json=json_data, timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def place_order(
        self, symbol: str, side: OrderSide, volume: float, sl: float, tp: float
    ) -> OrderResult:
        instrument = self._instrument(symbol)
        pip_value = PIP_VALUES.get(symbol, 0.0001)

        # Risk-based sizing when volume=0
        if volume == 0:
            account = self.get_account_info()
            equity = account.get("equity", INITIAL_CAPITAL)
            sl_distance = abs(tp - sl)  # rough estimate — in production, use current price
            if sl_distance > 0:
                volume = (equity * self._risk_per_trade * pip_value) / sl_distance
            else:
                volume = 0.01  # minimum lot

        units = int(volume * LOTS_TO_UNITS)
        if side == OrderSide.SELL:
            units = -units

        order_body = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),
                "stopLossOnFill": {"price": f"{sl:.5f}"},
                "takeProfitOnFill": {"price": f"{tp:.5f}"},
            }
        }

        try:
            data = self._api("POST", "/orders", order_body)
            fill = data.get("orderFillTransaction", {})
            trade_id = fill.get("tradeOpened", {}).get("tradeID", "")
            fill_price = float(fill.get("price", 0))
            fill_units = abs(int(fill.get("tradeOpened", {}).get("units", 0)))
            fill_volume = fill_units / LOTS_TO_UNITS

            log.info(
                "oanda_order_filled",
                trade_id=trade_id,
                side=side.value,
                price=fill_price,
                units=fill_units,
            )

            return OrderResult(
                order_id=trade_id,
                symbol=symbol,
                side=side,
                price=fill_price,
                volume=fill_volume,
                success=True,
                message="Filled",
            )
        except requests.exceptions.HTTPError as e:
            msg = str(e)
            try:
                msg = e.response.json().get("errorMessage", msg)
            except Exception:
                pass
            log.warning("oanda_order_rejected", error=msg)
            return OrderResult(
                order_id="",
                symbol=symbol,
                side=side,
                price=0.0,
                volume=0.0,
                success=False,
                message=msg,
            )

    def close_position(self, order_id: str, **kwargs) -> OrderResult:
        try:
            data = self._api("PUT", f"/trades/{order_id}/close")
            close_tx = data.get("orderFillTransaction", {})
            close_price = float(close_tx.get("price", 0))
            units = abs(int(close_tx.get("units", 0)))

            log.info("oanda_position_closed", trade_id=order_id, price=close_price)
            return OrderResult(
                order_id=order_id,
                symbol="",
                side=OrderSide.BUY,
                price=close_price,
                volume=units / LOTS_TO_UNITS,
                success=True,
                message="Closed",
            )
        except requests.exceptions.HTTPError as e:
            msg = str(e)
            try:
                msg = e.response.json().get("errorMessage", msg)
            except Exception:
                pass
            log.warning("oanda_close_failed", trade_id=order_id, error=msg)
            return OrderResult(
                order_id=order_id,
                symbol="",
                side=OrderSide.BUY,
                price=0.0,
                volume=0.0,
                success=False,
                message=msg,
            )

    def get_positions(self) -> list[dict]:
        data = self._api("GET", "/openTrades")
        trades = data.get("trades", [])
        positions = []
        for t in trades:
            units = int(t.get("currentUnits", 0))
            side = "BUY" if units > 0 else "SELL"
            positions.append({
                "order_id": t["id"],
                "symbol": t.get("instrument", ""),
                "side": side,
                "entry_price": float(t.get("price", 0)),
                "volume": abs(units) / LOTS_TO_UNITS,
                "sl": float(t.get("stopLossOrder", {}).get("price", 0)),
                "tp": float(t.get("takeProfitOrder", {}).get("price", 0)),
                "entry_time": t.get("openTime", ""),
                "unrealized_pnl": float(t.get("unrealizedPL", 0)),
            })
        return positions

    def get_account_info(self) -> dict:
        data = self._api("GET", "/summary")
        acct = data.get("account", {})
        balance = float(acct.get("balance", 0))
        equity = float(acct.get("NAV", balance))
        return {
            "balance": balance,
            "equity": equity,
            "open_positions": int(acct.get("openTradeCount", 0)),
            "total_pnl": float(acct.get("pl", 0)),
            "margin_used": float(acct.get("marginUsed", 0)),
            "margin_available": float(acct.get("marginAvailable", 0)),
        }

    def get_closed_trades(self) -> list[dict]:
        data = self._api("GET", "/trades?state=CLOSED&count=100")
        trades = data.get("trades", [])
        result = []
        for t in trades:
            units = int(t.get("initialUnits", 0))
            side = "BUY" if units > 0 else "SELL"
            result.append({
                "strategy_name": "",
                "symbol": t.get("instrument", ""),
                "timeframe": "",
                "side": side,
                "entry_time": t.get("openTime", ""),
                "exit_time": t.get("closeTime", ""),
                "entry_price": float(t.get("price", 0)),
                "exit_price": float(t.get("averageClosePrice", 0)),
                "volume": abs(units) / LOTS_TO_UNITS,
                "pnl": float(t.get("realizedPL", 0)),
                "sl": 0.0,
                "tp": 0.0,
                "exit_reason": "OANDA",
            })
        return result

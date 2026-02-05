"""OANDA v20 data feed — historical candles and streaming prices."""

import json
import time
from typing import Callable

import pandas as pd
import requests

from config.settings import (
    OANDA_ACCOUNT_ID,
    OANDA_API_TOKEN,
    OANDA_BASE_URL,
    OANDA_ENVIRONMENT,
    OANDA_GRANULARITY_MAP,
    OANDA_STREAM_URL,
    OANDA_SYMBOL_MAP,
)
from src.data.feed import DataFeed
from src.utils.logger import get_logger

log = get_logger(__name__)


class OandaFeed(DataFeed):
    """Data feed using OANDA v20 REST + streaming API."""

    def __init__(
        self,
        account_id: str = OANDA_ACCOUNT_ID,
        api_token: str = OANDA_API_TOKEN,
        environment: str = OANDA_ENVIRONMENT,
    ) -> None:
        self._account_id = account_id
        self._api_token = api_token
        self._base_url = OANDA_BASE_URL[environment]
        self._stream_url = OANDA_STREAM_URL[environment]
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _instrument(self, symbol: str) -> str:
        return OANDA_SYMBOL_MAP.get(symbol, symbol)

    def get_historical(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        instrument = self._instrument(symbol)
        granularity = OANDA_GRANULARITY_MAP.get(timeframe, "H1")

        log.info(
            "oanda_fetching_historical",
            instrument=instrument,
            granularity=granularity,
            start=start,
            end=end,
        )

        all_candles = []
        from_time = pd.Timestamp(start).isoformat() + "Z"
        to_time = pd.Timestamp(end).isoformat() + "Z"

        while True:
            params = {
                "granularity": granularity,
                "from": from_time,
                "to": to_time,
                "price": "M",  # mid prices
                "count": 5000,
            }

            url = f"{self._base_url}/v3/instruments/{instrument}/candles"
            resp = requests.get(url, headers=self._headers, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            candles = data.get("candles", [])
            if not candles:
                break

            for c in candles:
                if not c.get("complete", False):
                    continue
                mid = c["mid"]
                all_candles.append({
                    "timestamp": pd.Timestamp(c["time"]),
                    "open": float(mid["o"]),
                    "high": float(mid["h"]),
                    "low": float(mid["l"]),
                    "close": float(mid["c"]),
                    "volume": int(c.get("volume", 0)),
                })

            # Paginate: use the last candle's time as new 'from'
            last_time = candles[-1]["time"]
            if last_time >= to_time or len(candles) < 5000:
                break
            from_time = last_time

        if not all_candles:
            log.warning("oanda_no_historical_data")
            return pd.DataFrame()

        df = pd.DataFrame(all_candles)
        # Remove timezone info for consistency
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
        log.info("oanda_fetched_rows", count=len(df))
        return df

    def stream_prices(self, symbol: str, callback: Callable[[dict], None]) -> None:
        instrument = self._instrument(symbol)
        url = f"{self._stream_url}/v3/accounts/{self._account_id}/pricing/stream"
        params = {"instruments": instrument}

        log.info("oanda_stream_starting", instrument=instrument)

        while True:
            try:
                resp = requests.get(
                    url,
                    headers=self._headers,
                    params=params,
                    stream=True,
                    timeout=30,
                )
                resp.raise_for_status()

                for line in resp.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("type") != "PRICE":
                        continue

                    bids = data.get("bids", [])
                    asks = data.get("asks", [])
                    if not bids or not asks:
                        continue

                    callback({
                        "timestamp": pd.Timestamp(data["time"]),
                        "bid": float(bids[0]["price"]),
                        "ask": float(asks[0]["price"]),
                    })

            except requests.exceptions.RequestException as e:
                log.warning("oanda_stream_reconnecting", error=str(e))
                time.sleep(2)

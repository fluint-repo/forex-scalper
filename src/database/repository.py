from datetime import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from src.database.models import Candle, SessionLocal, Tick, Trade, engine
from src.utils.logger import get_logger

log = get_logger(__name__)


class CandleRepository:
    def upsert_candles(self, df: pd.DataFrame, symbol: str, timeframe: str) -> int:
        """Insert candles from a DataFrame, skipping duplicates."""
        if df.empty:
            return 0

        records = []
        for _, row in df.iterrows():
            records.append({
                "timestamp": row["timestamp"],
                "symbol": symbol,
                "timeframe": timeframe,
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row.get("volume", 0),
                "spread": row.get("spread"),
            })

        stmt = insert(Candle).values(records)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["timestamp", "symbol", "timeframe"],
        )

        with SessionLocal() as session:
            result = session.execute(stmt)
            session.commit()
            count = result.rowcount
            log.info("upserted_candles", symbol=symbol, timeframe=timeframe, rows=count)
            return count

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> pd.DataFrame:
        query = text("""
            SELECT timestamp, open, high, low, close, volume, spread
            FROM candles
            WHERE symbol = :symbol AND timeframe = :timeframe
              AND (:start IS NULL OR timestamp >= :start)
              AND (:end IS NULL OR timestamp <= :end)
            ORDER BY timestamp DESC
            LIMIT :limit
        """)
        with engine.connect() as conn:
            df = pd.read_sql(
                query,
                conn,
                params={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "start": start,
                    "end": end,
                    "limit": limit,
                },
            )
        return df.sort_values("timestamp").reset_index(drop=True)


class TickRepository:
    def insert_tick(self, symbol: str, bid: float, ask: float, timestamp: datetime) -> None:
        with SessionLocal() as session:
            session.add(Tick(
                timestamp=timestamp,
                symbol=symbol,
                bid=bid,
                ask=ask,
            ))
            session.commit()


class TradeRepository:
    def insert_trades(self, df: pd.DataFrame) -> int:
        """Insert trades from a DataFrame into the trades table."""
        if df.empty:
            return 0

        records = []
        for _, row in df.iterrows():
            records.append({
                "strategy_name": row["strategy_name"],
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "side": row["side"],
                "entry_time": row["entry_time"],
                "exit_time": row.get("exit_time"),
                "entry_price": row["entry_price"],
                "exit_price": row.get("exit_price"),
                "volume": row["volume"],
                "pnl": row.get("pnl"),
                "sl": row.get("sl"),
                "tp": row.get("tp"),
                "exit_reason": row.get("exit_reason"),
                "created_at": datetime.utcnow(),
            })

        with SessionLocal() as session:
            session.execute(insert(Trade).values(records))
            session.commit()
            count = len(records)
            log.info("inserted_trades", count=count)
            return count

    def get_trades(
        self,
        strategy: str,
        symbol: str,
    ) -> pd.DataFrame:
        query = text("""
            SELECT id, strategy_name, symbol, timeframe, side,
                   entry_time, exit_time, entry_price, exit_price,
                   volume, pnl, sl, tp, exit_reason, created_at
            FROM trades
            WHERE strategy_name = :strategy AND symbol = :symbol
            ORDER BY entry_time
        """)
        with engine.connect() as conn:
            df = pd.read_sql(
                query,
                conn,
                params={"strategy": strategy, "symbol": symbol},
            )
        return df

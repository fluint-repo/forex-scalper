from datetime import datetime, date

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

    def insert_trade(self, trade: dict, run_id: int | None = None) -> int:
        """Insert a single trade, optionally linked to a strategy run."""
        with SessionLocal() as session:
            stmt = text("""
                INSERT INTO trades (strategy_name, symbol, timeframe, side,
                    entry_time, exit_time, entry_price, exit_price,
                    volume, pnl, sl, tp, exit_reason, run_id, created_at)
                VALUES (:strategy_name, :symbol, :timeframe, :side,
                    :entry_time, :exit_time, :entry_price, :exit_price,
                    :volume, :pnl, :sl, :tp, :exit_reason, :run_id, :created_at)
                RETURNING id
            """)
            result = session.execute(stmt, {
                "strategy_name": trade.get("strategy_name", ""),
                "symbol": trade.get("symbol", ""),
                "timeframe": trade.get("timeframe", ""),
                "side": trade.get("side", ""),
                "entry_time": trade.get("entry_time"),
                "exit_time": trade.get("exit_time"),
                "entry_price": trade.get("entry_price", 0),
                "exit_price": trade.get("exit_price", 0),
                "volume": trade.get("volume", 0),
                "pnl": trade.get("pnl", 0),
                "sl": trade.get("sl", 0),
                "tp": trade.get("tp", 0),
                "exit_reason": trade.get("exit_reason", ""),
                "run_id": run_id,
                "created_at": datetime.utcnow(),
            })
            session.commit()
            row = result.fetchone()
            return row[0] if row else 0

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

    def create_run(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        broker_type: str,
        initial_capital: float,
        config: dict | None = None,
    ) -> int:
        """Create a strategy run record. Returns run_id."""
        import json
        with SessionLocal() as session:
            stmt = text("""
                INSERT INTO strategy_runs
                    (strategy_name, symbol, timeframe, broker_type, initial_capital, config)
                VALUES (:strategy_name, :symbol, :timeframe, :broker_type, :initial_capital, :config)
                RETURNING id
            """)
            result = session.execute(stmt, {
                "strategy_name": strategy_name,
                "symbol": symbol,
                "timeframe": timeframe,
                "broker_type": broker_type,
                "initial_capital": initial_capital,
                "config": json.dumps(config) if config else None,
            })
            session.commit()
            row = result.fetchone()
            return row[0]

    def close_run(self, run_id: int, final_capital: float, total_trades: int) -> None:
        """Close a strategy run."""
        with SessionLocal() as session:
            session.execute(text("""
                UPDATE strategy_runs
                SET stopped_at = NOW(), final_capital = :final_capital, total_trades = :total_trades
                WHERE id = :run_id
            """), {"run_id": run_id, "final_capital": final_capital, "total_trades": total_trades})
            session.commit()

    def get_performance_summary(self, run_id: int) -> dict:
        """Get aggregated performance stats for a run."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total_trades,
                    COALESCE(SUM(pnl), 0) as total_pnl,
                    COALESCE(SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END), 0) as winning_trades,
                    COALESCE(SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END), 0) as losing_trades,
                    COALESCE(AVG(pnl), 0) as avg_pnl,
                    COALESCE(MAX(pnl), 0) as best_trade,
                    COALESCE(MIN(pnl), 0) as worst_trade,
                    COALESCE(SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END), 0) as gross_profit,
                    COALESCE(ABS(SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END)), 0) as gross_loss
                FROM trades WHERE run_id = :run_id
            """), {"run_id": run_id})
            row = result.fetchone()
            if row is None or row[0] == 0:
                return {
                    "total_trades": 0, "total_pnl": 0, "win_rate": 0,
                    "avg_pnl": 0, "best_trade": 0, "worst_trade": 0,
                    "profit_factor": 0,
                }
            total = row[0]
            win_rate = row[2] / total if total > 0 else 0
            profit_factor = row[7] / row[8] if row[8] > 0 else float("inf") if row[7] > 0 else 0
            return {
                "total_trades": total,
                "total_pnl": round(row[1], 2),
                "winning_trades": row[2],
                "losing_trades": row[3],
                "win_rate": round(win_rate, 4),
                "avg_pnl": round(row[4], 2),
                "best_trade": round(row[5], 2),
                "worst_trade": round(row[6], 2),
                "profit_factor": round(profit_factor, 2),
            }

    def get_daily_summaries(self, run_id: int) -> list[dict]:
        """Get daily P&L breakdown for a run."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT date, realized_pnl, trade_count, win_count, max_drawdown
                FROM daily_summary
                WHERE run_id = :run_id
                ORDER BY date
            """), {"run_id": run_id})
            rows = result.fetchall()
            return [
                {
                    "date": str(r[0]),
                    "realized_pnl": r[1],
                    "trade_count": r[2],
                    "win_count": r[3],
                    "max_drawdown": r[4],
                }
                for r in rows
            ]

    def update_daily_summary(
        self, run_id: int, trade_date: date, pnl: float, is_win: bool
    ) -> None:
        """Upsert daily summary for a run."""
        with SessionLocal() as session:
            session.execute(text("""
                INSERT INTO daily_summary (run_id, date, realized_pnl, trade_count, win_count)
                VALUES (:run_id, :date, :pnl, 1, :win)
                ON CONFLICT (run_id, date) DO UPDATE SET
                    realized_pnl = daily_summary.realized_pnl + :pnl,
                    trade_count = daily_summary.trade_count + 1,
                    win_count = daily_summary.win_count + :win
            """), {"run_id": run_id, "date": trade_date, "pnl": pnl, "win": 1 if is_win else 0})
            session.commit()

    def get_trade_history(self, run_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
        """Get paginated trade history for a run."""
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, strategy_name, symbol, timeframe, side,
                       entry_time, exit_time, entry_price, exit_price,
                       volume, pnl, sl, tp, exit_reason, created_at
                FROM trades
                WHERE run_id = :run_id
                ORDER BY entry_time DESC
                LIMIT :limit OFFSET :offset
            """), {"run_id": run_id, "limit": limit, "offset": offset})
            rows = result.fetchall()
            columns = ["id", "strategy_name", "symbol", "timeframe", "side",
                       "entry_time", "exit_time", "entry_price", "exit_price",
                       "volume", "pnl", "sl", "tp", "exit_reason", "created_at"]
            return [dict(zip(columns, r)) for r in rows]

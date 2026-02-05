"""Candle history endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_engine_manager
from src.api.schemas import CandleResponse
from src.api.state import EngineManager

router = APIRouter(prefix="/api", tags=["candles"])


@router.get("/candles", response_model=list[CandleResponse])
def get_candles(
    limit: int = Query(250, ge=1, le=5000),
    mgr: EngineManager = Depends(get_engine_manager),
):
    if mgr.engine is None:
        raise HTTPException(status_code=400, detail="No engine active")
    df = mgr.engine.candle_history
    if df.empty:
        return []
    df = df.tail(limit)
    result = []
    for _, row in df.iterrows():
        result.append(CandleResponse(
            timestamp=str(row["timestamp"]),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row.get("volume", 0),
        ))
    return result

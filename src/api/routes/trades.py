"""Trade history endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_engine_manager
from src.api.schemas import TradeResponse
from src.api.state import EngineManager

router = APIRouter(prefix="/api", tags=["trades"])


@router.get("/trades", response_model=list[TradeResponse])
def get_trades(
    limit: int = Query(100, ge=1, le=1000),
    mgr: EngineManager = Depends(get_engine_manager),
):
    if mgr.broker is None:
        raise HTTPException(status_code=400, detail="No broker active")
    trades = mgr.broker.get_closed_trades()
    result = []
    for t in trades[-limit:]:
        result.append(TradeResponse(
            strategy_name=t.get("strategy_name", ""),
            symbol=t.get("symbol", ""),
            timeframe=t.get("timeframe", ""),
            side=t["side"],
            entry_time=str(t.get("entry_time", "")),
            exit_time=str(t.get("exit_time", "")),
            entry_price=t["entry_price"],
            exit_price=t["exit_price"],
            volume=t["volume"],
            pnl=t["pnl"],
            sl=t.get("sl", 0),
            tp=t.get("tp", 0),
            exit_reason=t.get("exit_reason", ""),
        ))
    return result

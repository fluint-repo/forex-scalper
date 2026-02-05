"""Performance analytics endpoints — Phase 5C."""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_engine_manager
from src.api.state import EngineManager

router = APIRouter(prefix="/api/performance", tags=["performance"])


@router.get("/summary")
def performance_summary(mgr: EngineManager = Depends(get_engine_manager)):
    if mgr.engine is None or mgr.engine.run_id is None:
        raise HTTPException(status_code=400, detail="No active run")
    from src.database.repository import TradeRepository
    repo = TradeRepository()
    return repo.get_performance_summary(mgr.engine.run_id)


@router.get("/daily")
def daily_summary(mgr: EngineManager = Depends(get_engine_manager)):
    if mgr.engine is None or mgr.engine.run_id is None:
        raise HTTPException(status_code=400, detail="No active run")
    from src.database.repository import TradeRepository
    repo = TradeRepository()
    return repo.get_daily_summaries(mgr.engine.run_id)


@router.get("/history")
def trade_history(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    mgr: EngineManager = Depends(get_engine_manager),
):
    if mgr.engine is None or mgr.engine.run_id is None:
        raise HTTPException(status_code=400, detail="No active run")
    from src.database.repository import TradeRepository
    repo = TradeRepository()
    return repo.get_trade_history(mgr.engine.run_id, limit, offset)

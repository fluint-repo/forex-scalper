"""Positions endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_engine_manager
from src.api.schemas import PositionResponse
from src.api.state import EngineManager

router = APIRouter(prefix="/api", tags=["positions"])


@router.get("/positions", response_model=list[PositionResponse])
def get_positions(
    engine_id: str | None = Query(None),
    mgr: EngineManager = Depends(get_engine_manager),
):
    if engine_id:
        inst = mgr.get_engine(engine_id)
        if inst is None:
            raise HTTPException(status_code=404, detail=f"Engine '{engine_id}' not found")
        positions = inst.broker.get_positions()
    elif mgr.broker is not None:
        positions = mgr.broker.get_positions()
    else:
        raise HTTPException(status_code=400, detail="No broker active")

    result = []
    for p in positions:
        result.append(PositionResponse(
            order_id=p["order_id"],
            symbol=p.get("symbol", ""),
            side=p["side"],
            entry_price=p["entry_price"],
            volume=p["volume"],
            sl=p.get("sl", 0),
            tp=p.get("tp", 0),
            entry_time=str(p.get("entry_time", "")),
            unrealized_pnl=p.get("unrealized_pnl", 0),
        ))
    return result


@router.post("/positions/{order_id}/close")
def close_position(order_id: str, mgr: EngineManager = Depends(get_engine_manager)):
    if mgr.broker is None:
        raise HTTPException(status_code=400, detail="No broker active")
    result = mgr.broker.close_position(order_id)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return {"status": "closed", "order_id": order_id}

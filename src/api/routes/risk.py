"""Risk management endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_engine_manager
from src.api.state import EngineManager

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/status")
def risk_status(mgr: EngineManager = Depends(get_engine_manager)):
    if mgr.risk_manager is None:
        raise HTTPException(status_code=400, detail="No risk manager active")
    return mgr.risk_status


@router.post("/reset")
def reset_circuit_breaker(mgr: EngineManager = Depends(get_engine_manager)):
    if mgr.risk_manager is None:
        raise HTTPException(status_code=400, detail="No risk manager active")
    mgr.risk_manager.reset_daily()
    return {"status": "reset", "circuit_breaker_active": False}

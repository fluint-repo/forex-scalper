"""Account endpoint."""

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_engine_manager
from src.api.schemas import AccountResponse
from src.api.state import EngineManager

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/account", response_model=AccountResponse)
def get_account(mgr: EngineManager = Depends(get_engine_manager)):
    if mgr.broker is None:
        raise HTTPException(status_code=400, detail="No broker active")
    info = mgr.broker.get_account_info()
    return AccountResponse(**info)

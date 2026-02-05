"""Strategy control endpoints — multi-engine support (Phase 5D)."""

from fastapi import APIRouter, Depends, HTTPException

from config.settings import INITIAL_CAPITAL
from src.api.deps import get_engine_manager
from src.api.schemas import StrategyParamsUpdate, StrategyStartRequest, StrategyStatusResponse
from src.api.state import EngineManager
from src.strategy.bb_reversion import BBReversionStrategy
from src.strategy.ema_crossover import EMACrossoverStrategy

router = APIRouter(prefix="/api/strategy", tags=["strategy"])

STRATEGIES = {
    "ema_crossover": EMACrossoverStrategy,
    "bb_reversion": BBReversionStrategy,
}


@router.post("/start")
def start_strategy(
    req: StrategyStartRequest,
    mgr: EngineManager = Depends(get_engine_manager),
):
    if req.strategy not in STRATEGIES:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {req.strategy}")

    strategy = STRATEGIES[req.strategy]()

    if req.broker == "oanda":
        from src.broker.oanda import OandaBroker
        from src.data.oanda_feed import OandaFeed
        broker = OandaBroker()
        feed = OandaFeed()
    else:
        from src.broker.paper import PaperBroker
        from src.data.demo_feed import DemoFeed
        broker = PaperBroker(symbol=req.symbol, capital=req.capital)
        feed = DemoFeed()

    engine_id = mgr.start_engine(
        strategy=strategy,
        feed=feed,
        broker=broker,
        symbol=req.symbol,
        timeframe=req.timeframe,
        broker_type=req.broker,
    )

    return {"status": "started", "engine_id": engine_id, "strategy": req.strategy, "symbol": req.symbol}


@router.post("/stop")
def stop_strategy(mgr: EngineManager = Depends(get_engine_manager)):
    if not mgr.is_running:
        raise HTTPException(status_code=400, detail="No engine running")
    mgr.stop_engine()
    return {"status": "stopped"}


@router.post("/{engine_id}/stop")
def stop_engine(engine_id: str, mgr: EngineManager = Depends(get_engine_manager)):
    inst = mgr.get_engine(engine_id)
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Engine '{engine_id}' not found")
    if not inst.engine.is_running:
        raise HTTPException(status_code=400, detail=f"Engine '{engine_id}' not running")
    mgr.stop_engine(engine_id)
    return {"status": "stopped", "engine_id": engine_id}


@router.post("/stop-all")
def stop_all_engines(mgr: EngineManager = Depends(get_engine_manager)):
    mgr.stop_all()
    return {"status": "all_stopped"}


@router.get("/status", response_model=None)
def strategy_status(mgr: EngineManager = Depends(get_engine_manager)):
    engines = mgr.list_engines()
    if not engines:
        return StrategyStatusResponse(running=False)
    return {"engines": engines, "running": mgr.is_running}


@router.get("/{engine_id}/status")
def engine_status(engine_id: str, mgr: EngineManager = Depends(get_engine_manager)):
    inst = mgr.get_engine(engine_id)
    if inst is None:
        raise HTTPException(status_code=404, detail=f"Engine '{engine_id}' not found")
    return {
        "engine_id": engine_id,
        "running": inst.engine.is_running,
        "strategy": inst.strategy.name,
        "symbol": inst.symbol,
        "timeframe": inst.timeframe,
        "broker": inst.broker_type,
    }


@router.put("/params")
def update_params(
    update: StrategyParamsUpdate,
    mgr: EngineManager = Depends(get_engine_manager),
):
    if mgr.strategy is None:
        raise HTTPException(status_code=400, detail="No strategy active")
    mgr.strategy.config.params.update(update.params)
    return {"status": "updated", "params": mgr.strategy.config.params}

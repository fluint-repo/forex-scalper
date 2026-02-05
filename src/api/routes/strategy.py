"""Strategy control endpoints."""

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
    if mgr.is_running:
        raise HTTPException(status_code=400, detail="Engine already running")

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

    mgr.start_engine(
        strategy=strategy,
        feed=feed,
        broker=broker,
        symbol=req.symbol,
        timeframe=req.timeframe,
        broker_type=req.broker,
    )

    return {"status": "started", "strategy": req.strategy, "symbol": req.symbol}


@router.post("/stop")
def stop_strategy(mgr: EngineManager = Depends(get_engine_manager)):
    if not mgr.is_running:
        raise HTTPException(status_code=400, detail="Engine not running")
    mgr.stop_engine()
    return {"status": "stopped"}


@router.get("/status", response_model=StrategyStatusResponse)
def strategy_status(mgr: EngineManager = Depends(get_engine_manager)):
    running = mgr.is_running
    return StrategyStatusResponse(
        running=running,
        strategy=mgr.strategy.name if mgr.strategy else "",
        symbol=mgr.symbol,
        timeframe=mgr.timeframe,
        broker=mgr.broker_type,
    )


@router.put("/params")
def update_params(
    update: StrategyParamsUpdate,
    mgr: EngineManager = Depends(get_engine_manager),
):
    if mgr.strategy is None:
        raise HTTPException(status_code=400, detail="No strategy active")
    mgr.strategy.config.params.update(update.params)
    return {"status": "updated", "params": mgr.strategy.config.params}

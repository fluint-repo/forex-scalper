"""EngineManager — manages multiple TradingEngine instances for the API."""

import threading
from dataclasses import dataclass, field
from typing import Any

from src.broker.base import Broker
from src.data.feed import DataFeed
from src.engine.event_bus import EventBus
from src.engine.trading import TradingEngine
from src.risk.manager import RiskManager
from src.strategy.base import Strategy
from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class EngineInstance:
    engine_id: str
    engine: TradingEngine
    broker: Broker
    feed: DataFeed
    strategy: Strategy
    event_bus: EventBus
    risk_manager: RiskManager | None = None
    run_id: int | None = None
    symbol: str = ""
    timeframe: str = ""
    broker_type: str = ""


class EngineManager:
    """Thread-safe manager for multiple TradingEngine instances."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._engines: dict[str, EngineInstance] = {}
        # Shared risk manager for portfolio-level risk
        self._shared_risk_manager: RiskManager | None = None

        # Legacy single-engine compatibility properties
        self._last_started: str | None = None

    # --- Legacy properties for backward compatibility ---
    @property
    def engine(self) -> TradingEngine | None:
        with self._lock:
            if self._last_started and self._last_started in self._engines:
                return self._engines[self._last_started].engine
            # Return first running engine
            for inst in self._engines.values():
                if inst.engine.is_running:
                    return inst.engine
            return None

    @property
    def broker(self) -> Broker | None:
        with self._lock:
            if self._last_started and self._last_started in self._engines:
                return self._engines[self._last_started].broker
            for inst in self._engines.values():
                if inst.engine.is_running:
                    return inst.broker
            return None

    @property
    def feed(self) -> DataFeed | None:
        with self._lock:
            if self._last_started and self._last_started in self._engines:
                return self._engines[self._last_started].feed
            return None

    @property
    def strategy(self) -> Strategy | None:
        with self._lock:
            if self._last_started and self._last_started in self._engines:
                return self._engines[self._last_started].strategy
            return None

    @property
    def event_bus(self) -> EventBus | None:
        with self._lock:
            if self._last_started and self._last_started in self._engines:
                return self._engines[self._last_started].event_bus
            return None

    @property
    def risk_manager(self) -> RiskManager | None:
        return self._shared_risk_manager

    @property
    def symbol(self) -> str:
        with self._lock:
            if self._last_started and self._last_started in self._engines:
                return self._engines[self._last_started].symbol
            return ""

    @property
    def timeframe(self) -> str:
        with self._lock:
            if self._last_started and self._last_started in self._engines:
                return self._engines[self._last_started].timeframe
            return ""

    @property
    def broker_type(self) -> str:
        with self._lock:
            if self._last_started and self._last_started in self._engines:
                return self._engines[self._last_started].broker_type
            return ""

    @property
    def is_running(self) -> bool:
        with self._lock:
            return any(inst.engine.is_running for inst in self._engines.values())

    @property
    def risk_status(self) -> dict:
        if self._shared_risk_manager is not None:
            return self._shared_risk_manager.get_status()
        return {}

    # --- Multi-engine API ---

    def _generate_engine_id(self, strategy_name: str, symbol: str, timeframe: str) -> str:
        base = f"{strategy_name}_{symbol}_{timeframe}"
        if base not in self._engines:
            return base
        i = 2
        while f"{base}_{i}" in self._engines:
            i += 1
        return f"{base}_{i}"

    def start_engine(
        self,
        strategy: Strategy,
        feed: DataFeed,
        broker: Broker,
        symbol: str,
        timeframe: str,
        broker_type: str = "paper",
        engine_id: str | None = None,
    ) -> str:
        """Start a new engine instance. Returns engine_id."""
        with self._lock:
            if engine_id is None:
                engine_id = self._generate_engine_id(strategy.name, symbol, timeframe)

            if engine_id in self._engines:
                inst = self._engines[engine_id]
                if inst.engine.is_running:
                    raise RuntimeError(f"Engine '{engine_id}' already running")

            event_bus = EventBus()

            # Create or reuse shared risk manager
            if self._shared_risk_manager is None:
                self._shared_risk_manager = RiskManager(broker)
                self._shared_risk_manager.reset_daily()

            eng = TradingEngine(
                strategy=strategy,
                feed=feed,
                broker=broker,
                symbol=symbol,
                timeframe=timeframe,
                event_bus=event_bus,
                risk_manager=self._shared_risk_manager,
            )

            inst = EngineInstance(
                engine_id=engine_id,
                engine=eng,
                broker=broker,
                feed=feed,
                strategy=strategy,
                event_bus=event_bus,
                risk_manager=self._shared_risk_manager,
                symbol=symbol,
                timeframe=timeframe,
                broker_type=broker_type,
            )
            self._engines[engine_id] = inst
            self._last_started = engine_id

            eng.start()
            log.info("engine_started", engine_id=engine_id, symbol=symbol, strategy=strategy.name)
            return engine_id

    def stop_engine(self, engine_id: str | None = None) -> None:
        """Stop a specific engine or the last started one."""
        with self._lock:
            if engine_id is None:
                engine_id = self._last_started

            if engine_id is None:
                return

            inst = self._engines.get(engine_id)
            if inst is None or not inst.engine.is_running:
                return

            inst.engine.stop()
            log.info("engine_stopped", engine_id=engine_id)

    def stop_all(self) -> None:
        """Stop all running engines."""
        with self._lock:
            for engine_id, inst in self._engines.items():
                if inst.engine.is_running:
                    inst.engine.stop()
                    log.info("engine_stopped", engine_id=engine_id)

    def get_engine(self, engine_id: str) -> EngineInstance | None:
        with self._lock:
            return self._engines.get(engine_id)

    def list_engines(self) -> list[dict[str, Any]]:
        """Return status of all engines."""
        with self._lock:
            result = []
            for eid, inst in self._engines.items():
                result.append({
                    "engine_id": eid,
                    "running": inst.engine.is_running,
                    "strategy": inst.strategy.name,
                    "symbol": inst.symbol,
                    "timeframe": inst.timeframe,
                    "broker": inst.broker_type,
                })
            return result

    def get_all_positions(self) -> list[dict]:
        """Aggregate positions from all running engines' brokers."""
        # Copy broker list under lock, then query without holding lock
        with self._lock:
            brokers = []
            seen_brokers = set()
            for inst in self._engines.values():
                broker_id = id(inst.broker)
                if broker_id in seen_brokers:
                    continue
                seen_brokers.add(broker_id)
                if inst.engine.is_running:
                    brokers.append((inst.engine_id, inst.broker))

        all_positions = []
        for engine_id, broker in brokers:
            try:
                for pos in broker.get_positions():
                    pos["engine_id"] = engine_id
                    all_positions.append(pos)
            except Exception:
                log.exception("get_positions_failed", engine_id=engine_id)
        return all_positions

    def get_all_trades(self, limit: int = 100) -> list[dict]:
        """Aggregate closed trades from all engines' brokers."""
        # Copy broker list under lock, then query without holding lock
        with self._lock:
            brokers = []
            seen_brokers = set()
            for inst in self._engines.values():
                broker_id = id(inst.broker)
                if broker_id in seen_brokers:
                    continue
                seen_brokers.add(broker_id)
                brokers.append((inst.engine_id, inst.broker))

        all_trades = []
        for engine_id, broker in brokers:
            try:
                for t in broker.get_closed_trades():
                    t["engine_id"] = engine_id
                    all_trades.append(t)
            except Exception:
                log.exception("get_trades_failed", engine_id=engine_id)
        return all_trades[-limit:]

    def get_aggregated_account(self) -> dict:
        """Aggregate account info across all brokers."""
        # Copy broker list under lock, then query without holding lock
        with self._lock:
            brokers = []
            seen_brokers = set()
            for inst in self._engines.values():
                broker_id = id(inst.broker)
                if broker_id in seen_brokers:
                    continue
                seen_brokers.add(broker_id)
                brokers.append((inst.engine_id, inst.broker))

        total_balance = 0.0
        total_equity = 0.0
        total_positions = 0
        total_pnl = 0.0

        for engine_id, broker in brokers:
            try:
                info = broker.get_account_info()
                total_balance += info.get("balance", 0)
                total_equity += info.get("equity", 0)
                total_positions += info.get("open_positions", 0)
                total_pnl += info.get("total_pnl", 0)
            except Exception:
                log.exception("get_account_failed", engine_id=engine_id)

        return {
            "balance": total_balance,
            "equity": total_equity,
            "open_positions": total_positions,
            "total_pnl": total_pnl,
        }

    def get_health(self) -> dict[str, Any]:
        """Return health status for all engines."""
        with self._lock:
            engines = [(eid, inst.engine) for eid, inst in self._engines.items()]

        result = {}
        for engine_id, engine in engines:
            result[engine_id] = engine.health_status
        return result

    def get_all_event_buses(self) -> list[EventBus]:
        """Return all event buses for WS subscription."""
        with self._lock:
            return [inst.event_bus for inst in self._engines.values()]

"""EngineManager — singleton managing TradingEngine lifecycle for the API."""

import threading

from src.broker.base import Broker
from src.data.feed import DataFeed
from src.engine.event_bus import EventBus
from src.engine.trading import TradingEngine
from src.strategy.base import Strategy
from src.utils.logger import get_logger

log = get_logger(__name__)


class EngineManager:
    """Thread-safe singleton managing the TradingEngine lifecycle."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.engine: TradingEngine | None = None
        self.broker: Broker | None = None
        self.feed: DataFeed | None = None
        self.strategy: Strategy | None = None
        self.event_bus: EventBus | None = None
        self._symbol: str = ""
        self._timeframe: str = ""
        self._broker_type: str = ""

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self.engine is not None and self.engine.is_running

    @property
    def symbol(self) -> str:
        return self._symbol

    @property
    def timeframe(self) -> str:
        return self._timeframe

    @property
    def broker_type(self) -> str:
        return self._broker_type

    def start_engine(
        self,
        strategy: Strategy,
        feed: DataFeed,
        broker: Broker,
        symbol: str,
        timeframe: str,
        broker_type: str = "paper",
    ) -> None:
        with self._lock:
            if self.engine is not None and self.engine.is_running:
                raise RuntimeError("Engine already running")

            self.strategy = strategy
            self.feed = feed
            self.broker = broker
            self.event_bus = EventBus()
            self._symbol = symbol
            self._timeframe = timeframe
            self._broker_type = broker_type

            self.engine = TradingEngine(
                strategy=strategy,
                feed=feed,
                broker=broker,
                symbol=symbol,
                timeframe=timeframe,
                event_bus=self.event_bus,
            )
            self.engine.start()
            log.info("engine_manager_started", symbol=symbol, strategy=strategy.name)

    def stop_engine(self) -> None:
        with self._lock:
            if self.engine is None or not self.engine.is_running:
                return
            self.engine.stop()
            log.info("engine_manager_stopped")

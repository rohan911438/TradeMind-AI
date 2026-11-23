"""StreamEngine wires the pipeline together:

    FeedSimulator --publish--> EventBus --get--> Processor --> MarketState
                                                     |--> Metrics (latency)
                                                     '--> Recorder (Parquet, async)
"""
from __future__ import annotations

import asyncio
import time

from ..config import settings
from ..predictx.data import daily_volatility, load_history
from .bus import InMemoryEventBus
from .metrics import Metrics
from .recorder import Recorder
from .simulator import FeedSimulator
from .state import SymbolState


class StreamEngine:
    def __init__(self) -> None:
        self.bus = InMemoryEventBus()
        self.metrics = Metrics()
        self.recorder = Recorder(settings.EVENTS_DIR, enabled=settings.RECORD_EVENTS)
        self.states: dict[str, SymbolState] = {}
        self.sources: dict[str, str] = {}
        self.sim: FeedSimulator | None = None
        self._tasks: list[asyncio.Task] = []

    def _bootstrap(self) -> None:
        seeds = {}
        for sym in settings.SYMBOLS:
            hist, src = load_history(sym)
            self.sources[sym] = src
            self.states[sym] = SymbolState(sym, hist, settings.BAR_SECONDS)
            seeds[sym] = (float(hist["close"].iloc[-1]), daily_volatility(hist))
        self.sim = FeedSimulator(self.bus, seeds, settings.EVENTS_PER_SEC, settings.BAR_SECONDS,
                                 seed=settings.RANDOM_SEED)

    async def _process(self) -> None:
        bus, states, metrics, recorder = self.bus, self.states, self.metrics, self.recorder
        while True:
            ev = await bus.get()
            # perf_counter_ns: monotonic, sub-microsecond clock (time.time_ns is ~1 ms on Windows)
            ev.ingest_ns = time.perf_counter_ns()
            states[ev.symbol].update(ev)
            ev.processed_ns = time.perf_counter_ns()
            metrics.observe(ev)
            recorder.add(ev)

    async def start(self) -> None:
        await asyncio.to_thread(self._bootstrap)
        self._tasks = [asyncio.create_task(c) for c in
                       (self.sim.run(), self._process(), self.metrics.run(), self.recorder.run())]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await self.recorder.flush()

    def monitor(self) -> dict:
        return {
            "events_per_sec": self.metrics.eps,
            "target_rate": self.sim.rate if self.sim else 0,
            "total_events": self.metrics.total,
            "queue_depth": self.bus.depth(),
            "dropped": self.bus.dropped,
            "eps_history": list(self.metrics.eps_history),
            "uptime_s": round(time.time() - self.metrics.started, 1),
            "recorder": self.recorder.stats(),
            **self.metrics.cached,
        }

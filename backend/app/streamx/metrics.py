"""Performance metrics: throughput and latency percentiles over a ring buffer."""
from __future__ import annotations

import asyncio
import time
from collections import deque

import numpy as np

from .events import MarketEvent


class Metrics:
    def __init__(self, window: int = 10_000) -> None:
        self.proc_us: deque[float] = deque(maxlen=window)   # ingest -> processed
        self.e2e_us: deque[float] = deque(maxlen=window)    # created -> processed (includes queue wait)
        self.total = 0
        self._count_this_sec = 0
        self.eps = 0.0
        self.eps_history: deque[dict] = deque(maxlen=120)
        self.started = time.time()
        self.cached: dict = {}

    def observe(self, ev: MarketEvent) -> None:
        self.proc_us.append((ev.processed_ns - ev.ingest_ns) / 1000)
        self.e2e_us.append((ev.processed_ns - ev.created_ns) / 1000)
        self.total += 1
        self._count_this_sec += 1

    @staticmethod
    def _pct(buf: deque) -> dict:
        if not buf:
            return {"p50": 0, "p95": 0, "p99": 0, "max": 0}
        a = np.fromiter(buf, dtype=float)
        p50, p95, p99 = np.percentile(a, [50, 95, 99])
        return {"p50": round(p50, 1), "p95": round(p95, 1), "p99": round(p99, 1), "max": round(float(a.max()), 1)}

    def histogram(self) -> dict:
        if not self.proc_us:
            return {"edges": [], "counts": []}
        edges = [0, 5, 10, 20, 50, 100, 200, 500, 1000, 1e12]
        counts, _ = np.histogram(np.fromiter(self.proc_us, dtype=float), bins=edges)
        labels = ["<5", "5-10", "10-20", "20-50", "50-100", "100-200", "200-500", "500-1000", ">1000"]
        return {"edges": labels, "counts": counts.tolist()}

    async def run(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            self.eps = float(self._count_this_sec)
            self._count_this_sec = 0
            self.eps_history.append({"t": int(time.time()), "eps": self.eps})
            self.cached = {"processing_latency_us": self._pct(self.proc_us),
                           "end_to_end_latency_us": self._pct(self.e2e_us),
                           "histogram": self.histogram()}

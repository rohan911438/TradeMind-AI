"""Asynchronous event recorder -> Parquet files (columnar format, the same layout an S3 data lake uses).

Events are buffered in memory and written in batches by a background thread, so disk I/O
never blocks the processing loop.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .events import MarketEvent

COLUMNS = ["seq", "symbol", "price", "qty", "bid", "ask", "bid_qty", "ask_qty",
           "created_ns", "ingest_ns", "processed_ns"]


class Recorder:
    def __init__(self, base_dir: Path, enabled: bool = True, flush_every_s: float = 5.0,
                 max_batch: int = 20_000) -> None:
        self.enabled = enabled
        self.session = time.strftime("session-%Y%m%d-%H%M%S")
        self.dir = base_dir / self.session
        self.flush_every_s = flush_every_s
        self.max_batch = max_batch
        self._buf: list[tuple] = []
        self.recorded = 0
        self.files = 0
        self.last_flush = time.time()
        self.last_write_ms = 0.0

    def add(self, ev: MarketEvent) -> None:
        if self.enabled:
            self._buf.append((ev.seq, ev.symbol, ev.price, ev.qty, ev.bids[0][0], ev.asks[0][0],
                              sum(q for _, q in ev.bids), sum(q for _, q in ev.asks),
                              ev.created_ns, ev.ingest_ns, ev.processed_ns))

    def _write(self, rows: list[tuple], path: Path) -> None:
        t0 = time.perf_counter()
        cols = list(zip(*rows))
        table = pa.table({name: list(col) for name, col in zip(COLUMNS, cols)})
        pq.write_table(table, path, compression="snappy")
        self.last_write_ms = (time.perf_counter() - t0) * 1000

    async def flush(self) -> None:
        if not self._buf:
            return
        rows, self._buf = self._buf, []
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"part-{self.files:05d}.parquet"
        await asyncio.to_thread(self._write, rows, path)
        self.files += 1
        self.recorded += len(rows)
        self.last_flush = time.time()

    async def run(self) -> None:
        while True:
            await asyncio.sleep(0.5)
            if self.enabled and (len(self._buf) >= self.max_batch or time.time() - self.last_flush >= self.flush_every_s):
                await self.flush()

    def stats(self) -> dict:
        return {"enabled": self.enabled, "session": self.session, "recorded": self.recorded,
                "files": self.files, "buffered": len(self._buf),
                "seconds_since_flush": round(time.time() - self.last_flush, 1),
                "last_write_ms": round(self.last_write_ms, 1), "path": str(self.dir)}

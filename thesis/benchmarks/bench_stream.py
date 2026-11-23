"""StreamX benchmarks: thesis Experiments A, B and C.

Run from the repository root with the backend virtual environment:

    backend\.venv\Scripts\python.exe thesis\benchmarks\bench_stream.py            # all
    backend\.venv\Scripts\python.exe thesis\benchmarks\bench_stream.py A C        # selected

A  Capture interval: fixed-interval snapshots vs event-driven capture of the same stream
B  Persistence: no persistence vs async Parquet (production design) vs synchronous SQLite
C  Load and scalability: target rate 100 -> 20,000 events/s, 3 trials each

The benchmarks use the production StreamX classes (FeedSimulator, InMemoryEventBus,
SymbolState, Recorder). Results are written to thesis/benchmarks/results/*.json.
"""
from __future__ import annotations

import asyncio
import json
import math
import platform
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import psutil
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.predictx.data import daily_volatility, load_history  # noqa: E402
from app.streamx.bus import InMemoryEventBus  # noqa: E402
from app.streamx.recorder import Recorder  # noqa: E402
from app.streamx.simulator import FeedSimulator  # noqa: E402
from app.streamx.state import SymbolState  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

HIST, SEEDS = {}, {}
for _s in settings.SYMBOLS:
    _h, _ = load_history(_s)
    HIST[_s] = _h
    SEEDS[_s] = (float(_h["close"].iloc[-1]), daily_volatility(_h))


def new_states() -> dict[str, SymbolState]:
    return {s: SymbolState(s, HIST[s], settings.BAR_SECONDS) for s in settings.SYMBOLS}


def pct(values) -> dict | None:
    a = np.asarray(values, dtype=float)
    if a.size == 0:
        return None
    p50, p95, p99 = np.percentile(a, [50, 95, 99])
    return {"p50": round(float(p50), 2), "p95": round(float(p95), 2), "p99": round(float(p99), 2),
            "max": round(float(a.max()), 2), "mean": round(float(a.mean()), 2), "n": int(a.size)}


def save(name: str, obj: dict) -> None:
    (RESULTS / f"{name}.json").write_text(json.dumps(obj, indent=2))
    print(f"  -> results/{name}.json")


def row(ev) -> tuple:
    return (ev.seq, ev.symbol, ev.price, ev.qty, ev.bids[0][0], ev.asks[0][0],
            sum(q for _, q in ev.bids), sum(q for _, q in ev.asks),
            ev.created_ns, ev.ingest_ns, ev.processed_ns)


# --------------------------------------------------------------------------- persistence sinks
class TimedRecorder(Recorder):
    """Production Recorder + measurement of persistence lag (processed -> written to Parquet)."""

    def __init__(self, *a, **kw) -> None:
        super().__init__(*a, **kw)
        self.lags_us: list[float] = []

    async def flush(self) -> None:
        if not self._buf:
            return
        rows, self._buf = self._buf, []
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.dir / f"part-{self.files:05d}.parquet"
        await asyncio.to_thread(self._write, rows, path)
        done = time.perf_counter_ns()
        self.lags_us.extend((done - r[10]) / 1000 for r in rows)
        self.files += 1
        self.recorded += len(rows)
        self.last_flush = time.time()

    def integrity(self) -> dict:
        files = sorted(self.dir.glob("*.parquet")) if self.dir.exists() else []
        seqs = np.concatenate([pq.read_table(f, columns=["seq"]).column("seq").to_numpy() for f in files]) \
            if files else np.array([], dtype=int)
        return {"rows_written": int(seqs.size), "unique_seq": int(np.unique(seqs).size),
                "duplicates": int(seqs.size - np.unique(seqs).size), "files": len(files)}


class SyncSQLite:
    """Baseline: the processing path waits for a committed database write for every event."""

    def __init__(self, path: Path, wal: bool) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path, isolation_level=None)   # autocommit -> one commit per event
        if wal:
            self.con.execute("PRAGMA journal_mode=WAL")
            self.con.execute("PRAGMA synchronous=NORMAL")
        else:
            self.con.execute("PRAGMA journal_mode=DELETE")
            self.con.execute("PRAGMA synchronous=FULL")
        self.con.execute("CREATE TABLE IF NOT EXISTS ev (seq INTEGER, symbol TEXT, price REAL, qty INTEGER,"
                         " bid REAL, ask REAL, bid_qty INTEGER, ask_qty INTEGER,"
                         " created_ns INTEGER, ingest_ns INTEGER, processed_ns INTEGER)")

    def write(self, ev) -> None:
        self.con.execute("INSERT INTO ev VALUES (?,?,?,?,?,?,?,?,?,?,?)", row(ev))

    def integrity(self) -> dict:
        n, u = self.con.execute("SELECT COUNT(*), COUNT(DISTINCT seq) FROM ev").fetchone()
        return {"rows_written": n, "unique_seq": u, "duplicates": n - u, "files": 1}

    def close(self) -> None:
        self.con.close()


# --------------------------------------------------------------------------- live pipeline run
async def run_pipeline(rate: int, duration: float, mode: str, tmp: Path, warmup: float = 2.0) -> dict:
    """Simulator -> bus -> processor (+ persistence) for `warmup + duration` seconds."""
    bus = InMemoryEventBus()
    states = new_states()
    sim = FeedSimulator(bus, SEEDS, rate, settings.BAR_SECONDS, seed=42)
    rec = TimedRecorder(tmp, enabled=True) if mode == "async_parquet" else None
    sink = SyncSQLite(tmp / f"{mode}.db", wal=(mode == "sync_sqlite_wal")) if mode.startswith("sync") else None

    proc_us: list[float] = []
    path_us: list[float] = []
    e2e_us: list[float] = []
    st = {"processed": 0, "measuring": False, "max_depth": 0}

    async def process() -> None:
        while True:
            ev = await bus.get()
            ev.ingest_ns = time.perf_counter_ns()
            states[ev.symbol].update(ev)
            ev.processed_ns = time.perf_counter_ns()
            if rec is not None:
                rec.add(ev)
            elif sink is not None:
                sink.write(ev)
            done = time.perf_counter_ns()
            st["processed"] += 1
            if st["measuring"]:
                proc_us.append((ev.processed_ns - ev.ingest_ns) / 1000)
                path_us.append((done - ev.ingest_ns) / 1000)
                e2e_us.append((done - ev.created_ns) / 1000)

    async def sampler() -> None:
        while True:
            await asyncio.sleep(0.05)
            st["max_depth"] = max(st["max_depth"], bus.depth())

    tasks = [asyncio.create_task(c) for c in (sim.run(), process(), sampler())]
    if rec is not None:
        tasks.append(asyncio.create_task(rec.run()))
    me = psutil.Process()
    await asyncio.sleep(warmup)
    me.cpu_percent(None)
    n0, t0 = st["processed"], time.perf_counter()
    st["measuring"] = True
    await asyncio.sleep(duration)
    st["measuring"] = False
    n1, t1 = st["processed"], time.perf_counter()
    cpu = me.cpu_percent(None)
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    in_queue = bus.depth()

    out = {
        "mode": mode, "target_rate": rate, "duration_s": duration,
        "achieved_rate": round((n1 - n0) / (t1 - t0), 1),
        "generated": sim.seq, "processed": st["processed"], "dropped": bus.dropped,
        "left_in_queue": in_queue, "max_queue_depth": st["max_depth"],
        "unaccounted": sim.seq - st["processed"] - bus.dropped - in_queue,
        "cpu_percent_one_core": round(cpu, 1), "rss_mb": round(me.memory_info().rss / 2**20, 1),
        "state_update_us": pct(proc_us), "processing_path_us": pct(path_us), "end_to_end_us": pct(e2e_us),
    }
    if rec is not None:
        await rec.flush()
        out["persistence_lag_ms"] = {k: (round(v / 1000, 1) if k != "n" else v)
                                     for k, v in (pct(rec.lags_us) or {}).items()}
        out["integrity"] = rec.integrity()
    if sink is not None:
        out["persistence_lag_ms"] = {"p50": 0, "p95": 0, "p99": 0, "note": "durable before processing completes"}
        out["integrity"] = sink.integrity()
        sink.close()
    if "integrity" in out:
        out["integrity"]["matches_processed"] = out["integrity"]["unique_seq"] == st["processed"]
    return out


# --------------------------------------------------------------------------- drain (saturation) test
def drain(mode: str, n: int, tmp: Path) -> dict:
    """Pre-generate n events, then process them as fast as possible (no feed pacing)."""
    sim = FeedSimulator(InMemoryEventBus(), SEEDS, 1000, settings.BAR_SECONDS, seed=7)
    g0 = time.perf_counter()
    events = [sim.next_event() for _ in range(n)]
    gen_rate = n / (time.perf_counter() - g0)
    states = new_states()
    rec = Recorder(tmp, enabled=True) if mode == "async_parquet" else None
    sink = SyncSQLite(tmp / f"drain-{mode}.db", wal=(mode == "sync_sqlite_wal")) if mode.startswith("sync") else None
    lat = []
    t0 = time.perf_counter()
    for ev in events:
        ev.ingest_ns = time.perf_counter_ns()
        states[ev.symbol].update(ev)
        ev.processed_ns = time.perf_counter_ns()
        if rec is not None:
            rec.add(ev)
        elif sink is not None:
            sink.write(ev)
        lat.append((time.perf_counter_ns() - ev.ingest_ns) / 1000)
    t1 = time.perf_counter()
    write_ms = 0.0
    if rec is not None:          # the background write the production recorder would do
        rows, rec._buf = rec._buf, []
        rec.dir.mkdir(parents=True, exist_ok=True)
        rec._write(rows, rec.dir / "part-00000.parquet")
        write_ms = rec.last_write_ms
    if sink is not None:
        sink.close()
    t2 = time.perf_counter()
    return {"mode": mode, "events": n, "processing_throughput": round(n / (t1 - t0)),
            "time_to_durable_s": round(t2 - t0, 3), "batch_write_ms": round(write_ms, 1),
            "per_event_us": pct(lat), "generator_rate": round(gen_rate)}


# --------------------------------------------------------------------------- experiments
async def collect_stream(rate: int, duration: float) -> list:
    bus = InMemoryEventBus(maxsize=10_000_000)
    sim = FeedSimulator(bus, SEEDS, rate, settings.BAR_SECONDS, seed=11)
    task = asyncio.create_task(sim.run())
    await asyncio.sleep(duration)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    evs = []
    while bus.depth():
        evs.append(await bus.get())
    return evs


def experiment_a() -> None:
    print("Experiment A: capture interval")
    out = {"intervals_ms": [10, 50, 100, 500, 1000], "runs": []}
    for rate, duration in ((200, 30), (2000, 20)):
        evs = asyncio.run(collect_stream(rate, duration))
        t_start = min(e.created_ns for e in evs)
        span_s = (max(e.created_ns for e in evs) - t_start) / 1e9
        rows = [{"interval_ms": 0, "label": "event-driven (every tick)", "snapshots": len(evs),
                 "events": len(evs), "hidden_events_pct": 0.0, "hidden_price_changes_pct": 0.0,
                 "mean_intra_interval_range_bps": 0.0, "realised_var_ratio": 1.0}]
        for ms in out["intervals_ms"]:
            dns = ms * 1_000_000
            snaps = hidden = changes = changes_seen = 0
            ranges, rv_ratio = [], []
            for sym in settings.SYMBOLS:
                se = [e for e in evs if e.symbol == sym]
                t = np.array([e.created_ns for e in se]) - t_start
                p = np.array([e.price for e in se])
                b = t // dns
                n_bins = int(math.ceil(span_s * 1000 / ms))
                snaps += n_bins
                last_idx = np.r_[np.nonzero(np.diff(b))[0], len(b) - 1]   # last event in each non-empty bin
                hidden += len(se) - len(last_idx)
                changes += int((np.diff(p) != 0).sum())
                sp = p[last_idx]
                changes_seen += int((np.diff(sp) != 0).sum())
                for lo, hi in zip(np.r_[0, last_idx[:-1] + 1], last_idx + 1):
                    seg = p[lo:hi]
                    ranges.append((seg.max() - seg.min()) / seg.mean() * 1e4)
                lr_all = np.diff(np.log(p))
                lr_s = np.diff(np.log(sp))
                if (lr_all ** 2).sum() > 0:
                    rv_ratio.append(float((lr_s ** 2).sum() / (lr_all ** 2).sum()))
            rows.append({"interval_ms": ms, "label": f"snapshot every {ms} ms", "snapshots": snaps,
                         "events": len(evs), "hidden_events_pct": round(100 * hidden / len(evs), 2),
                         "hidden_price_changes_pct": round(100 * (1 - changes_seen / max(changes, 1)), 2),
                         "mean_intra_interval_range_bps": round(float(np.mean(ranges)), 2),
                         "realised_var_ratio": round(float(np.mean(rv_ratio)), 3)})
        out["runs"].append({"feed_rate": rate, "duration_s": round(span_s, 1), "events": len(evs),
                            "events_per_symbol_per_s": round(len(evs) / span_s / len(settings.SYMBOLS), 1),
                            "rows": rows})
        print(f"  rate {rate}: {len(evs)} events")
    save("A_capture_interval", out)


def experiment_b() -> None:
    print("Experiment B: persistence strategy")
    modes = ["none", "async_parquet", "sync_sqlite_wal", "sync_sqlite_full"]
    out = {"paced": [], "drain": []}
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for m in modes:
            r = asyncio.run(run_pipeline(1000, 10, m, tmp / f"paced-{m}"))
            out["paced"].append(r)
            print(f"  paced {m:18s} achieved {r['achieved_rate']:8.1f}/s  path p50 {r['processing_path_us']['p50']} us")
        (tmp / "warm").mkdir(parents=True, exist_ok=True)
        drain("none", 20_000, tmp / "warm")                      # warm caches / allocator before timing
        for m, n in (("none", 50_000), ("async_parquet", 50_000), ("sync_sqlite_wal", 20_000), ("sync_sqlite_full", 2_000)):
            reps = []
            for k in range(3):
                d_ = tmp / f"drain-{m}-{k}"
                d_.mkdir(parents=True, exist_ok=True)
                reps.append(drain(m, n, d_))
            reps.sort(key=lambda r: r["processing_throughput"])
            r = dict(reps[1])                                   # median of 3 repeats
            r["repeats_throughput"] = [x["processing_throughput"] for x in reps]
            out["drain"].append(r)
            print(f"  drain {m:18s} {r['processing_throughput']:>8} ev/s  (repeats {r['repeats_throughput']})")
    save("B_persistence", out)


def experiment_c(trials: int = 3) -> None:
    print("Experiment C: load and scalability")
    rates = [100, 500, 1000, 2000, 5000, 10000, 20000]
    out = {"rates": rates, "trials": trials, "duration_s": 10, "runs": []}
    with tempfile.TemporaryDirectory() as d:
        for rate in rates:
            for k in range(trials):
                r = asyncio.run(run_pipeline(rate, 10, "async_parquet", Path(d) / f"c-{rate}-{k}"))
                r["trial"] = k + 1
                out["runs"].append(r)
                print(f"  {rate:>6}/s trial {k + 1}: achieved {r['achieved_rate']:8.1f}  "
                      f"p50 {r['state_update_us']['p50']:6.1f} us  p99 {r['state_update_us']['p99']:7.1f} us  "
                      f"e2e p99 {r['end_to_end_us']['p99'] / 1000:7.1f} ms  drop {r['dropped']}  cpu {r['cpu_percent_one_core']}%")
    save("C_load", out)


def environment() -> None:
    import pandas, pyarrow, xgboost, sklearn, fastapi
    cpu = "unknown"
    if platform.system() == "Windows":
        import subprocess
        cpu = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
                             capture_output=True, text=True).stdout.strip()
    save("environment", {
        "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"), "os": platform.platform(),
        "cpu": cpu or platform.processor(), "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(), "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "python": platform.python_version(),
        "versions": {"numpy": np.__version__, "pandas": pandas.__version__, "pyarrow": pyarrow.__version__,
                     "xgboost": xgboost.__version__, "scikit-learn": sklearn.__version__, "fastapi": fastapi.__version__},
        "clock": "time.perf_counter_ns (QueryPerformanceCounter on Windows, monotonic, sub-microsecond)",
        "event_loop": type(asyncio.new_event_loop()).__name__,
    })


if __name__ == "__main__":
    which = set(sys.argv[1:]) or {"env", "A", "B", "C"}
    if "env" in which or len(sys.argv) == 1:
        environment()
    if "A" in which:
        experiment_a()
    if "B" in which:
        experiment_b()
    if "C" in which:
        experiment_c()

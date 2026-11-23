"""API benchmarks: thesis Experiment G (local server vs Render cloud deployment).

    backend\.venv\Scripts\python.exe thesis\benchmarks\bench_api.py [--skip-cloud]

Starts a local uvicorn server on port 8011, then measures client-observed HTTP latency for the main
endpoints (sequential requests after warm-up), WebSocket push intervals, and the in-cloud StreamX
metrics reported by the deployed service. Cloud figures include the network round trip from the
test machine (Kolkata) to Render's Singapore region.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
LOCAL = "http://127.0.0.1:8011"
CLOUD = "https://trademind-ai-ujm6.onrender.com"
N = 50

ENDPOINTS = [
    ("GET", "/api/health", None),
    ("GET", "/api/market/RELIANCE/snapshot", None),
    ("GET", "/api/market/RELIANCE/candles?limit=400", None),
    ("GET", "/api/predict/RELIANCE", None),
    ("POST", "/api/risk/evaluate", {"symbol": "RELIANCE", "side": "BUY", "qty": 10}),
    ("GET", "/api/paper/portfolio", None),
]


def stats(ms: list[float]) -> dict:
    a = np.array(ms)
    return {"n": len(ms), "p50_ms": round(float(np.percentile(a, 50)), 1),
            "p95_ms": round(float(np.percentile(a, 95)), 1), "max_ms": round(float(a.max()), 1),
            "mean_ms": round(float(a.mean()), 1)}


def bench_http(base: str) -> dict:
    out = {"base_url": base}
    with httpx.Client(base_url=base, timeout=120) as c:
        t0 = time.perf_counter()
        c.get("/api/health").raise_for_status()
        out["first_request_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        c.post("/api/auth/guest").raise_for_status()
        rows = []
        for method, path, body in ENDPOINTS:
            for _ in range(3):
                c.request(method, path, json=body)
            ms = []
            for _ in range(N):
                t0 = time.perf_counter()
                r = c.request(method, path, json=body)
                ms.append((time.perf_counter() - t0) * 1000)
                r.raise_for_status()
            rows.append({"endpoint": f"{method} {path.split('?')[0]}", "bytes": len(r.content), **stats(ms)})
            print(f"  {base[:30]:30s} {method:4s} {path:42s} p50 {rows[-1]['p50_ms']:7.1f} ms")
        out["endpoints"] = rows
        out["server_stream_metrics"] = c.get("/api/monitor/metrics").json()
        c.post("/api/auth/logout")
    out["websocket"] = bench_ws(base)
    return out


def bench_ws(base: str) -> dict:
    from websockets.sync.client import connect
    url = base.replace("https://", "wss://").replace("http://", "ws://") + "/ws/market"
    arrivals = []
    t_open = time.perf_counter()
    with connect(url, open_timeout=60) as ws:
        connect_ms = (time.perf_counter() - t_open) * 1000
        for _ in range(41):
            ws.recv(timeout=30)
            arrivals.append(time.perf_counter())
    gaps = np.diff(arrivals) * 1000
    return {"connect_ms": round(connect_ms, 1), "messages": len(arrivals),
            "interval_ms": {"p50": round(float(np.percentile(gaps, 50)), 1),
                            "p95": round(float(np.percentile(gaps, 95)), 1),
                            "mean": round(float(gaps.mean()), 1)}}


def main() -> None:
    print("Experiment G: API latency (local vs cloud)")
    out = {"measured_at": time.strftime("%Y-%m-%d %H:%M:%S"), "requests_per_endpoint": N}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8011", "--log-level", "warning"],
                            cwd=ROOT / "backend", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(120):
            try:
                if httpx.get(LOCAL + "/api/health", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        time.sleep(3)   # let the stream warm up
        out["local"] = bench_http(LOCAL)
    finally:
        proc.terminate()
        proc.wait(timeout=20)
    if "--skip-cloud" not in sys.argv:
        out["cloud"] = bench_http(CLOUD)
    (RESULTS / "G_api.json").write_text(json.dumps(out, indent=2))
    print("  -> results/G_api.json")


if __name__ == "__main__":
    main()

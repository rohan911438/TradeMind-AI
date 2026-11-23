"""End-to-end product check against a running server.

    python -m scripts.e2e_check                                  # http://127.0.0.1:8000
    python -m scripts.e2e_check https://trademind-ai-ujm6.onrender.com
"""
from __future__ import annotations

import asyncio
import json
import sys
import time

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
results: list[tuple[bool, str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((bool(cond), name, detail))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def client() -> httpx.Client:
    return httpx.Client(base_url=BASE, timeout=60, follow_redirects=True)


def main() -> None:
    anon = client()

    # ---------- static & health ----------
    for path, ctype in [("/", "text/html"), ("/app", "text/html"), ("/css/tw.css", "text/css"),
                        ("/css/theme.css", "text/css"), ("/js/app.js", "javascript"), ("/js/landing.js", "javascript"),
                        ("/vendor/lightweight-charts.js", "javascript"), ("/vendor/chart.umd.min.js", "javascript"),
                        ("/img/logo.svg", "svg"), ("/docs", "text/html")]:
        r = anon.get(path)
        check(f"GET {path}", r.status_code == 200 and ctype in r.headers.get("content-type", ""),
              f"{r.status_code} {r.headers.get('content-type')}")
    r = anon.get("/does-not-exist")
    check("unknown path -> 404", r.status_code == 404, str(r.status_code))

    h = anon.get("/api/health").json()
    check("health ok + model loaded", h["status"] == "ok" and h["model_loaded"], json.dumps(h)[:200])
    syms = [s["symbol"] for s in anon.get("/api/symbols").json()]
    check("4 symbols", len(syms) == 4, str(syms))

    # ---------- market ----------
    c = anon.get("/api/market/RELIANCE/candles?limit=300").json()
    check("candles returned", len(c) >= 100, str(len(c)))
    check("candles time-ordered", all(c[i]["time"] < c[i + 1]["time"] for i in range(len(c) - 1)))
    check("candles OHLC sane", all(b["low"] <= min(b["open"], b["close"]) and b["high"] >= max(b["open"], b["close"]) for b in c))
    snap = anon.get("/api/market/tcs/snapshot")
    check("lowercase symbol works", snap.status_code == 200, str(snap.status_code))
    s = snap.json()
    check("book: 5 levels, bid < ask", len(s["bids"]) == 5 and len(s["asks"]) == 5 and s["bid"] < s["ask"], f"{s['bid']} {s['ask']}")
    check("unknown symbol -> 404", anon.get("/api/market/XYZ/snapshot").status_code == 404)
    check("candles limit validation", anon.get("/api/market/TCS/candles?limit=abc").status_code == 422)

    # ---------- PredictX ----------
    for sym in syms:
        p = anon.get(f"/api/predict/{sym}").json()
        ok = p["signal"] in ("BUY", "SELL", "HOLD", "NO_TRADE") and 0 <= p["confidence"] <= 1 \
            and abs(sum(p["probabilities"].values()) - 1) < 0.01 and len(p["top_factors"]) == 4 and p["disclaimer"]
        check(f"predict {sym}", ok, json.dumps(p)[:200])
    check("predict unknown -> 404", anon.get("/api/predict/XYZ").status_code == 404)
    mi = anon.get("/api/predict/model-info").json()
    check("model-info has metrics", "macro_f1" in mi and "confusion_matrix" in mi)
    se = anon.get("/api/sentiment/INFY").json()
    check("sentiment", se["label"] in ("Positive", "Negative", "Neutral") and se["headlines"])

    # ---------- auth ----------
    cfg = anon.get("/api/auth/config").json()
    check("auth config exposes Google client id", bool(cfg.get("google_client_id")), str(cfg))
    check("me without session -> 401", anon.get("/api/auth/me").status_code == 401)
    for path in ("/api/paper/portfolio", "/api/paper/orders", "/api/paper/equity", "/api/risk/portfolio"):
        check(f"{path} requires login", anon.get(path).status_code == 401)
    check("order requires login", anon.post("/api/paper/orders", json={"symbol": "TCS", "side": "BUY", "qty": 1}).status_code == 401)
    r = anon.post("/api/auth/google", json={"credential": "not-a-real-token"})
    check("bogus Google token -> 401", r.status_code == 401, f"{r.status_code} {r.text[:120]}")
    check("google missing body -> 422", anon.post("/api/auth/google", json={}).status_code == 422)

    a = client()
    u = a.post("/api/auth/guest").json()
    check("guest login", u["provider"] == "guest" and u["id"].startswith("guest:"))
    check("me after login", a.get("/api/auth/me").json()["id"] == u["id"])
    pf = a.get("/api/paper/portfolio").json()
    check("starts with 10L", pf["equity"] == 1_000_000 and pf["cash"] == 1_000_000, str(pf))

    # ---------- RiskGuard validation ----------
    ev = lambda body: a.post("/api/risk/evaluate", json=body)
    check("invalid side -> 422", ev({"symbol": "TCS", "side": "HOLD", "qty": 1}).status_code == 422)
    check("qty 0 rejected", ev({"symbol": "TCS", "side": "BUY", "qty": 0}).json()["verdict"]["status"] == "REJECTED")
    check("negative qty rejected", ev({"symbol": "TCS", "side": "BUY", "qty": -5}).json()["verdict"]["status"] == "REJECTED")
    check("unknown symbol risk -> 404", ev({"symbol": "XYZ", "side": "BUY", "qty": 1}).status_code == 404)
    v = ev({"symbol": "TCS", "side": "SELL", "qty": 5}).json()["verdict"]
    check("sell without position rejected", v["status"] == "REJECTED", v["reasons"][0])
    r = ev({"symbol": "TCS", "side": "BUY", "qty": 10**12})
    check("huge qty handled", r.status_code == 200 and r.json()["verdict"]["approved_qty"] < 10**6, r.text[:150])

    # ---------- full trade lifecycle ----------
    buy_sym, verdict = None, None
    t_end = time.time() + 120
    while time.time() < t_end and buy_sym is None:
        for sym in syms:
            p = anon.get(f"/api/predict/{sym}").json()
            if p["signal"] in ("BUY", "HOLD"):
                vv = ev({"symbol": sym, "side": "BUY", "qty": None}).json()["verdict"]
                if vv["approved_qty"] > 0:
                    buy_sym, verdict = sym, vv
                    break
        if buy_sym is None:
            time.sleep(4)
    check("found a tradable BUY/HOLD signal within 2 min", buy_sym is not None)
    if buy_sym:
        check("suggested verdict has stop<entry<target", verdict["stop_loss"] < verdict["entry"] < verdict["target"], str(verdict))
        q = max(2, min(verdict["approved_qty"], 40))
        o = a.post("/api/paper/orders", json={"symbol": buy_sym, "side": "BUY", "qty": q}).json()
        filled = o["order"]["status"] == "FILLED"
        check(f"BUY {q} {buy_sym} filled", filled, json.dumps(o["verdict"])[:200])
        if filled:
            pf = a.get("/api/paper/portfolio").json()
            pos = pf["positions"][buy_sym]
            mv = sum(p["market_value"] for p in pf["positions"].values())
            check("position qty matches", pos["qty"] == o["order"]["filled_qty"])
            check("equity = cash + market value", abs(pf["equity"] - (pf["cash"] + mv)) < 1, f"{pf['equity']} vs {pf['cash'] + mv}")
            check("cash reduced by cost", abs((1_000_000 - pf["cash"]) - o["order"]["filled_qty"] * o["order"]["fill_price"]) < 0.5)
            half = pos["qty"] // 2
            o2 = a.post("/api/paper/orders", json={"symbol": buy_sym, "side": "SELL", "qty": half}).json()
            check("partial SELL filled", o2["order"]["status"] == "FILLED" and o2["order"]["realised_pnl"] is not None)
            rest = pos["qty"] - half
            o3 = a.post("/api/paper/orders", json={"symbol": buy_sym, "side": "SELL", "qty": rest + 100}).json()
            check("oversell reduced to held", o3["verdict"]["status"] == "REDUCED" and o3["order"]["filled_qty"] == rest,
                  json.dumps(o3["verdict"])[:200])
            pf = a.get("/api/paper/portfolio").json()
            check("position closed", buy_sym not in pf["positions"])
            check("all cash after close", abs(pf["cash"] - pf["equity"]) < 0.01)
            check("realised pnl consistent", abs((pf["cash"] - 1_000_000) - pf["realised_pnl"]) < 0.5,
                  f"cash delta {pf['cash'] - 1_000_000} vs realised {pf['realised_pnl']}")
            orders = a.get("/api/paper/orders").json()
            check("orders logged (newest first)", len(orders) >= 3 and orders[0]["side"] == "SELL")

    # ---------- account isolation, reset, logout ----------
    b = client()
    b.post("/api/auth/guest")
    check("second user isolated", b.get("/api/paper/orders").json() == [])
    rp = a.post("/api/paper/reset").json()
    check("reset restores 10L", rp["equity"] == 1_000_000 and rp["orders_count"] == 0)
    check("equity curve endpoint", isinstance(a.get("/api/paper/equity").json(), list))
    rk = a.get("/api/risk/portfolio").json()
    check("risk portfolio", "limits" in rk and len(rk["per_symbol"]) == 4)
    a.post("/api/auth/logout")
    check("logout clears session", a.get("/api/auth/me").status_code == 401)

    # ---------- monitor ----------
    check("rate 0 -> 422", anon.post("/api/monitor/rate", json={"events_per_sec": 0}).status_code == 422)
    check("rate 30000 -> 422", anon.post("/api/monitor/rate", json={"events_per_sec": 30000}).status_code == 422)
    m = anon.get("/api/monitor/metrics").json()
    check("metrics shape", "processing_latency_us" in m and m["events_per_sec"] > 0, str(m.get("events_per_sec")))

    # ---------- websockets ----------
    async def ws_check(path: str, key: str) -> bool:
        import websockets
        url = BASE.replace("https://", "wss://").replace("http://", "ws://") + path
        async with websockets.connect(url, open_timeout=20) as ws:
            msgs = [json.loads(await asyncio.wait_for(ws.recv(), 10)) for _ in range(2)]
        return all(key in msg for msg in msgs)

    for path, key in (("/ws/market", "symbols"), ("/ws/monitor", "events_per_sec")):
        try:
            check(f"websocket {path}", asyncio.run(ws_check(path, key)))
        except Exception as exc:
            check(f"websocket {path}", False, repr(exc))

    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed against {BASE}")
    for _, name, detail in failed:
        print(f"  FAILED: {name}  {detail}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

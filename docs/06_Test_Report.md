# Test Report

**Product:** TradeMind AI 1.0 · **Date:** 23 Nov 2026 · **Environments:** Windows 10 laptop (local) and Render cloud (production)

## 1. Summary

| Suite | Checks | Local | Production |
|---|---|---|---|
| Unit tests (`pytest`) | 18 | ✅ 18/18 | n/a |
| End-to-end checks (`scripts/e2e_check.py`) | 116 | ✅ 116/116 | ✅ 116/116 |
| Manual browser testing (desktop) | 6 screens + landing page | ✅ | ✅ |
| Responsive testing (390 px phone width) | 6 screens + landing page | ✅ no horizontal overflow | ✅ |

## 2. How to run

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.e2e_check                                   # local
.\.venv\Scripts\python.exe -m scripts.e2e_check https://trademind-ai-ujm6.onrender.com   # production
```

## 3. Unit tests (17)

| Area | Tests |
|---|---|
| RiskGuard (13) | sizing capped by single-stock exposure; large order REDUCED; small order APPROVED with stop < entry < target; risk budget binds with a wide stop; buying against a SELL signal allowed at 25% size with a warning; buying on NO TRADE allowed with a warning; daily loss limit still applies against the AI; low confidence fails R:R; HOLD halves size; daily loss limit; total exposure cap; sell without position rejected and oversell capped; risk-level thresholds |
| Features (3) | **no look-ahead** (changing future rows never changes past features); no NaN after warm-up; labels valid with the last *horizon* rows empty |
| Paper broker (2) | buy-buy-sell P&L arithmetic with average price; rejected orders change nothing |

## 4. End-to-end checks (67)

| Group | What is verified |
|---|---|
| Static & routing (11) | landing page, app, CSS, JS, vendor bundles, logo, Swagger docs, 404 for unknown paths |
| Health & market (10) | model loaded, ≥ 50 symbols, ticker with `&` (M&M) URL-encoded, candles ordered and OHLC-consistent, lowercase symbols accepted, 5-level book with bid < ask, 404 for unknown symbols, 422 for a bad `limit` |
| PredictX (54) | for every symbol: valid signal, probabilities sum to 1, 4 factors, disclaimer present; model card; sentiment; 404 for unknown symbols |
| Auth & security (10) | Google Client ID exposed to the frontend; 401 without a session on every protected route; **forged Google token rejected (401)**; missing body (422); guest login; `/me` after login |
| RiskGuard validation (7) | invalid side (422), qty 0 and negative qty rejected, unknown symbol (404), sell without position rejected, absurd qty (10¹²) handled safely, buy against the AI approved with a warning |
| Trade lifecycle (13) | finds a tradable signal; stop < entry < target; BUY fills; position qty matches; **equity = cash + market value**; cash reduced by exactly qty × price; partial SELL realises P&L; oversell REDUCED to held qty; position closed; **cash delta = realised P&L**; order log newest first |
| Accounts (6) | second user fully isolated; reset restores ₹10,00,000; equity curve; risk portfolio; logout clears session |
| Monitor (3) | rate 0 and 30,000 rejected (422); metrics shape |
| WebSockets (2) | `/ws/market` and `/ws/monitor` deliver messages (over WSS in production) |

## 5. Performance measurements

| Environment | Target rate | Achieved | P50 | P95 | P99 |
|---|---|---|---|---|---|
| Render | 200/s | 200/s | 8.4 µs | 16.3 µs | 26.4 µs |
| Laptop | 200/s | 199/s | 18.2 µs | 63.2 µs | 250 µs |
| Laptop | 3,000/s | 3,159/s | 9.5 µs | 26.8 µs | 71 µs |

End-to-end latency (creation → processed) includes the simulator's ~10 ms publish batching, so it is in milliseconds by design.

## 6. Defects found and fixed

| # | Defect | Found by | Root cause | Fix |
|---|---|---|---|---|
| 1 | Feed ran at ~8,000 events/s instead of 200 | API smoke test | asyncio treats short sleeps as already due on Windows (15.6 ms clock resolution) | Pace by real elapsed time (`rate × Δt`) |
| 2 | Latency always 0 µs or ~1 ms | API smoke test | `time.time_ns()` has ~1 ms resolution on Windows | `time.perf_counter_ns()` |
| 3 | ~90% of signals NO TRADE; RiskGuard rejected every BUY | Signal distribution analysis | Threshold and reward curve assumed confidence ≥ 0.4; the real model outputs 0.34–0.39 | Threshold = validation median (0.351); reward scales with edge over 1/3 |
| 4 | Browser froze on the landing page | Browser test | Tailwind runtime re-scanned the DOM on every live update | Precompiled Tailwind CSS (15 KB) |
| 5 | Trade and Portfolio screens overflowed on phones | Responsive test | Implicit grid tracks sized to content | `grid-cols-1` (`minmax(0,1fr)`) + `min-width:0` |
| 6 | Feed badge wrapped to 3 lines; price and change % collided on cards | Responsive test | Fixed text on narrow screens | Short badge on mobile, wrapping price row |
| 7 | Users could keep stale CSS/JS after a deploy | Responsive test | No cache headers → heuristic caching | `Cache-Control: no-cache` on app files; vendor files cached for 1 day |
| 8 | Close-position clicks could be lost | Browser automation | Table re-rendered every 3 s, replacing the buttons | Delegated click handler on the table + double-click guard |
| 9 | Large latency values overflowed tiles | Visual check | µs formatting only | Switch to ms above 1,000 µs |
| 10 | Sign-in screen appeared late | Visual check | Auth started after the chart loaded | Auth starts immediately on page load |

## 7. Not covered / known limitations
- Google sign-in has to be completed manually by a person; automated tests cover token rejection, not a real Google login.
- No load test beyond 5,000 events/s on the free tier.
- Paper accounts reset when the free-tier service restarts (ephemeral disk).

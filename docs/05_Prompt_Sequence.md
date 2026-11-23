# Prompt Sequence: Building TradeMind AI with Claude Code

## How to use this file
1. Open a terminal in `C:\Users\dell\Desktop\COLEZ` and run `claude`.
2. Paste **one prompt at a time**, in order. Don't paste the next one until the "✅ Check" list passes.
3. After each step passes: `git add -A; git commit -m "P<n>: <title>"`.
4. If something breaks, use the **Fix-it prompts** at the bottom rather than moving on.
5. When starting a fresh session (new day), paste the **Session starter** first.

> **Session starter** (paste at the start of any new session)
> ```
> Read CLAUDE.md and docs/03_System_Architecture.md. Then look at the current code and
> git log, and tell me in 5 bullets what is already built and which prompt from
> docs/05_Prompt_Sequence.md we should do next. Don't write code yet.
> ```

---

## PHASE 1: Foundation & StreamX (Week 1)

### P0: Project setup
```
Set up the project skeleton described in docs/03_System_Architecture.md section 3.
- git init, add a .gitignore for Python, Node, .venv, .env, backend/data/events, backend/data/raw, node_modules
- create backend/ with requirements.txt (fastapi, uvicorn[standard], pydantic, pydantic-settings,
  sqlalchemy, pandas, numpy, pyarrow, xgboost, scikit-learn, yfinance, pytest, httpx)
- create backend/app/config.py with pydantic-settings (SYMBOLS, EVENTS_PER_SEC=200,
  DATABASE_URL=sqlite:///./trademind.db, STARTING_CAPITAL=1000000, CONFIDENCE_THRESHOLD=0.55,
  USE_FINBERT=false, EVENT_BUS=memory) and a .env.example
- create backend/app/main.py with FastAPI, CORS, and GET /api/health
- create empty packages: streamx, predictx, riskguard, paper, db, api
- write a short README.md with Windows setup steps
Create the venv, install the requirements, start uvicorn and show me /api/health working.
```
✅ Check: `http://localhost:8000/api/health` returns JSON. `http://localhost:8000/docs` opens.

### P1: Events, bus, and simulator
```
Build the StreamX core in backend/app/streamx/:
1. events.py: MarketEvent pydantic model exactly as in docs/03 section 4.
2. bus.py: an abstract EventBus (publish, subscribe -> async iterator) and an
   InMemoryEventBus using asyncio.Queue (bounded, maxsize 100_000). Leave a KafkaEventBus
   stub class with a docstring explaining how it would work; do not implement Kafka yet.
3. simulator.py: FeedSimulator for symbols RELIANCE, TCS, INFY, HDFCBANK.
   - Seed prices: try yfinance last close for <SYMBOL>.NS, fall back to hard-coded values if offline.
   - GBM price process with per-symbol volatility; a slowly changing "regime" (-1..+1) that
     skews book quantities so order-book imbalance is meaningful.
   - 5-level bids/asks around mid, tick size 0.05, realistic quantities.
   - Configurable events_per_sec (changeable at runtime), round-robin across symbols.
   - Stamps created_ts_ns with time.time_ns(). Uses a fixed random seed option.
Write a small unit test for the simulator (bids < asks, 5 levels, prices positive).
```
✅ Check: `pytest -q` passes.

### P2: Processor, market state, and metrics
```
Continue StreamX:
1. state.py: MarketState per symbol: last price, best bid/ask, spread, book, day open/high/low,
   change %, 1-minute OHLCV candles (keep last 500), order-book imbalance
   (sum top-5 bid qty - ask qty)/(sum), rolling volatility of 1-min returns (annualised).
2. processor.py: async task that consumes from the bus, sets ingest_ts_ns, updates state,
   sets processed_ts_ns, sends latencies to metrics and forwards the event to the recorder queue.
3. metrics.py: ring buffer (10_000) of processing latency (processed-ingest) and end-to-end
   latency (processed-created) in microseconds; events/sec computed every second;
   p50/p95/p99 via numpy; queue depth; also keep the last 120 seconds of events/sec history.
4. Wire all tasks into FastAPI lifespan in main.py (start on startup, cancel cleanly on shutdown).
5. Endpoints: GET /api/symbols, GET /api/market/{symbol}/snapshot,
   GET /api/market/{symbol}/candles, GET /api/monitor/metrics, POST /api/monitor/rate.
```
✅ Check: `/api/monitor/metrics` shows events/sec ≈ 200. Snapshot prices change on each refresh. POST rate 1000 raises events/sec.

### P3: Recorder and WebSockets
```
Continue StreamX:
1. recorder.py: async recorder with its own asyncio.Queue. Batches events (5000 or every 2s)
   and writes Parquet files to backend/data/events/<session_id>/part-<n>.parquet using
   pyarrow in a thread (asyncio.to_thread) so it never blocks the processor.
   Track recorder lag (queue size + time since last flush) and expose it in metrics.
   Session id = start datetime. Add an optional S3 upload hook that only runs if
   S3_BUCKET is set (boto3 imported lazily). Default off.
2. api/ws.py: WS /ws/market broadcasting a compact snapshot of all symbols every 100 ms
   (last, bid, ask, change%, imbalance, top-5 book, latest candle). WS /ws/monitor sends
   metrics every 1 s. Handle disconnects cleanly; support multiple clients.
```
✅ Check: Parquet files appear under `backend/data/events/`. A quick Python WebSocket client (ask Claude to write `scripts/ws_check.py`) prints messages.

---

## PHASE 2: Dashboard (Week 2)

### P4: Frontend skeleton and Market Dashboard
```
Create the frontend in frontend/ with Vite + React + TypeScript + Tailwind CSS.
- Dark trading-terminal theme, left sidebar navigation with 6 pages: Market, AI Intelligence,
  StreamX Monitor, Risk, Paper Trading, Replay (placeholders for now except Market).
- vite.config.ts proxies /api and /ws to http://localhost:8000.
- lib/ws.ts: a reusable useWebSocket hook with auto-reconnect.
- Market page: watchlist (4 symbols with price + change% coloured), large candlestick chart
  using the lightweight-charts library (load history from /candles, update the last candle from WS),
  order book (5 levels, depth bars), imbalance gauge (-1..+1) and a visible
  "SIMULATED FEED" badge in the header. Clicking a watchlist symbol switches the chart.
Keep components small: PriceChart, OrderBook, Watchlist, ImbalanceGauge.
```
✅ Check: `npm run dev`. The chart moves live, the book updates, switching symbols works, and nothing freezes after 5 minutes.

### P5: StreamX Monitor page
```
Build the StreamX Monitor page:
- Stat tiles: events/sec, P50, P95, P99 processing latency (µs), end-to-end P99,
  bus queue depth, recorder lag, total events recorded.
- Line chart (recharts) of events/sec over the last 120 s; bar chart / histogram of latency buckets.
- A slider (10 to 5000 ev/s) that calls POST /api/monitor/rate.
- A small architecture strip showing Simulator → EventBus → Processor → State/Recorder → WS
  with live counts on each arrow.
Data comes from /ws/monitor.
```
✅ Check: moving the slider visibly changes ev/s. The latency tiles update every second.

---

## PHASE 3: PredictX (Weeks 3–4)

### P6: Data, features, and training
```
Build PredictX training in backend/app/predictx/:
1. data.py: download 5-minute bars for the last 59 days (yfinance, interval "5m") for
   RELIANCE.NS, TCS.NS, INFY.NS, HDFCBANK.NS; cache to backend/data/raw/<symbol>_5m.csv;
   handle the yfinance MultiIndex columns; fall back to cached CSV if offline.
2. features.py: pure function build_features(df) -> DataFrame with: ret_1, ret_5, ret_15,
   rsi_14, macd, macd_signal, macd_hist, ema_ratio (ema9/ema21 - 1), bb_pctb, atr_14_pct,
   vol_20 (rolling std of returns), volume_z. No look-ahead. Implement the indicators
   with pandas (no TA library). Also make_labels(df, horizon=6, threshold=0.003).
   Note: live 'imbalance' is NOT a training feature (no historical book data); it is blended at inference.
3. train.py (CLI with argparse): pooled dataset across symbols, time-ordered 80/20 split,
   XGBoost multi-class (SELL=0, HOLD=1, BUY=2), early stopping on the last part of train,
   class weights for balance. Save models/xgb_model.json, models/feature_list.json and
   models/metrics.json (accuracy, macro F1, per-class report, confusion matrix,
   baseline = majority class accuracy, label distribution, train/test date ranges,
   global feature importance). Print a clear summary.
4. tests: features have no NaN after warm-up and never use future rows
   (changing a future row must not change past features).
Run the training and show me the metrics honestly, even if accuracy is modest.
```
✅ Check: `models/metrics.json` exists. Test accuracy and macro-F1 are reported **next to the baseline**. Write these numbers down for your report.

### P7: Inference, explanation, and sentiment
```
Build PredictX inference:
1. model.py: load the model once at startup. predict(symbol) builds features from the
   live 1-min candles in MarketState (resample to 5-min; if fewer than ~40 bars of live
   history, prepend the cached historical 5m bars, rescaled so the last close matches the
   live price). Returns probabilities.
2. explain.py: use booster.predict(DMatrix, pred_contribs=True) for the predicted class,
   take the top 4 features by |contribution|, and turn each into a plain-English sentence
   with templates (e.g. RSI < 35 "near oversold", ema_ratio > 0 "short-term trend above
   medium-term trend"). Build a 2-3 sentence overall explanation.
3. Market pressure from live imbalance: > 0.2 Positive, < -0.2 Negative, else Neutral.
   Blend: if pressure agrees with the signal, add +0.03 confidence (cap 0.95); if it disagrees, -0.05.
   Document this rule clearly in code comments as a heuristic.
4. NO_TRADE if confidence < CONFIDENCE_THRESHOLD or annualised volatility is extreme (> 80%).
5. sentiment.py: create data/news/sample_headlines.json (~8 realistic-sounding but clearly
   sample headlines per symbol, marked "sample": true) and a simple finance lexicon scorer
   -> score -1..+1 and label. If USE_FINBERT=true, lazily load ProsusAI/finbert via
   transformers instead (optional; do not add transformers to the base requirements,
   use requirements-optional.txt).
6. Endpoints: GET /api/predict/{symbol} (Signal schema from docs/03 incl. disclaimer),
   GET /api/predict/model-info, GET /api/sentiment/{symbol}.
```
✅ Check: `/api/predict/RELIANCE` returns the full Signal JSON in under 200 ms. The signal changes over time as the simulated regime changes.

### P8: AI Intelligence page
```
Build the AI Intelligence page:
- Symbol selector. Big SignalCard: BUY (green) / SELL (red) / HOLD (amber) / NO TRADE (grey),
  confidence %, market pressure, risk-level placeholder, horizon, "updated X s ago".
  Auto-refresh every 10 s plus a "Re-analyse" button.
- Probability bar (SELL/HOLD/BUY).
- Top factors as horizontal contribution bars (green pushes toward the signal, red against) with the sentence under each.
- Explanation paragraph, sentiment panel with headlines (show "sample headlines" tag).
- Collapsible "Model info": test accuracy vs baseline, macro-F1, confusion matrix grid,
  global feature importance, train/test periods.
- The disclaimer always visible at the bottom of the card.
- A "Test this signal in Paper Trading" button that goes to the Paper page with symbol and side prefilled.
```
✅ Check: you can explain every number on this page in your own words.

---

## PHASE 4: RiskGuard & Paper Trading (Week 5)

### P9: RiskGuard engine
```
Build backend/app/riskguard/ exactly per docs/02 section 2.3 and the RiskVerdict schema in docs/03.
- rules.py: small pure functions, one per rule (stop/target from ATR, position sizing,
  risk/reward check, exposure caps, daily loss limit, signal check, risk level).
- engine.py: evaluate(symbol, side, requested_qty | None, portfolio, market_state, signal)
  -> RiskVerdict. If requested_qty is None, return the suggested size.
  Status: REJECTED if any hard rule fails, REDUCED if qty was cut, else APPROVED.
  Every decision appends a human-readable reason.
- All limits come from config (RISK_PER_TRADE=0.01, MAX_SYMBOL_EXPOSURE=0.20,
  MAX_TOTAL_EXPOSURE=0.60, MIN_RR=1.5, DAILY_LOSS_LIMIT=0.03).
- Endpoints: POST /api/risk/evaluate, GET /api/risk/portfolio.
- pytest: at least 8 tests covering approve, reduce (exposure), reject (R:R, daily loss,
  NO_TRADE), sizing math, and the risk-level thresholds.
```
✅ Check: `pytest -q` is all green. You can explain each rule.

### P10: Paper broker
```
Build backend/app/db (SQLAlchemy models from docs/03 section 4, create tables on startup)
and backend/app/paper/broker.py:
- Account starts with STARTING_CAPITAL. Long-only for simplicity (SELL only up to the held qty).
- place_order(symbol, side, qty): fetch the current signal + run RiskGuard; if REJECTED, store
  the order with status REJECTED and reasons; else fill approved_qty at ask (BUY) / bid (SELL),
  update cash and position (avg price, realised P&L). Store the signal snapshot with the order.
- portfolio(): cash, positions with live mark-to-market (mid price), unrealised/realised P&L,
  equity, exposure %. Background task saves equity_snapshot every 10 s.
- Endpoints: POST /api/paper/orders, GET /api/paper/portfolio, GET /api/paper/orders,
  GET /api/paper/equity, POST /api/paper/reset.
- pytest for broker: buy then sell P&L math, cannot sell more than held, rejected orders do not change cash.
```
✅ Check: place a buy via `/docs`, see the position, sell it, see realised P&L.

### P11: Risk and Paper Trading pages
```
Build the two frontend pages:
Paper Trading page:
- Order ticket: symbol, side, qty (with a "Use suggested size" button), shows the current
  AI signal inline. Step 1 "Check risk" calls /api/risk/evaluate and shows the verdict
  (APPROVED/REDUCED/REJECTED colour, approved qty, stop, target, R:R, reasons).
  Step 2 "Confirm paper order" places it.
- Account summary tiles (cash, equity, day P&L, total P&L), positions table with live P&L,
  orders log (including rejected orders with reasons), equity curve chart.
- Reset account button (with an in-page confirm, not window.confirm).
Risk page:
- Portfolio exposure donut by symbol + cash, total exposure vs the 60% limit bar,
  per-symbol volatility and risk level, daily loss vs limit, table of current risk limits.
Also replace the risk-level placeholder on the AI page with the real value.
```
✅ Check: the full demo flow works. AI signal → check risk → REDUCED or APPROVED → confirm → position shows → P&L moves.

---

## PHASE 5: Replay, Benchmark, Cloud (Week 6)

### P12: Historical replay (stretch)
```
Build replay in backend/app/streamx/replay.py:
- GET /api/replay/sessions lists recorded sessions (folder, event count, duration).
- POST /api/replay/start {session, speed: 1|10|100}: pause the simulator, read the Parquet
  files in order and publish events to the same EventBus, preserving inter-event timing / speed.
- POST /api/replay/stop resumes the simulator. /api/health shows feed mode.
- Replay page in the frontend: session picker, speed buttons, progress bar, and the same
  chart + order book components reused. Header badge switches to "REPLAY 10x".
```
✅ Check: record 5 minutes, then replay at 10×. The chart replays it in about 30 s.

### P13: Benchmark script
```
Create backend/scripts/benchmark.py:
- Runs the bus + processor + metrics (and optionally recorder) WITHOUT the web server.
- Pushes N events as fast as possible (--events 100000) and also at fixed rates
  (--rates 1000 5000 20000), with and without the recorder.
- Outputs a markdown table to docs/benchmark_results.md: rate, achieved ev/s, P50/P95/P99
  processing latency, end-to-end P99, recorder lag, CPU/RAM info (platform + psutil if available).
Run it and show me the table.
```
✅ Check: `docs/benchmark_results.md` contains your real numbers. These go into the report.

### P14: Docker and cloud deployment
```
Containerise and prepare deployment:
- backend/Dockerfile (python:3.11-slim, non-root, uvicorn), frontend/Dockerfile (multi-stage:
  node build -> nginx serving dist and proxying /api and /ws to backend).
- docker-compose.yml: backend + frontend (default). Profile "full" adds postgres, redis and
  kafka (KRaft single node); when EVENT_BUS=kafka, use a KafkaEventBus implemented with
  aiokafka (optional dependency). Keep the memory bus as default.
- Mount backend/models and backend/data as volumes.
- docs/DEPLOYMENT.md: step-by-step deploy on an AWS EC2 t3.small/medium (Ubuntu): security
  group ports, install Docker, clone, docker compose up -d, open in browser. Include cost
  warning and how to stop the instance.
Verify docker compose up works locally (if Docker Desktop is installed).
```
✅ Check: `docker compose up --build` gives a working app on `http://localhost`.

---

## PHASE 6: Polish (Week 7)

### P15: Demo polish
```
Prepare for the demo:
- A "Demo mode" toggle (config DEMO_MODE=true) that seeds the paper account with 2 sample trades
  and starts the simulator with a regime that produces clear signal changes every ~1-2 minutes.
- An About/Architecture page in the UI showing the three-engine diagram and the cloud mapping
  table from docs/03.
- Loading and error states on every page (backend down => friendly banner, not blank screen).
- Consistent number formatting in Indian style (₹10,00,000) via lib/format.ts.
- Final README: features, screenshots placeholders, setup, run, train, test, benchmark, deploy.
- Run all tests and a full manual walkthrough of docs/04 demo script; list anything broken.
```
✅ Check: rehearse the 7-minute script from doc 04 twice without touching code.

---

## Fix-it prompts (use anytime)

**Error after a step**
```
Running <command> gives this error:
<paste full error>
Find the root cause, fix it, and re-run to confirm. Don't change unrelated code.
```

**UI looks broken**
```
On the <page> page, <describe what you see vs what you expect>. Check the browser-facing
code and the API response it uses, fix it, and tell me how to verify.
```

**Explain for viva**
```
Explain backend/app/<file>.py to me as if I'm going to be questioned on it in a viva:
what it does, the key functions, the design choice, and 3 likely questions with answers.
```

**Scope creep guard**
```
Before we add anything new: is this needed for the demo flow in docs/04 section 1?
If not, add it to "Future scope" in docs/01 instead of building it.
```

**Report material**
```
Using docs/, models/metrics.json and docs/benchmark_results.md, draft chapter <N> of my
final report following the outline in docs/04 section 6. Use only real numbers from these
files; do not invent results.
```

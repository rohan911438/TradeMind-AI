# Development Log & Extension Prompts

## Part A: How TradeMind AI was built (23 Nov 2026)

The original plan was a 7-week build (React, Kafka, FinBERT, LSTM). With a one-day deadline, the scope was cut to the core demo flow, and every component was kept behind an interface that leads to the full design.

| Step | What was done | Key decision |
|---|---|---|
| 1 | Docs pack: synopsis, SRS, architecture, demo plan | Fix the scope before writing code |
| 2 | Python 3.11 venv; FastAPI, XGBoost, pandas, PyArrow, yfinance | Single backend serves the API **and** the frontend, so there is no separate build |
| 3 | **StreamX**: event dataclass, bus interface, simulator, state, metrics, recorder, engine | In-memory bus behind an `EventBus` ABC (Kafka-ready) |
| 4 | **PredictX**: yfinance download (~17k real NSE bars), ten features, purged split, XGBoost, model card | Judge on macro-F1 and hit-rate vs baselines, not accuracy |
| 5 | **RiskGuard**: seven rules as pure functions + 12 unit tests | Every verdict explains itself |
| 6 | **Paper broker** + SQLite persistence | Long-only; SELL always closes |
| 7 | **Auth**: Google ID-token verification + guest mode | Demo never blocked by OAuth setup |
| 8 | **UI**: landing page and six-screen terminal | Dark, glass and gradient look with live data everywhere |
| 9 | Smoke test → fixed feed rate (8,000/s instead of 200/s), zero latency readings, over-strict NO TRADE threshold | Pace by elapsed time; `perf_counter_ns`; calibrate the threshold to the validation median |
| 10 | Browser test → UI froze | Replaced the Tailwind runtime with precompiled CSS |
| 11 | GitHub + Dockerfile → Render deploy (Singapore, free tier) | Public repo lets a different-email Render account deploy; auto-deploy on push |
| 12 | Google Client ID configured locally and on Render | Origins: Render URL + localhost |
| 13 | Full test pass: 67 e2e checks, browser and mobile testing | Fixed mobile overflow, stale cache, Close-button race, latency tile overflow |
| 14 | README and docs rewritten to match the shipped product | – |

## Part B: Prompts for extending the product with Claude Code

Open a terminal in the repo, run `claude`, and start every session with:

```
Read CLAUDE.md and docs/03_System_Architecture.md, check git log, and summarise in 5 bullets
what exists. Don't write code yet.
```

After every change, run: `cd backend; python -m pytest -q; python -m scripts.e2e_check`.

### E1: Historical replay
```
Add historical replay to StreamX: streamx/replay.py reads a recorded session from
backend/data/events/<session>/ in order and publishes events to the same EventBus at 1x/10x/100x,
pausing the simulator. Endpoints: GET /api/replay/sessions, POST /api/replay/start {session, speed},
POST /api/replay/stop. Add a Replay screen reusing the chart and order book, and switch the header
badge to "REPLAY 10x". Add e2e checks.
```

### E2: FinBERT sentiment
```
Add optional FinBERT sentiment (ProsusAI/finbert via transformers) behind USE_FINBERT=true,
lazy-loaded, with requirements-optional.txt. Keep the lexicon as the default. Show which method
is active on the AI Signals screen. Do not enable it on the Render free tier (512 MB RAM).
```

### E3: Persistent accounts in the cloud
```
Make db.py use PostgreSQL when DATABASE_URL is set (psycopg), falling back to SQLite.
Keep the same two tables. Document creating a free Postgres on Render and setting DATABASE_URL.
```

### E4: Kafka event bus
```
Implement KafkaEventBus with aiokafka (optional dependency) behind EVENT_BUS=kafka, topic
"market-events", key = symbol. Add a docker-compose.yml with a single-node KRaft Kafka and a
"full" profile. Keep the in-memory bus as the default.
```

### E5: Benchmark script
```
Create backend/scripts/benchmark.py that runs bus + processor + metrics without the web server,
at fixed rates (1k, 5k, 20k events/s) with and without the recorder, and writes a markdown table
to docs/benchmark_results.md (achieved rate, P50/P95/P99, recorder lag, machine info).
```

### Fix-it prompts
```
Running <command> gives: <paste error>. Find the root cause, fix it, re-run to confirm.
Don't change unrelated code.
```
```
Explain backend/app/<file>.py as if I'll be questioned on it in a viva: purpose, key functions,
design choice, and 3 likely questions with answers.
```

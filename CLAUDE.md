# TradeMind AI — Project Context for Claude Code

College final-year project (Cloud Computing + AI). An **educational prototype**, not a real trading system.
Read `docs/03_System_Architecture.md` before writing code, and follow `docs/05_Prompt_Sequence.md` step by step.

## What must actually WORK in the demo (core)
1. **StreamX**: simulated live market feed (ticks + 5-level order book) → event bus → market state → WebSocket to UI. Events recorded to Parquet. Latency metrics (P50/P95/P99, events/sec).
2. **PredictX**: XGBoost model trained on real historical NSE data (yfinance). Returns BUY / SELL / HOLD / NO_TRADE + confidence + top contributing factors + plain-English explanation.
3. **RiskGuard**: volatility, position sizing, risk/reward, exposure limits → APPROVED / REDUCED / REJECTED with reasons.
4. **Paper Trading**: virtual ₹10,00,000, market orders that must pass RiskGuard, positions, live P&L.
5. **React dashboard** that shows all of the above.

## What is SIMULATED / OPTIONAL (do not over-build)
- Live data is a **simulator seeded from real prices**. Always label it "Simulated feed" in the UI.
- Kafka: only behind the `EventBus` interface + optional docker-compose profile. Default = in-process asyncio bus.
- Sentiment: lexicon scorer over `data/news/sample_headlines.json` by default; FinBERT only if `USE_FINBERT=true`.
- Storage: SQLite by default (SQLAlchemy), Postgres via `DATABASE_URL`. Parquet files in `backend/data/events/` stand in for S3.
- LSTM, C++ optimisation, auth, API Gateway, TimescaleDB = future work. Do not build unless asked.

## Stack
- Backend: Python 3.11, FastAPI, uvicorn, pydantic v2, SQLAlchemy 2, pandas, pyarrow, xgboost, yfinance, pytest
- Frontend: React + Vite + TypeScript + Tailwind CSS + `lightweight-charts` + recharts
- Dev OS: Windows 10 (PowerShell). Use `python -m venv .venv` and `.venv\Scripts\activate`.

## Conventions
- Keep it simple and readable — the student must be able to explain every file in a viva.
- Each engine lives in its own package: `backend/app/streamx`, `predictx`, `riskguard`, `paper`.
- All timestamps are `time.time_ns()` integers (ns) in events; ISO strings in API responses.
- Every API response that shows a signal includes the disclaimer: "Educational prototype. Not financial advice."
- Config via `backend/app/config.py` (pydantic-settings, `.env` file). No secrets in code.
- Write pytest tests for RiskGuard rules, feature engineering and the paper broker.
- After each prompt step: run the app/tests, fix errors, then summarise what changed.

## Run commands (once built)
- Backend: `cd backend; .venv\Scripts\activate; uvicorn app.main:app --reload --port 8000`
- Frontend: `cd frontend; npm run dev` (port 5173, proxies `/api` and `/ws` to 8000)
- Train model: `cd backend; python -m app.predictx.train --symbols RELIANCE.NS TCS.NS INFY.NS HDFCBANK.NS`
- Tests: `cd backend; pytest -q`
- Benchmark: `cd backend; python -m scripts.benchmark --events 100000`

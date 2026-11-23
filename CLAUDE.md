# TradeMind AI: Project Context for Claude Code

College final-year project (Cloud Computing + AI). **Shipped and deployed** at https://trademind-ai-ujm6.onrender.com.
Educational paper-trading prototype, not a real trading system. Read `docs/03_System_Architecture.md` before changing code.

## Stack (as built)
- Backend: Python 3.11, FastAPI, Uvicorn, XGBoost, pandas, PyArrow, yfinance, google-auth, itsdangerous. Persistence in SQLite (`backend/app/db.py`).
- Frontend: plain HTML/JS in `backend/static/` (no React, no npm build), **precompiled** Tailwind (`css/tw.css`), TradingView Lightweight Charts, Chart.js. Served by FastAPI.
- Deploy: `Dockerfile` → Render, auto-deploy on push to `main`.

## Engines
- `app/streamx/`: simulator → `EventBus` → processor → `SymbolState` / `Metrics` / `Recorder`. The live feed is SIMULATED from real NSE prices; always label it.
- `app/predictx/`: features (no look-ahead), `train.py` (purged split), `model.py` (signal + explanation), `sentiment.py` (sample headlines).
- `app/riskguard/engine.py`: pure-function rules; every verdict carries reasons.
- `app/paper/broker.py`: per-user accounts. `app/auth.py`: Google ID-token verification + guest.

## Rules
- Keep code simple and explainable (viva).
- Never reintroduce the Tailwind runtime script; it froze the UI. After adding Tailwind classes, rebuild from the repo root:
  `npx tailwindcss@3.4.5 -c tools/tailwind/tailwind.config.js -i tools/tailwind/input.css -o backend/static/css/tw.css --minify`
- Use `time.perf_counter_ns()` for latency and pace loops by elapsed time (Windows timer resolution).
- Signal responses include the disclaimer. Never claim the model is more accurate than `models/metrics.json` shows.
- No secrets in git (`backend/.env`, `data/.secret_key`, `data/*.db` are ignored).
- After each change: `cd backend; python -m pytest -q; python -m scripts.e2e_check`, then commit and push.

## Commands (from `backend/`, venv at `.venv`)
- Run: `.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000` (or `run.bat` at the root)
- Train: `.\.venv\Scripts\python.exe -m app.predictx.train [--refresh]`
- Tests: `.\.venv\Scripts\python.exe -m pytest -q` · E2E: `.\.venv\Scripts\python.exe -m scripts.e2e_check [url]`

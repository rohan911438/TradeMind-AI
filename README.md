# TradeMind AI

**A cloud-ready AI market-intelligence and risk-aware paper-trading platform.**
College project: Cloud Computing + AI integration. Educational prototype, not financial advice.

TradeMind AI streams market events (**StreamX**), explains what an XGBoost model sees in them (**PredictX**), checks every idea against a risk engine (**RiskGuard**), and lets each user test it with **₹10,00,000 of virtual capital**. Users sign in with Google.

## What works
| Engine | Feature |
|---|---|
| StreamX | Live simulated tick + 5-level order-book feed seeded from **real NSE prices**, asyncio event bus (Kafka-compatible interface), market state, candles, order-book imbalance, volatility, Parquet recorder, P50/P95/P99 latency & throughput monitor, adjustable event rate (10–5,000/s) |
| PredictX | XGBoost 3-class model (SELL/HOLD/BUY) trained on ~17k real NSE 5-minute bars (RELIANCE, TCS, INFY, HDFCBANK), purged time-ordered split, per-prediction factor contributions, plain-English explanation, order-book-pressure and sentiment blend, NO TRADE gate |
| RiskGuard | ATR stop loss, 1 % risk position sizing, confidence-scaled risk/reward gate, 20 % single-stock and 60 % total exposure caps, 3 % daily loss limit: APPROVED / REDUCED / REJECTED with reasons |
| Paper trading | Per-user accounts (Google sign-in or guest), fills at bid/ask, positions, realised/unrealised P&L, equity curve, order log with the AI signal and the risk verdict |
| UI | Landing page + trading terminal: Market, AI Signals, Paper Trade, Portfolio & Risk, StreamX Monitor, Architecture |

## Run locally (Windows)
```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.predictx.train          # optional: model is already in models/
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```
Open http://localhost:8000. Or just double-click `run.bat`.

Tests: `cd backend; .\.venv\Scripts\python.exe -m pytest -q`

## Google sign-in setup
1. Google Cloud Console → APIs & Services → Credentials → **Create OAuth client ID** → *Web application*.
2. Authorised JavaScript origins: `http://localhost:8000` (plus your deployed URL).
3. Copy `backend/.env.example` to `backend/.env` and set `GOOGLE_CLIENT_ID=...`, then restart.
Without it, the app offers **Continue as guest**.

## Model results (held-out test set, real NSE data)
See `backend/models/metrics.json`. The model beats the trivial baselines on balanced metrics (macro-F1 0.39 vs 0.25; BUY/SELL hit-rate ~26 % vs ~20 % chance). Plain accuracy is lower than "always HOLD" because HOLD is 59 % of bars and the model is trained with balanced class weights. Short-horizon prediction is noisy, which is why RiskGuard exists.

## Honest scope
- The live feed is **simulated** (no free real-time NSE tick feed exists). It is seeded from real prices and labelled in the UI. One live candle = one 5-minute bar, compressed to 10 s.
- Sentiment uses illustrative sample headlines with a finance lexicon (FinBERT is future work).
- Kafka, S3, RDS and Redis are mapped in the architecture; the prototype uses in-process equivalents.

Docs: `docs/` (synopsis, SRS, architecture, demo plan).

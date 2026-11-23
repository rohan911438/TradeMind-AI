# Project Synopsis

## Title
**TradeMind AI: A Cloud-Based Intelligent Trading and High-Frequency Market Intelligence Platform**

| | |
|---|---|
| **Domain** | Cloud Computing with Artificial Intelligence Integration |
| **Type** | Educational research prototype (paper trading only, no real money) |
| **Live deployment** | https://trademind-ai-ujm6.onrender.com |
| **Repository** | https://github.com/rohan911438/TradeMind-AI |

---

## 1. Abstract

Retail traders face a continuous flood of market data, little help interpreting it, weak risk discipline and no safe environment to test ideas. **TradeMind AI** is a cloud-deployed platform that integrates three cooperating engines.

- **StreamX** ingests a high-frequency stream of trades and five-level order-book updates. It maintains real-time market state, records every event to columnar Parquet storage and measures its own processing latency with nanosecond timestamps.
- **PredictX** applies a gradient-boosted decision-tree model (XGBoost), trained on real NSE 5-minute data, to produce explainable **BUY / SELL / HOLD / NO TRADE** signals. Each signal comes with a confidence score, per-prediction feature contributions and a blend of order-book pressure and news sentiment.
- **RiskGuard** evaluates volatility, position size, risk/reward and portfolio exposure before any simulated order is accepted, and approves, reduces or rejects it with stated reasons.

Users sign in with Google and trade a personal ₹10,00,000 virtual account through a responsive web terminal. The system runs as a Docker container on a cloud platform with continuous deployment from GitHub.

On a held-out test set the model achieves a **macro-F1 of 0.390 against a 0.248 baseline** and a **directional hit-rate of 25.6% against 20.3% chance**. The pipeline processes events with a **median latency of 8–18 µs**.

## 2. Problem Statement

1. **Information overload:** prices, volumes, order books and news change continuously.
2. **Delayed or aggregated data:** many retail tools refresh periodically and hide short-term behaviour.
3. **Lack of interpretation:** beginners struggle to read technical indicators and order-book pressure.
4. **Weak risk management:** trades are placed without considering volatility, position size or potential loss.
5. **No safe testing environment:** strategies are tried with real money first.

## 3. Objectives and Outcomes

| # | Objective | Outcome |
|---|---|---|
| 1 | Design a scalable, event-driven, cloud-deployable architecture | ✅ Event-bus pipeline behind a Kafka-compatible interface, stateless API, Docker image, continuous deployment on Render |
| 2 | Capture events with precise timestamps and measure latency and throughput | ✅ Three nanosecond timestamps per event; live P50/P95/P99 monitor; up to 5,000 events/s |
| 3 | Integrate ML for explainable trading signals with confidence | ✅ XGBoost 3-class model on real NSE data, per-prediction contributions, plain-English explanations |
| 4 | Build a risk engine that approves, reduces or rejects trades | ✅ Seven rules covering sizing, stops, R:R, exposure caps, daily loss limit and the AI gate |
| 5 | Provide a paper-trading environment with virtual capital | ✅ Per-user ₹10,00,000 accounts, live P&L, equity curve, order log |
| 6 | Benchmark and report system performance | ✅ Measured locally and in the cloud (see section 8) |
| 7 | Secure multi-user access | ✅ Google Sign-In (server-side ID-token verification) and guest mode |

## 4. Scope

**In scope (implemented):** simulated live market feed seeded from real NSE prices; event processing, metrics and recording; XGBoost signal model with explanations; lexicon-based sentiment; risk engine; per-user paper trading; Google authentication; monitoring dashboard; Docker-based cloud deployment.

**Out of scope:** real exchange connectivity, real-money or automated live trading, exchange colocation or FPGA hardware, microsecond institutional execution, autonomous reinforcement-learning agents.

## 5. System Modules

| Module | Responsibility | Key techniques |
|---|---|---|
| **StreamX** | Ingest ticks and book updates, maintain market state, compute imbalance and volatility, record history, measure latency | asyncio event bus, geometric Brownian motion simulator, WebSockets, Parquet (PyArrow) |
| **PredictX** | Features, training, inference, explanation, sentiment | XGBoost (multi:softprob), purged time-series split, `pred_contribs` (SHAP-style) values, finance lexicon |
| **RiskGuard** | Position sizing, ATR stop-loss, risk/reward, exposure caps, daily loss limit | Pure-function rule engine with human-readable reasons |
| **Paper broker** | Virtual accounts, fills at bid/ask, positions, realised and unrealised P&L | SQLite persistence (RDS-ready) |
| **Auth** | Sign-in and sessions | Google Identity Services, OpenID Connect ID-token verification, signed session cookies |
| **Web terminal** | Landing page plus six screens: Market, AI Signals, Paper Trade, Portfolio & Risk, StreamX Monitor, Architecture | HTML, Tailwind CSS (precompiled), TradingView Lightweight Charts, Chart.js |
| **Cloud layer** | Packaging, deployment, configuration | Docker, Render, 12-factor environment configuration, health checks |

## 6. Methodology

1. **Data collection.** Real 5-minute OHLCV bars for RELIANCE, TCS, INFY and HDFCBANK (NSE) from Yahoo Finance via `yfinance`: about 4,300 bars per stock covering late August to 23 November 2026, cached as CSV.
2. **Live feed simulation.** No free real-time NSE tick feed is available, so a stochastic simulator continues each stock from its last real close. Prices follow geometric Brownian motion with the stock's measured volatility, scaled to real elapsed time. A hidden, slowly drifting regime adds trends and skews order-book quantities, so book imbalance carries information as it does in real markets. One live candle represents one 5-minute bar, compressed to 10 seconds.
3. **Event processing.** Each event is stamped at creation, ingestion and completion of processing with a monotonic nanosecond clock. Latency percentiles come from a 10,000-event ring buffer.
4. **Feature engineering.** Ten scale-free features: 1/5/15-bar returns, RSI-14, MACD histogram, EMA-9/21 ratio, Bollinger %B, ATR %, 20-bar volatility and volume z-score. A unit test verifies that changing future rows never changes past features.
5. **Labelling.** Forward return over the next 6 bars (30 minutes): BUY if above +0.25%, SELL if below −0.25%, otherwise HOLD.
6. **Training.** Per-stock time-ordered split (68% train / 12% validation / 20% test), with the 6 rows before each boundary purged to stop label leakage. XGBoost with balanced class weights and early stopping on validation log-loss. The NO TRADE threshold is the median validation confidence.
7. **Explainability.** XGBoost per-prediction feature contributions for the predicted class; the top four are turned into sentences.
8. **Signal blending.** Live order-book pressure (±4–5%) and sentiment (+2%) adjust the raw confidence, using a documented heuristic.
9. **Risk evaluation.** Fixed-fractional sizing (1% of equity at risk), 1.5 × ATR stop, reward multiple scaled by the model's edge over the uninformed 1/3 level, minimum R:R of 1.2, caps of 20% per stock and 60% total, 3% daily loss limit.
10. **Evaluation.** Macro-F1, accuracy, directional hit-rate and confusion matrix against majority and chance baselines; latency and throughput measured locally and in the cloud; unit and end-to-end tests.

## 7. Hardware & Software

| | Requirement |
|---|---|
| Development machine | Windows 10/11 laptop, 8 GB RAM |
| Cloud | Render web service (free tier: 512 MB RAM, shared CPU). Also runs on AWS EC2 t3.small or larger |
| Software | Python 3.11, Git, Docker; Node.js only to rebuild CSS |
| Python libraries | FastAPI, Uvicorn, Pydantic, NumPy, pandas, PyArrow, XGBoost, scikit-learn, yfinance, google-auth, itsdangerous, pytest, httpx |
| Frontend libraries | Tailwind CSS 3.4 (precompiled), TradingView Lightweight Charts 4.1, Chart.js 4.4 |

## 8. Results

### 8.1 Model (held-out test period 5–23 Nov 2026, 3,438 bars)

| Metric | TradeMind | Baseline |
|---|---|---|
| Macro-F1 | **0.390** | 0.248 (always HOLD) |
| BUY/SELL hit-rate | **25.6%** | 20.3% (chance) |
| Precision on confident signals | **29.5%** (on 28.9% of bars) | 20.3% |
| Accuracy | 43.8% | 59.3% (always HOLD) / 43.5% (random) |

Most important features: ATR % (0.17), volume z-score (0.15), 15-bar return (0.10), 20-bar volatility (0.10), 1-bar return (0.09).

### 8.2 System performance

| Environment | Load | P50 | P95 | P99 |
|---|---|---|---|---|
| Render cloud | 200 events/s | 8.4 µs | 16.3 µs | 26.4 µs |
| Windows laptop | 200 events/s | 18.2 µs | 63.2 µs | 250 µs |
| Windows laptop | 3,000 events/s | 9.5 µs | 26.8 µs | 71 µs |

The feed rate holds its target (199 events/s at a target of 200; 3,159 at 3,000). Parquet writes run in a background thread and never block processing.

### 8.3 Quality
18 unit tests and 116 end-to-end checks pass, both locally and against the production deployment (see the [Test Report](06_Test_Report.md)).

## 9. Limitations

- The live feed is simulated (seeded from real prices), so it does not track the real market in real time.
- The model's edge is modest, and early stopping at about 10 trees shows that the predictive signal in 5-minute technical features is weak. Confidence is not a probability of profit.
- Sentiment uses illustrative sample headlines.
- Python processing is millisecond-class end to end, not exchange-grade.
- On the free hosting tier the app sleeps when idle, and accounts reset when the service restarts.

## 10. Future Scope

FinBERT on a live news API; LSTM/Transformer models; Kafka on AWS MSK with horizontally scaled processors; PostgreSQL/TimescaleDB and an S3 data lake; historical replay and back-testing; broker API integration for real market data; persistent storage for accounts.

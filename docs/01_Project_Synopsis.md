# Project Synopsis

## Title
**TradeMind AI: A Cloud-Based Intelligent Trading and High-Frequency Market Intelligence Platform**

**Domain:** Cloud Computing with Artificial Intelligence Integration
**Type:** Educational research prototype (no real-money trading)

---

## 1. Abstract
Retail traders face a continuous flood of market data, little help interpreting it, and weak risk discipline. Most also have no safe place to test ideas before risking money. TradeMind AI is a cloud-native prototype that brings together three cooperating engines. **StreamX** ingests and processes high-frequency market events, keeps a real-time market state and measures its own processing latency. **PredictX** applies a gradient-boosted tree model (XGBoost) to technical indicators and order-book features to produce explainable BUY / SELL / HOLD / NO TRADE signals, and adds a news-sentiment score. **RiskGuard** evaluates volatility, position size, risk/reward and portfolio exposure before any simulated order is allowed. A React dashboard shows live market activity, AI signals, risk decisions, system performance metrics and a paper-trading account with virtual capital. The system is containerised for cloud deployment and benchmarked on throughput and latency.

## 2. Problem Statement
1. **Information overload:** prices, volumes, order books and news change continuously.
2. **Delayed or aggregated data:** many retail tools refresh periodically and hide short-term behaviour.
3. **Lack of interpretation:** beginners struggle to read technical indicators and order-book pressure.
4. **Weak risk management:** trades are placed without considering volatility or potential loss.
5. **No safe testing environment:** strategies are tried with real money first.

## 3. Objectives
1. Design a scalable, event-driven, cloud-deployable architecture for ingesting and processing market data.
2. Capture market events with nanosecond timestamps and measure processing latency (P50/P95/P99) and throughput.
3. Train and integrate a machine-learning model that produces explainable trading signals with confidence scores.
4. Build a rule-based risk engine that approves, reduces or rejects simulated trades.
5. Provide a paper-trading environment with virtual capital and live profit/loss.
6. Benchmark and report system performance.

## 4. Scope
**In scope:** simulated live market feed seeded from real NSE prices, event processing and recording, historical replay, XGBoost signal model, lexicon-based sentiment, risk engine, paper trading, monitoring dashboard, Docker-based deployment.

**Out of scope:** real exchange connectivity, real-money or automated live trading, exchange colocation or FPGA hardware, microsecond institutional execution, autonomous reinforcement-learning agents.

## 5. Proposed System Modules
| Module | Responsibility | Key techniques |
|---|---|---|
| StreamX (data engine) | Ingest ticks and order-book updates, maintain market state, compute imbalance and volatility, record events, replay history, measure latency | asyncio event bus (Kafka-compatible interface), WebSockets, Parquet |
| PredictX (AI engine) | Feature engineering, signal prediction, confidence, explanation, sentiment | XGBoost multi-class classifier, per-prediction feature contributions, lexicon sentiment (FinBERT optional) |
| RiskGuard (risk engine) | Volatility, ATR-based stop loss, position sizing, risk/reward, exposure caps, daily loss limit | Rule engine with clear reasons |
| Paper Trading | Virtual account, simulated fills at bid/ask, positions, P&L | SQLAlchemy persistence |
| Dashboard | Market, AI, Monitor, Risk, Paper Trading, Replay screens | React, Tailwind, TradingView Lightweight Charts |
| Cloud layer | Containerisation and deployment | Docker, Docker Compose, AWS EC2 (or similar) |

## 6. Methodology
1. **Data collection:** historical 5-minute and daily OHLCV bars for selected NSE stocks (RELIANCE, TCS, INFY, HDFCBANK) via the `yfinance` library.
2. **Live feed simulation:** free real-time NSE tick data is not available to students, so a stochastic simulator (geometric Brownian motion with a random order-book generator) is seeded from the last real price. The architecture can take a real feed through the same event interface.
3. **Event processing:** each event is timestamped at creation, ingestion and processing. Latency is the difference between these stamps.
4. **Model training:** labels come from the forward return over the next N bars (BUY if above +θ, SELL if below −θ, HOLD otherwise). The XGBoost classifier uses a time-ordered train/test split, so there is no look-ahead. It is evaluated with accuracy, macro-F1 and a confusion matrix, against a naive baseline.
5. **Explainability:** XGBoost's per-prediction feature contributions are turned into readable reasons.
6. **Risk evaluation:** fixed-fractional position sizing (risk 1% of capital per trade) with an ATR-based stop, a minimum risk/reward of 1.5 and exposure caps.
7. **Evaluation:** throughput (events/sec), latency percentiles, model metrics, paper-trading results.

## 7. Hardware & Software Requirements
**Hardware:** laptop with 8 GB RAM (16 GB recommended if FinBERT is enabled); cloud VM with 2 vCPU and 4 GB (for example AWS t3.medium) for deployment.
**Software:** Windows/Linux, Python 3.11, Node.js 20, Docker Desktop, Git, VS Code.
**Libraries:** FastAPI, Uvicorn, Pydantic, SQLAlchemy, pandas, PyArrow, XGBoost, scikit-learn, yfinance, React, Vite, Tailwind CSS, lightweight-charts, Recharts.

## 8. Expected Outcome
A working, containerised prototype where a user can watch a live (simulated) market, see an explained AI signal, view the risk engine's verdict and place a paper trade, plus a monitoring screen showing measured system latency and throughput.

## 9. Limitations
- The live feed is simulated, so prices do not reflect the real market in real time.
- Short-horizon price prediction is inherently noisy. Model accuracy is expected to be only modestly above baseline, and the project is honest about this.
- Model confidence is not a probability of profit.
- Python event processing is not comparable to exchange-grade HFT systems.

## 10. Future Scope
LSTM/Transformer sequence models, FinBERT on live news APIs, Kafka on a managed cluster (AWS MSK), TimescaleDB and S3 data lake, C++ hot-path processing, user authentication, broker API integration for real data feeds, strategy backtesting library.

# Software Requirements Specification (SRS)

**Product:** TradeMind AI · **Version:** 1.0 · **Date:** 23 Nov 2026

**Status legend:**
- ✅ **Implemented & tested**
- 🟡 **Implemented in simplified form**
- 🔌 **Interface/design only**
- ⏭️ **Future work**

## 1. Users

| User | Goal |
|---|---|
| Learner / trader | Watch the market, understand AI signals, test trades safely with virtual money |
| Evaluator (professor) | Verify architecture, AI and performance claims |

## 2. Functional Requirements

### 2.1 StreamX: data engine
| ID | Requirement | Status |
|---|---|---|
| SX-1 | Simulated tick + 5-level order-book stream for the 51 Nifty 50 stocks, seeded from the last real price | ✅ |
| SX-2 | Feed rate configurable at runtime (10 to 5,000 events/s; API accepts 1–20,000) | ✅ |
| SX-3 | Every event stamped with created / ingested / processed nanosecond timestamps | ✅ |
| SX-4 | Market state per symbol: last, bid/ask, spread, book, change %, candles | ✅ |
| SX-5 | Order-book imbalance `(ΣbidQty − ΣaskQty)/(ΣbidQty + ΣaskQty)` and annualised volatility | ✅ |
| SX-6 | WebSocket push to browsers (market every 250 ms, monitor every 1 s) | ✅ |
| SX-7 | Asynchronous, batched recording of events to Parquet, off the critical path | ✅ |
| SX-8 | Metrics: events/s, P50/P95/P99/max latency, histogram, queue depth, drops, recorder status | ✅ |
| SX-9 | Bounded queue with back-pressure (drops counted) | ✅ |
| SX-10 | Kafka event bus with the same interface | 🔌 (`KafkaEventBus` stub) |
| SX-11 | Historical replay of recorded sessions | ⏭️ |
| SX-12 | Real broker/exchange feed | ⏭️ |

### 2.2 PredictX: AI engine
| ID | Requirement | Status |
|---|---|---|
| PX-1 | Download real NSE 5-minute OHLCV (yfinance), cache to CSV, offline fallback | ✅ |
| PX-2 | Ten look-ahead-free features (returns, RSI, MACD hist, EMA ratio, %B, ATR %, volatility, volume z) | ✅ |
| PX-3 | XGBoost 3-class model, purged time-ordered split, balanced weights, early stopping | ✅ |
| PX-4 | Model card: macro-F1, accuracy, baselines, hit-rate, confusion matrix, feature importance | ✅ |
| PX-5 | Inference API: signal, probabilities, confidence, horizon, model version, disclaimer | ✅ |
| PX-6 | NO TRADE when confidence < threshold or annualised volatility > 80% | ✅ |
| PX-7 | Market pressure (Positive/Neutral/Negative) from live order-book imbalance | ✅ |
| PX-8 | Top-4 per-prediction feature contributions with plain-English explanations | ✅ |
| PX-9 | Sentiment score from sample headlines (finance lexicon) | 🟡 |
| PX-10 | FinBERT sentiment on live news | ⏭️ |
| PX-11 | LSTM / Transformer models | ⏭️ |

### 2.3 RiskGuard: risk engine
| ID | Requirement | Status |
|---|---|---|
| RG-1 | Stop-loss = entry − 1.5 × ATR (floor 0.2% of price) | ✅ |
| RG-2 | Position size = ⌊(equity × 1%) / stop distance⌋ | ✅ |
| RG-3 | Target from a reward multiple scaled by model edge; reject if R:R < 1.2 | ✅ |
| RG-4 | Exposure caps: 20% per stock, 60% total, never more than available cash; reduce quantity to fit | ✅ |
| RG-5 | Reject new buys once realised loss today ≥ 3% of starting capital | ✅ |
| RG-6 | Advisory AI gate: HOLD → half size; buying against SELL / NO TRADE → warning, 25% size, minimum-R:R target | ✅ |
| RG-7 | SELL (closing) always allowed up to the held quantity; oversell reduced | ✅ |
| RG-8 | Risk level LOW / MODERATE / HIGH from volatility and exposure | ✅ |
| RG-9 | Every verdict carries human-readable reasons | ✅ |

### 2.4 Paper trading
| ID | Requirement | Status |
|---|---|---|
| PT-1 | ₹10,00,000 virtual account per user, resettable | ✅ |
| PT-2 | Market orders fill at live ask (buy) / bid (sell) | ✅ |
| PT-3 | Every order passes RiskGuard; rejected orders are stored with reasons | ✅ |
| PT-4 | Positions, average price, realised/unrealised P&L, equity, exposure | ✅ |
| PT-5 | Equity curve (snapshot every 5 s) | ✅ |
| PT-6 | AI signal recorded with each order | ✅ |
| PT-7 | One-click position close | ✅ |
| PT-8 | Limit/stop orders, short selling | ⏭️ |

### 2.5 Authentication & accounts
| ID | Requirement | Status |
|---|---|---|
| AU-1 | Google Sign-In with server-side ID-token verification (signature, audience, expiry, verified email) | ✅ |
| AU-2 | Guest mode when Google is unavailable | ✅ |
| AU-3 | Signed, HTTP-only session cookie (14 days; `Secure` on HTTPS) | ✅ |
| AU-4 | All account, risk and order endpoints require a session (401 otherwise) | ✅ |
| AU-5 | Accounts isolated per user and persisted | ✅ |
| AU-6 | Sign-out | ✅ |

### 2.6 User interface
| Screen | Contents | Status |
|---|---|---|
| Landing page | Hero with live price/signal/latency card, live ticker, engines, how it works, cloud stack, CTA | ✅ |
| Market | Watchlist, live candlestick + volume chart, order book, imbalance gauge, mini signal, quick Buy/Sell | ✅ |
| AI Signals | Signal card, probabilities, explanation, factor bars, sentiment, model card | ✅ |
| Paper Trade | Two-step ticket (check → place), suggested size, verdict panel, positions, order history | ✅ |
| Portfolio & Risk | Account tiles, equity curve, exposure vs limits, per-stock risk, rule table, reset | ✅ |
| StreamX Monitor | Throughput chart, latency tiles and histogram, rate slider, pipeline view, recorder | ✅ |
| Architecture | Engine diagram, cloud mapping, honest-scope notes | ✅ |
| Responsive layout | Usable at 390 px phone width, no horizontal overflow | ✅ |

### 2.7 Cloud & deployment
| ID | Requirement | Status |
|---|---|---|
| CL-1 | Single Docker image (non-root, health check) | ✅ |
| CL-2 | 12-factor configuration through environment variables | ✅ |
| CL-3 | Public HTTPS deployment with WebSocket support | ✅ (Render) |
| CL-4 | Continuous deployment on push to `main` | ✅ |
| CL-5 | Cache policy: app files revalidate, vendor bundles cached for 1 day | ✅ |
| CL-6 | Managed Kafka, S3, RDS, Redis, autoscaling | ⏭️ |

## 3. Non-Functional Requirements

| ID | Requirement | Target | Measured |
|---|---|---|---|
| NF-1 | Processing latency at normal load | P99 < 5 ms | ✅ 26 µs (cloud), 250 µs (laptop) |
| NF-2 | Throughput | ≥ 3,000 events/s live | ✅ 3,159 events/s with P99 71 µs |
| NF-3 | Signal API response | < 200 ms | ✅ |
| NF-4 | UI update rate | ~4 market frames/s without freezing | ✅ (after precompiling Tailwind) |
| NF-5 | Recorder never blocks processing | async batched writes | ✅ background thread |
| NF-6 | Reproducibility | fixed seeds, pinned minimum versions | ✅ |
| NF-7 | Transparency | disclaimer on signals; simulated data labelled | ✅ |
| NF-8 | Testability | automated unit + e2e tests | ✅ 18 + 116 |
| NF-9 | Security | no secrets in repo; verified tokens; session cookies | ✅ |
| NF-10 | Portability | runs on Windows/Linux/Docker | ✅ |

## 4. Constraints & Assumptions
- There is no free real-time NSE tick feed, hence the simulator.
- yfinance 5-minute history covers only the last ~60 days.
- Free hosting tier: 512 MB RAM, sleeps when idle, ephemeral disk.
- This is an educational prototype, so there is no regulatory, brokerage or real-money functionality.

# Software Requirements Specification (SRS)

**Status legend**
- ✅ **CORE**: fully working in the demo
- 🟡 **PARTIAL**: works in a simplified form
- 🔌 **OPTIONAL**: implemented behind a switch, off by default
- ⏭️ **FUTURE**: documented only

## 1. Users
| User | Goal |
|---|---|
| Learner / trader | Watch the market, understand AI signals, test trades safely |
| Evaluator (professor) | Verify the architecture, AI and performance claims |

## 2. Functional Requirements

### 2.1 StreamX (Data Engine)
| ID | Requirement | Status |
|---|---|---|
| SX-1 | Generate a simulated tick + 5-level order-book stream for 4 symbols, seeded from the last real price | ✅ |
| SX-2 | Configurable event rate (10 to 5,000 events/sec) via config/API | ✅ |
| SX-3 | Stamp every event with `created_ts_ns`, `ingest_ts_ns`, `processed_ts_ns` | ✅ |
| SX-4 | Maintain market state per symbol: last price, best bid/ask, spread, book, 1-minute candles | ✅ |
| SX-5 | Compute order-book imbalance `(bidQty − askQty)/(bidQty + askQty)` and rolling volatility | ✅ |
| SX-6 | Push updates to the browser over WebSocket (throttled to ~10 UI updates/sec) | ✅ |
| SX-7 | Record events asynchronously to Parquet files (batched), off the critical path | ✅ |
| SX-8 | Metrics: events/sec, P50/P95/P99 latency, queue depth, recorder lag | ✅ |
| SX-9 | Historical replay of recorded Parquet events at 1×/10×/100× speed | 🟡 |
| SX-10 | Kafka as the event bus (same interface) | 🔌 |
| SX-11 | Real broker/exchange feed | ⏭️ |

### 2.2 PredictX (AI Engine)
| ID | Requirement | Status |
|---|---|---|
| PX-1 | Download historical OHLCV (yfinance) and cache to CSV | ✅ |
| PX-2 | Feature engineering: returns (1/5/15 bars), RSI-14, MACD, EMA-9/21 ratio, Bollinger %B, ATR-14, rolling volatility, volume z-score | ✅ |
| PX-3 | Train an XGBoost 3-class model (SELL/HOLD/BUY) with a time-based split; save the model plus a metrics JSON | ✅ |
| PX-4 | Report accuracy, macro-F1, confusion matrix, baseline comparison | ✅ |
| PX-5 | Inference API: signal, class probabilities, confidence, horizon | ✅ |
| PX-6 | NO_TRADE when confidence is below threshold (default 0.55) or when volatility is extreme | ✅ |
| PX-7 | Blend live order-book imbalance into "market pressure" (Positive/Neutral/Negative) | ✅ |
| PX-8 | Explanation: top 3 to 5 feature contributions turned into sentences | ✅ |
| PX-9 | Sentiment score per symbol from sample headlines (lexicon) | 🟡 |
| PX-10 | FinBERT sentiment | 🔌 |
| PX-11 | LSTM model | ⏭️ |

### 2.3 RiskGuard (Risk Engine)
| ID | Requirement | Status |
|---|---|---|
| RG-1 | Stop loss = entry ∓ 1.5 × ATR; target = entry ± 2.5 × ATR | ✅ |
| RG-2 | Position size = (capital × 1%) / stop distance, floored to whole shares | ✅ |
| RG-3 | Reject if risk/reward < 1.5 | ✅ |
| RG-4 | Cap single-symbol exposure at 20% and total exposure at 60% of equity; REDUCE the quantity when needed | ✅ |
| RG-5 | Reject if the daily realised loss exceeds 3% of starting capital | ✅ |
| RG-6 | Reject if the signal is NO_TRADE/HOLD, or if the side conflicts with the signal (warning only, configurable) | ✅ |
| RG-7 | Risk level LOW/MODERATE/HIGH from annualised volatility and exposure | ✅ |
| RG-8 | Every verdict lists human-readable reasons | ✅ |

### 2.4 Paper Trading
| ID | Requirement | Status |
|---|---|---|
| PT-1 | Virtual account of ₹10,00,000, resettable | ✅ |
| PT-2 | Market BUY/SELL orders fill at the current ask/bid | ✅ |
| PT-3 | Every order passes through RiskGuard first; rejected orders are stored with reasons | ✅ |
| PT-4 | Positions, average price, unrealised and realised P&L, equity curve | ✅ |
| PT-5 | Record the signal at order time so prediction can be compared with outcome | 🟡 |
| PT-6 | Limit/stop orders, short selling | ⏭️ |

### 2.5 Dashboard (UI)
| Screen | Contents | Status |
|---|---|---|
| Market Dashboard | Watchlist, live candlestick chart, order book, imbalance gauge, "Simulated feed" badge | ✅ |
| AI Intelligence | Signal card (BUY/SELL/HOLD/NO TRADE), confidence, pressure, factor bars, explanation, sentiment, model metrics | ✅ |
| StreamX Monitor | Events/sec chart, P50/P95/P99 tiles, latency histogram, queue depth, recorder lag, rate slider | ✅ |
| Risk Management | Verdict panel, exposure by symbol, volatility, risk level, limits | ✅ |
| Paper Trading | Order ticket (signal → risk → confirm), positions, orders log, P&L, equity curve | ✅ |
| Historical Replay | Choose a recorded session, play at a chosen speed, chart updates | 🟡 |

### 2.6 Cloud / Deployment
| ID | Requirement | Status |
|---|---|---|
| CL-1 | Dockerfiles for backend and frontend; docker-compose for the full stack | ✅ |
| CL-2 | Config via environment variables (12-factor) | ✅ |
| CL-3 | Deploy on one cloud VM (AWS EC2 free tier or similar) | 🟡 |
| CL-4 | Kafka + Postgres + Redis compose profile | 🔌 |
| CL-5 | S3 upload of Parquet files (boto3, if credentials present) | 🔌 |
| CL-6 | API Gateway, autoscaling, MSK, TimescaleDB | ⏭️ |

## 3. Non-Functional Requirements
| ID | Requirement | Target |
|---|---|---|
| NF-1 | Processing latency (ingest → processed) at 1,000 ev/s | P99 < 5 ms on a laptop |
| NF-2 | Sustained throughput (benchmark script, no UI) | ≥ 20,000 ev/s |
| NF-3 | Signal API response time | < 200 ms |
| NF-4 | UI update rate | ~10 fps, no browser freeze |
| NF-5 | Recorder must not block the processing loop | Async batched writes |
| NF-6 | Reproducibility | Fixed random seeds; `requirements.txt` / `package-lock.json` |
| NF-7 | Transparency | Disclaimer on all signals; simulated data clearly labelled |
| NF-8 | Testability | pytest for risk rules, features, broker |

The targets are goals. Report the actual measured numbers in your final report, whatever they turn out to be.

## 4. Constraints & Assumptions
- No free real-time NSE tick feed, hence the simulator.
- yfinance 5-minute data only covers the last ~60 days. Daily data covers years.
- Single-user prototype, so no authentication.

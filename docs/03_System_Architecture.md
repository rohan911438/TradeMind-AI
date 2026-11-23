# System Architecture & Design

## 1. High-Level Architecture

```
                         ┌──────────────────────────────────────────────┐
                         │           React Dashboard (Vite)             │
                         │ Market | AI | Monitor | Risk | Paper | Replay│
                         └───────────────┬──────────────────────────────┘
                              REST /api  │  WebSocket /ws
                         ┌───────────────▼──────────────────────────────┐
                         │          FastAPI  (API layer)                │
                         └──┬─────────────┬──────────────┬──────────────┘
                            │             │              │
        ┌───────────────────▼──┐   ┌──────▼───────┐  ┌───▼────────────┐
        │       StreamX        │   │   PredictX   │  │   RiskGuard    │
        │ Simulator / Replay   │   │ features.py  │  │ rules engine   │
        │        │             │   │ XGBoost      │  │ sizing, caps   │
        │   EventBus ──────────┼──▶│ explain      │  └───▲────────────┘
        │ (asyncio | Kafka)    │   │ sentiment    │      │
        │        │             │   └──────┬───────┘      │
        │  Processor → State   │──────────┘ market state │
        │        │      │      │                  ┌──────┴─────────┐
        │  Recorder   Metrics  │                  │ Paper Broker   │
        └────┬─────────────────┘                  └──────┬─────────┘
             │ Parquet (S3-ready)                        │ SQLAlchemy
        ┌────▼──────────┐                         ┌──────▼─────────┐
        │ data/events/  │                         │ SQLite/Postgres│
        └───────────────┘                         └────────────────┘
```

**Cloud mapping (for the presentation):**
| Prototype | Cloud equivalent |
|---|---|
| asyncio EventBus | Apache Kafka / AWS MSK |
| Parquet in `data/events/` | Amazon S3 data lake |
| SQLite | Amazon RDS PostgreSQL / TimescaleDB |
| In-memory market state | Redis / ElastiCache |
| Docker Compose on one VM | ECS / EKS with autoscaling |
| FastAPI | API Gateway + containers |

## 2. Data Flow (one tick)
1. `FeedSimulator` creates a `MarketEvent` (`created_ts_ns`) and publishes it to `EventBus`.
2. `Processor` consumes it (`ingest_ts_ns`), updates `MarketState` (price, book, candle, imbalance, volatility) and sets `processed_ts_ns`.
3. `Metrics` records `processed − ingest` (processing latency) and `processed − created` (end-to-end latency).
4. `Recorder` gets the event through a separate queue and flushes batches of 5,000 events (or every 2 s) to Parquet.
5. The WebSocket broadcaster sends a throttled snapshot (every 100 ms) to connected clients.
6. On request, `PredictX` builds features from recent candles plus live imbalance and returns a `Signal`.
7. On an order, `PaperBroker` → `RiskGuard.evaluate()` → fill or reject → store in DB.

## 3. Folder Structure
```
COLEZ/
├── CLAUDE.md
├── docs/
├── docker-compose.yml
├── backend/
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   ├── app/
│   │   ├── main.py              # FastAPI app, lifespan starts StreamX tasks
│   │   ├── config.py            # pydantic-settings
│   │   ├── schemas.py           # shared pydantic models
│   │   ├── api/                 # routes_market, routes_predict, routes_risk,
│   │   │                        # routes_paper, routes_monitor, routes_replay, ws
│   │   ├── streamx/             # events, bus, simulator, processor, state,
│   │   │                        # recorder, replay, metrics
│   │   ├── predictx/            # data, features, train, model, explain, sentiment
│   │   ├── riskguard/           # engine.py, rules.py
│   │   ├── paper/               # broker.py
│   │   └── db/                  # session.py, models.py
│   ├── data/
│   │   ├── raw/                 # cached yfinance CSVs
│   │   ├── events/              # Parquet event recordings
│   │   └── news/sample_headlines.json
│   ├── models/                  # xgb_model.json, metrics.json, feature_list.json
│   ├── scripts/benchmark.py
│   └── tests/
└── frontend/
    ├── Dockerfile
    ├── vite.config.ts           # proxy /api, /ws → :8000
    └── src/
        ├── App.tsx              # sidebar layout + routes
        ├── lib/api.ts, lib/ws.ts, lib/format.ts
        ├── components/          # SignalCard, OrderBook, PriceChart, StatTile, ...
        └── pages/               # Dashboard, Intelligence, Monitor, Risk, Paper, Replay
```

## 4. Core Schemas

### MarketEvent
```python
class MarketEvent(BaseModel):
    seq: int
    symbol: str                   # "RELIANCE"
    type: Literal["TRADE", "BOOK"]
    price: float                  # last trade price
    qty: int
    bids: list[tuple[float, int]] # 5 levels, best first
    asks: list[tuple[float, int]]
    created_ts_ns: int
    ingest_ts_ns: int | None = None
    processed_ts_ns: int | None = None
```

### Signal (PredictX output)
```json
{
  "symbol": "RELIANCE",
  "signal": "BUY",                       // BUY | SELL | HOLD | NO_TRADE
  "confidence": 0.62,
  "probabilities": {"SELL": 0.14, "HOLD": 0.24, "BUY": 0.62},
  "horizon": "next 30 minutes (6 x 5-min bars)",
  "market_pressure": "Positive",         // from order-book imbalance
  "imbalance": 0.41,
  "sentiment": {"score": 0.3, "label": "Positive", "headlines_used": 4},
  "top_factors": [
    {"feature": "rsi_14", "value": 38.2, "contribution": 0.21, "text": "RSI is near oversold (38), which historically preceded rebounds"},
    {"feature": "imbalance", "value": 0.41, "contribution": 0.15, "text": "Buy-side order-book pressure is strong"}
  ],
  "explanation": "The model leans BUY mainly because ...",
  "model_version": "xgb-2026-11-23",
  "generated_at": "2026-11-23T10:15:00Z",
  "disclaimer": "Educational prototype. Confidence is not a probability of profit. Not financial advice."
}
```

### RiskVerdict (RiskGuard output)
```json
{
  "status": "REDUCED",                   // APPROVED | REDUCED | REJECTED
  "symbol": "RELIANCE", "side": "BUY",
  "requested_qty": 200, "approved_qty": 120,
  "entry": 1451.0, "stop_loss": 1438.4, "target": 1472.0,
  "risk_reward": 1.67, "risk_amount": 1512.0,
  "annualised_volatility": 0.24, "risk_level": "MODERATE",
  "exposure_symbol_after": 0.174, "exposure_total_after": 0.31,
  "reasons": ["Quantity reduced to keep single-stock exposure under 20%"]
}
```

### DB tables (SQLAlchemy)
- `account(id, starting_cash, cash, created_at)`
- `position(symbol PK, qty, avg_price, realised_pnl)`
- `order(id, ts, symbol, side, requested_qty, filled_qty, fill_price, status, risk_status, risk_reasons JSON, signal JSON)`
- `equity_snapshot(ts, equity)` (written every 10 s)

## 5. API Contract
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Status + feed mode (simulated/replay) |
| GET | `/api/symbols` | Watchlist with last price & change |
| GET | `/api/market/{symbol}/snapshot` | Book, last price, imbalance, volatility |
| GET | `/api/market/{symbol}/candles?limit=300` | 1-minute candles from the live state |
| WS | `/ws/market` | Throttled snapshots for all symbols |
| GET | `/api/predict/{symbol}` | Signal |
| GET | `/api/predict/model-info` | Metrics JSON, feature importance |
| GET | `/api/sentiment/{symbol}` | Sentiment score + headlines |
| POST | `/api/risk/evaluate` | `{symbol, side, qty?}` → RiskVerdict |
| GET | `/api/risk/portfolio` | Exposure, volatility per position, limits |
| POST | `/api/paper/orders` | `{symbol, side, qty}` → order + verdict |
| GET | `/api/paper/portfolio` | Cash, equity, positions, P&L |
| GET | `/api/paper/orders` | Order history |
| GET | `/api/paper/equity` | Equity curve |
| POST | `/api/paper/reset` | Reset account |
| GET | `/api/monitor/metrics` | Events/sec, P50/P95/P99, queue depth, recorder lag |
| POST | `/api/monitor/rate` | `{events_per_sec}` change simulator rate |
| WS | `/ws/monitor` | Metrics every 1 s |
| GET | `/api/replay/sessions` | Recorded Parquet sessions |
| POST | `/api/replay/start` | `{session, speed}` |
| POST | `/api/replay/stop` | Back to the simulator |

## 6. Key Algorithms

**Simulator price:** `p_t = p_{t−1} · exp((μ − σ²/2)Δt + σ√Δt·Z)`, with σ taken from the stock's historical volatility. Book levels are spread around the mid price with random quantities. A slow-moving "regime" variable skews bid/ask quantity, so imbalance carries some information and the demo shows meaningful pressure changes.

**Labels:** `fwd_ret = close[t+6]/close[t] − 1`. BUY if > +0.3%, SELL if < −0.3%, else HOLD. Tune θ so the classes are roughly balanced.

**Explanation:** `booster.predict(dmatrix, pred_contribs=True)` gives per-feature contributions for the predicted class. Take the top 3 to 5 by absolute value and map each to a sentence template, e.g. `rsi_14 < 35` → "RSI is near oversold".

**Position sizing:** `qty = floor((equity × 0.01) / |entry − stop|)`, then capped by exposure limits.

**Latency percentiles:** a ring buffer of the last 10,000 latencies, with `numpy.percentile` computed every second.

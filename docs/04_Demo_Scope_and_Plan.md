# Demo Guide & Viva Preparation

**Demo URL:** https://trademind-ai-ujm6.onrender.com · **Local fallback:** double-click `run.bat` → http://localhost:8000

## 1. The demo promise
> "Open TradeMind AI, sign in with Google, watch a live market stream, see what the AI thinks and why, see the risk engine's verdict, place a paper trade, and see the system's own latency numbers."

## 2. Before you present (checklist)
- [ ] **10 minutes before:** open the demo URL to wake the free-tier server (the first load takes about a minute)
- [ ] Sign in with Google once and confirm the account loads
- [ ] Reset the paper account (Portfolio & Risk → Reset account, click twice)
- [ ] Open `run.bat` locally as a backup, on a second browser tab
- [ ] Keep the backup screen recording ready (3 minutes, the full flow)
- [ ] Zoom the browser to 110–125% for the projector

## 3. Seven-minute script

| Time | Screen | What to show and say |
|---|---|---|
| 0:00 | Slides | **Problem:** information overload, delayed data, no interpretation, poor risk control, no safe testing |
| 0:30 | Landing page | Three engines. Point at the live price card, AI signal and P99 latency; these are real values from the server |
| 1:00 | Sign-in | "Continue with Google": the ID token is verified on the server and gives each user their own ₹10 lakh account |
| 1:20 | **Market** | Live candles, order book, imbalance gauge. Point at the **SIMULATED** badge and explain it honestly |
| 2:10 | **StreamX Monitor** | Drag the slider from 200 to 3,000 events/s; throughput rises and P50 stays around 10 µs. Mention async Parquet recording |
| 3:00 | **AI Signals** | Signal, probabilities, top factors in plain English, explanation. Open the model card: macro-F1 0.39 vs 0.25, hit-rate 25.6% vs 20.3% chance. Say: *"Confidence is not a probability of profit."* |
| 4:30 | **Paper Trade** | Enter 2,000 shares → *Check with RiskGuard* → **REDUCED** or **REJECTED** with reasons. Click *Use suggested size* → **APPROVED** → place it → position and live P&L appear |
| 5:30 | **Portfolio & Risk** | Exposure against the 20% / 60% limits, equity curve, the rules table |
| 6:10 | **Architecture** | Cloud mapping table: Kafka, S3, RDS, Redis, ECS. Docker + Render + auto-deploy from GitHub |
| 6:40 | Slides | Results, limitations, future scope |

**If no stock shows BUY when you need it:** signals change every 10–20 s. Wait a moment, switch symbols, or demonstrate the **REJECTED** path first; it is just as important.

## 4. Likely viva questions

| Question | Answer |
|---|---|
| Why is the feed simulated? | There is no free real-time NSE tick feed. The simulator starts from real NSE prices with real volatility, and a real feed plugs into the same `EventBus` interface. |
| How accurate is the model? | Macro-F1 0.39 vs 0.25 baseline; BUY/SELL hit-rate 25.6% vs 20.3% chance. Accuracy (43.8%) is below "always HOLD" (59%) because HOLD dominates and we use balanced class weights; accuracy is the wrong metric here. |
| How do you avoid look-ahead bias? | Features only use past bars (a unit test proves it), the split is time-ordered, and the 6 rows before each boundary are purged because their labels look ahead. |
| Why XGBoost and not LSTM? | Tabular indicator features, about 17k rows, fast training, and built-in per-prediction explanations. LSTM is future work. |
| How is the explanation generated? | XGBoost `pred_contribs` (SHAP-style) values for the predicted class; the top four are turned into sentences. |
| What is order-book imbalance? | (bid qty − ask qty)/(bid qty + ask qty) over the top 5 levels; it measures short-term buy vs sell pressure. |
| How is latency measured? | Monotonic nanosecond timestamps at creation, ingest and processing, with percentiles over a 10,000-event ring buffer. |
| How is position size computed? | Risk 1% of equity: qty = 1% × equity / (1.5 × ATR), then capped at 20% per stock, 60% total and available cash. |
| Can a user bypass RiskGuard? | No. The order endpoint re-runs the AI signal and RiskGuard at submit time with the current price. |
| How does Google login work? | The browser gets a signed ID token from Google, the server verifies its signature, audience and expiry, and then sets a signed session cookie. |
| Where is the cloud? | Docker image on Render with HTTPS, WebSockets, health checks, env-based config and auto-deploy from GitHub. Each component maps to a managed AWS service. |
| What if the recorder is slow? | It has its own buffer and writes in a background thread, so processing never waits for disk. |
| Is this HFT? | No. It is an educational prototype inspired by HFT architecture: microsecond processing, millisecond end to end. |
| What did testing find? | Five UI/UX defects, two timing bugs and a cache issue, all fixed (see the Test Report). |

## 5. Final report outline
1. Introduction
2. Background: technical indicators, order books, gradient boosting, event-driven and cloud architecture
3. Requirements (doc 02)
4. Design (doc 03)
5. Implementation, one section per engine, with screenshots
6. Results: model metrics, latency table, sample verdicts, a paper-trading session
7. Testing (doc 06)
8. Deployment (doc 07)
9. Limitations
10. Conclusion & future work

Appendix: API reference and setup guide.

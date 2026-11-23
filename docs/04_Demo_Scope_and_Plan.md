# Demo Scope, Timeline & Viva Script

## 1. The demo promise
> "Open TradeMind AI, watch a live market stream, see what the AI thinks and why, see the risk engine's verdict, place a paper trade, and see the system's own latency numbers."

Everything in that sentence must work. Nothing else is required.

## 2. Feature triage
| Must work (marks come from here) | Nice if time allows | Talk about only (slides) |
|---|---|---|
| Simulated live feed + chart + order book | Historical replay | Kafka / MSK at scale |
| StreamX monitor (P50/P95/P99, ev/s) | Docker deploy on AWS EC2 | FinBERT, LSTM |
| XGBoost signal + explanation | Kafka compose profile | TimescaleDB, S3 lake |
| RiskGuard verdict with reasons | Equity curve chart | C++ hot path, FPGA |
| Paper trading with P&L | FinBERT switch | Auth, multi-user |
| Benchmark results table | | Real broker feed |

## 3. Timeline (about 7 weeks; adjust to your deadline)
| Week | Stage | Prompts (doc 05) | Deliverable you can show your guide |
|---|---|---|---|
| 1 | Setup + StreamX core | P0–P3 | Backend streaming fake ticks, metrics endpoint |
| 2 | Dashboard | P4–P5 | Live chart, order book, monitor page |
| 3 | PredictX training | P6 | Trained model + metrics.json + confusion matrix |
| 4 | PredictX live | P7–P8 | AI Intelligence page with explained signals |
| 5 | RiskGuard + Paper trading | P9–P11 | Full flow: signal → risk → trade → P&L |
| 6 | Replay, benchmark, Docker | P12–P14 | Benchmark table, docker-compose up works |
| 7 | Polish + report + rehearsal | P15 | Demo mode, screenshots, README, final report |

**Rule:** at the end of every week the app must run. Never leave it broken overnight. Commit after each prompt.

## 4. Seven-minute demo script
1. **(30 s) Problem.** One slide covering the five problems.
2. **(45 s) Architecture.** Three engines, and the cloud mapping table from doc 03.
3. **(1 min) Market Dashboard.** Live RELIANCE chart, order book updating. Point at the "Simulated feed" badge and explain why the feed is simulated.
4. **(1 min) StreamX Monitor.** Drag the rate slider from 100 to 2,000 ev/s. Show events/sec rising and P99 staying low. Mention that events are recorded to Parquet asynchronously.
5. **(1.5 min) AI Intelligence.** RELIANCE signal card: confidence, market pressure, top factors, explanation. Open "Model info" (test accuracy vs baseline, confusion matrix). State plainly that confidence is not a probability of profit.
6. **(1.5 min) RiskGuard + Paper Trading.** Try a BUY of 2,000 shares and show it REDUCED, with the reasons. Then trade a sensible size, which is APPROVED and filled. Show the position and live P&L. Then show one REJECTED case (NO_TRADE signal or poor risk/reward).
7. **(30 s) Benchmark + deployment.** Results table, plus `docker compose up`. If deployed, show the cloud URL.
8. **(15 s) Limitations and future scope.**

**Backup plan:** record a 3-minute screen video of the full flow the day before, in case Wi-Fi or a laptop fails.

## 5. Likely viva questions (prepare answers)
1. *Why simulated data?* There is no free real-time NSE tick feed. The `EventBus` interface means a real feed is a drop-in source.
2. *How accurate is your model?* Quote the real test-set numbers next to the baseline. Short-term prediction is noisy, which is why RiskGuard exists.
3. *How do you avoid look-ahead bias?* Time-ordered split, features use only past bars, and labels use future bars that the features never see.
4. *Why XGBoost over LSTM?* Tabular indicator features, small data, fast training, built-in explainability. LSTM is future work.
5. *Where is the "cloud"?* Containerised, stateless API, 12-factor config, Kafka-compatible bus, S3-ready storage, deployed on a VM. Use the mapping table.
6. *What is order-book imbalance?* (bidQty − askQty)/(bidQty + askQty), which measures short-term buy versus sell pressure.
7. *How is latency measured?* Nanosecond timestamps at creation, ingest and processing, with percentiles over a ring buffer.
8. *How is position size computed?* 1% of equity at risk divided by the ATR stop distance, then capped by exposure limits.
9. *What happens if the recorder is slow?* It has its own queue, so processing is not blocked. Recorder lag is shown on the monitor.
10. *Is this HFT?* No. It is an educational prototype inspired by HFT architecture, at millisecond rather than microsecond scale.

## 6. Final report outline
1. Introduction · 2. Literature/background (technical indicators, order books, gradient boosting, event-driven and cloud architecture) · 3. Requirements (doc 02) · 4. Design (doc 03) · 5. Implementation (one section per engine, with screenshots) · 6. Results (model metrics, benchmark table, sample risk verdicts, paper-trading session) · 7. Limitations · 8. Conclusion & future work · Appendix: API list, setup guide.

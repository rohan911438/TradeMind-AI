---
marp: true
theme: default
paginate: true
size: 16:9
style: |
  section { font-size: 22px; padding: 48px 64px; }
  h1 { font-size: 40px; }
  h2 { font-size: 32px; color: #0f766e; }
  table { font-size: 17px; }
  blockquote { font-size: 19px; border-left: 4px solid #0f766e; }
---

<!-- _paginate: false -->

# TradeMind AI

## A Cloud-Based Intelligent Trading and High-Frequency Market Intelligence Platform

**Project Report Presentation**

| | |
|---|---|
| **Domain** | Cloud Computing with Artificial Intelligence Integration |
| **Project Type** | Research Survey, System Design and Implemented Prototype |
| **Presented by** | *[Team Members]* |
| **Department** | *[Department Name]* |
| **Institution** | *[College Name]* |
| **Academic Year** | *[Academic Year]* |

**Live demo:** https://trademind-ai-ujm6.onrender.com · **Source:** https://github.com/rohan911438/TradeMind-AI

---

## Table of Contents

1. Introduction
2. Objectives of the Survey
3. Literature Survey
4. Research Gap and Problem Statement
5. Proposed System: TradeMind AI
6. System Architecture and Technologies
7. Findings
8. Conclusion
9. Future Scope
10. References

---

## 1. Introduction

- Financial markets generate large volumes of continuously changing data: **prices, trades, order-book updates and financial news**.
- Conventional trading applications often rely on **periodic snapshots or aggregated data**, which may not preserve every short-term market event.
- Traders also struggle to **interpret market information, predict price movements and manage portfolio risk**.
- **Cloud computing** provides scalable infrastructure for collecting, processing and storing market data.
- **Artificial Intelligence (AI)** can analyse historical patterns, market indicators and financial sentiment to support trading decisions.

> **Project vision:** TradeMind AI is a cloud-based intelligent trading and market-intelligence platform that combines high-frequency market-data processing, AI-driven analysis, risk management and simulated (paper) trading.

---

## 2. Objectives of the Survey

The survey studies existing research and technologies for AI-powered trading and cloud-based market-data systems, in order to:

1. Understand how **high-frequency trading (HFT) systems** capture and process market events.
2. Study **market microstructure**: order books, trades, bid-ask prices and order-book imbalance.
3. Review **machine-learning and deep-learning techniques** used for financial prediction.
4. Explore **cloud architectures** for scalable data ingestion, processing and storage.
5. Examine **risk-management methods** and realistic evaluation of trading strategies.
6. Identify **limitations** in existing approaches and define a feasible project contribution.

---

## 3. Literature Survey

| Research / Resource | Main focus | Relevance to TradeMind AI |
|---|---|---|
| Budish, Cramton & Shim (2015), *The High-Frequency Trading Arms Race* | Market design and latency competition | Explains why speed and market microstructure matter |
| Aquilina, Budish & O'Neill (2022), *Quantifying the High-Frequency Trading "Arms Race"* | Empirical measurement of latency races | Shows that many HFT interactions happen at microsecond timescales |
| Zhang, Zohren & Roberts (2019), *DeepLOB* | Deep learning on limit-order-book data for short-horizon prediction | Motivates AI analysis beyond daily closing prices |
| AWS Architecture Blog, *Optimize tick-to-trade latency…* | Low-latency architecture patterns | Informs event processing and asynchronous persistence |
| Apache Kafka documentation | Distributed event streaming and replay | Supports scalable ingestion and event pipelines |
| NSE real-time market-data documentation | Real-time, market-depth and tick-by-tick data products | Context for Indian market-data access |

> **Survey observation:** A trading system must distinguish between *sampling* data at fixed intervals and *capturing every market event*. A 100 ms snapshot can miss several events that occur within that interval.

---

## 4. Research Gap and Problem Statement

**Observed limitations**
- Periodic price snapshots may hide short-lived market activity.
- Price-prediction models alone do not explain order-book behaviour.
- Predictions often ignore uncertainty, transaction costs and portfolio risk.
- Synchronous database writes can slow a latency-sensitive processing path.
- Backtests mislead when future information **leaks** into training or costs are ignored.

**Problem statement**
To design and build a cloud-based platform that ingests timestamped market events, processes them efficiently, applies AI to market data, and provides **risk-aware trading insights** through a simulated trading environment.

> **Contribution:** Integrate high-frequency event engineering, explainable AI market intelligence and risk controls in one cloud-deployed educational prototype, with honest, measured evaluation.

---

## 5. Proposed System: TradeMind AI

**1. StreamX: Market Data Engine**
- Receives market events from an authorised data source or a controlled simulator (the prototype uses a simulator seeded from **real NSE prices**).
- Records timestamps, symbols, event types, prices and quantities; maintains in-memory market state and streaming features.
- Persists events **asynchronously** (Parquet) and measures P50/P95/P99 latency.

**2. PredictX: AI Intelligence Engine**
- **XGBoost** model on technical and volatility features (implemented); LSTM explored as future work.
- News sentiment: finance lexicon on sample headlines (implemented); **FinBERT** planned.
- Produces **explainable BUY / SELL / HOLD / NO TRADE** signals with per-prediction reasons.

**3. RiskGuard: Risk Management Engine**
- Measures volatility and portfolio exposure; applies 1%-risk position sizing and ATR stop-loss.
- Checks risk/reward, exposure caps and a daily loss limit; **approves, reduces or rejects** each order.
- Supports paper trading with ₹10,00,000 of virtual funds per user (Google Sign-In).

> **Important:** Signals are decision-support outputs, not guaranteed predictions or investment advice.

---

## 6. System Architecture and Technologies

**Data flow:** Market data source / simulator → **StreamX** ingestion (event bus) → event processing (timestamps, validation, in-memory state) → feature generation (returns, volatility, order-book imbalance) → **PredictX + RiskGuard** (AI inference and risk checks) → dashboard and paper-trading simulator

| Layer | Implemented in prototype | Production / planned |
|---|---|---|
| Frontend | HTML + Tailwind CSS, TradingView Lightweight Charts | React + Tailwind CSS |
| Backend | Python, FastAPI (REST + WebSockets) | Same, behind API Gateway |
| Streaming | asyncio event bus (Kafka-compatible interface) | Apache Kafka / AWS MSK |
| AI / ML | XGBoost, finance-lexicon sentiment | + LSTM (PyTorch), FinBERT |
| Market state | In-memory state | Redis / ElastiCache |
| Storage | SQLite (accounts), Parquet (event history) | PostgreSQL + TimescaleDB, AWS S3 |
| Auth | Google Sign-In (OpenID Connect) | Same |
| Cloud | Docker on Render, auto-deploy from GitHub | AWS ECS / EKS with autoscaling |

> **Architecture principle:** Keep the time-sensitive processing path separate from slower persistence and archival. All performance figures are **measured** on the deployed prototype.

---

## 7. Findings

**From the survey**
- **Event-level data matters:** fixed-interval snapshots and tick-by-tick capture give different levels of market detail.
- **Latency must be measured carefully:** arrival, processing, persistence and end-to-end latency are separate metrics.
- **Cloud involves trade-offs:** scalability and managed infrastructure versus network and scheduling variability in tail latency.
- **AI needs meaningful features:** order-book imbalance, volatility and sentiment complement price indicators.
- **Risk management is essential:** a prediction should never trigger a trade automatically.
- **Evaluation must be realistic:** chronological testing, costs, slippage and baseline comparisons.

**Measured in the TradeMind AI prototype**

| Metric | Result |
|---|---|
| Processing latency (cloud, 200 events/s) | P50 **8.4 µs** · P95 16.3 µs · P99 26.4 µs |
| Throughput (laptop) | **3,159 events/s** with P99 71 µs |
| Model macro-F1 (held-out, real NSE data) | **0.390** vs 0.248 baseline |
| BUY/SELL hit-rate | **25.6%** vs 20.3% chance |
| Testing | 17 unit + 67 end-to-end checks passing |

Evaluation metrics used: P50/P95/P99 latency, throughput, dropped events, **precision, recall and macro-F1** (classification). Sharpe ratio and maximum drawdown are planned for strategy back-testing.

---

## 8. Conclusion

- TradeMind AI demonstrates a unified approach to cloud-based market intelligence, combining **high-frequency data processing, AI-based analysis and risk-aware simulated trading**.
- The survey shows that effective trading intelligence needs more than price prediction. It also needs **reliable event capture, efficient processing, meaningful features, risk controls and careful evaluation**.
- The modular **StreamX, PredictX and RiskGuard** engines provide a foundation for developing and testing these capabilities.
- The model shows a **modest but honest edge** over baselines. This confirms that short-horizon prediction is noisy and that RiskGuard must sit between every signal and every order.

> **Outcome achieved:** A working, cloud-deployed educational prototype demonstrating event ingestion, market analytics, explainable AI signals, performance monitoring, Google sign-in and paper trading.

---

## 9. Future Scope

- Integrate **licensed exchange-grade** tick-by-tick or market-depth data where access is available.
- Explore faster event processing and selected **C++ optimisations**.
- Add **distributed stream processing (Kafka / AWS MSK)** and autoscaling for higher workloads.
- Investigate advanced order-book models (**DeepLOB**), temporal deep learning (LSTM / Transformers) and reinforcement learning.
- Use **FinBERT** on live financial news, with uncertainty estimation and model-drift monitoring.
- Add **historical replay**, back-testing with transaction costs, Sharpe ratio and drawdown.
- Add multi-asset support, richer portfolio analytics and **persistent cloud storage** (PostgreSQL / S3).
- Strengthen secure deployment, fault tolerance and disaster recovery.

> **Development boundary:** The prototype uses real historical NSE data plus a calibrated simulated live feed, and **simulated trading only**; no real-money order execution.

---

## 10. References

1. Budish, E., Cramton, P., & Shim, J. (2015). The High-Frequency Trading Arms Race: Frequent Batch Auctions as a Market Design Response. *The Quarterly Journal of Economics*, 130(4), 1547–1621. https://doi.org/10.1093/qje/qjv027
2. Aquilina, M., Budish, E., & O'Neill, P. (2022). Quantifying the High-Frequency Trading "Arms Race". *The Quarterly Journal of Economics*, 137(1), 493–564. https://doi.org/10.1093/qje/qjab032
3. Zhang, Z., Zohren, S., & Roberts, S. (2019). DeepLOB: Deep Convolutional Neural Networks for Limit Order Books. *IEEE Transactions on Signal Processing*, 67(11), 3001–3012. https://doi.org/10.1109/TSP.2019.2907260
4. Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*, 785–794. https://doi.org/10.1145/2939672.2939785
5. Amazon Web Services. Optimize tick-to-trade latency for digital assets exchanges and trading platforms on AWS. *AWS Architecture Blog*. https://aws.amazon.com/blogs/architecture/
6. Apache Software Foundation. *Apache Kafka Documentation*. https://kafka.apache.org/documentation/
7. National Stock Exchange of India. *Real-Time Market Data*. https://www.nseindia.com/market-data/real-time-data-subscription

<small>Verify the exact AWS article URL before formal submission, and add any other papers the team reads in full.</small>

---

<!-- _paginate: false -->

# Thank You

## TradeMind AI

**Cloud-Based Intelligent Trading & High-Frequency Market Intelligence Platform**

*Capturing market events. Understanding market behaviour. Supporting smarter decisions.*

**Live demo:** https://trademind-ai-ujm6.onrender.com

### Questions & Discussion

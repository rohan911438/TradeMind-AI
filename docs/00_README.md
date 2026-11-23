# TradeMind AI: Documentation

**Live product:** https://trademind-ai-ujm6.onrender.com · **Source:** https://github.com/rohan911438/TradeMind-AI

| # | Document | Audience | Use it for |
|---|---|---|---|
| 01 | [Project Synopsis](01_Project_Synopsis.md) | College / guide | Abstract, problem, objectives, methodology, results, limitations |
| 02 | [Software Requirements Specification](02_SRS.md) | Evaluators | Every requirement with its implementation status |
| 03 | [System Architecture & Design](03_System_Architecture.md) | Developers / viva | Components, data flow, schemas, full API reference, algorithms |
| 04 | [Demo Guide & Viva Preparation](04_Demo_Scope_and_Plan.md) | Presenter | 7-minute demo script, backup plan, likely questions with answers |
| 05 | [Development Log & Extension Prompts](05_Prompt_Sequence.md) | Developers | How the product was built, and prompts for extending it with Claude Code |
| 06 | [Test Report](06_Test_Report.md) | Evaluators | Test strategy, results, defects found and fixed |
| 07 | [Deployment Guide](07_Deployment_Guide.md) | Ops | Render (current), Docker, AWS EC2, configuration |

## Status at a glance (23 Nov 2026)

| Area | Status |
|---|---|
| StreamX (data engine) | ✅ Live: simulated feed, market state, latency metrics, Parquet recorder |
| PredictX (AI engine) | ✅ Live: XGBoost on real NSE data, explanations, sentiment blend |
| RiskGuard (risk engine) | ✅ Live: sizing, stops, R:R gate, exposure and loss limits |
| Paper trading | ✅ Live: per-user accounts, P&L, equity curve |
| Authentication | ✅ Google Sign-In + guest mode |
| Cloud deployment | ✅ Docker on Render, auto-deploy from GitHub |
| Tests | ✅ 17 unit + 67 end-to-end checks passing (local and production) |
| Kafka, FinBERT, LSTM, S3, RDS | ⏭️ Designed and mapped; future work |

# TradeMind AI — Documentation Pack

| # | Document | Use it for |
|---|----------|-----------|
| 01 | [Project Synopsis](01_Project_Synopsis.md) | Submit to college / guide approval. Abstract, objectives, scope, methodology. |
| 02 | [Software Requirements Specification](02_SRS.md) | Functional + non-functional requirements, with each feature tagged as working, simulated or future. |
| 03 | [System Architecture & Design](03_System_Architecture.md) | Architecture diagram, data flow, schemas, API contract, folder structure. **Claude Code reads this.** |
| 04 | [Demo Scope, Timeline & Viva Script](04_Demo_Scope_and_Plan.md) | What to show, week-by-week plan, 7-minute demo script, likely viva questions. |
| 05 | [Prompt Sequence](05_Prompt_Sequence.md) | The exact prompts to give Claude Code, in order, with a "check before moving on" list for each. |

Also see `../CLAUDE.md`. Claude Code loads it automatically in every session, so it keeps the scope tight.

## The one-line scope decision
> **Four things work end-to-end:** simulated live feed (StreamX), an AI signal (PredictX), a risk check (RiskGuard) and paper trading.
> Everything else (Kafka, FinBERT, LSTM, S3, TimescaleDB, C++) is either optional behind a switch or listed as future work.

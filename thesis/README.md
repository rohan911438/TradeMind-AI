# TradeMind AI: B.Tech Project Thesis

| File | What it is |
|---|---|
| [`main.md`](main.md) | **The complete thesis**: preliminary pages, Chapters 1–10, appendices and references, with every result measured |
| `TradeMind_AI_Thesis.docx` | Word version of `main.md` (Times New Roman 12 pt, 1.5 spacing, A4) for college formatting and printing |
| [`figures/`](figures) | All charts (generated from the benchmark results) and the rendered architecture diagrams |
| [`benchmarks/`](benchmarks) | The benchmark suite and raw results (`results/*.json`) |

## Benchmarks (Chapter 8)

| Experiment | Script | Question |
|---|---|---|
| A: Capture interval | `bench_stream.py A` | How much do fixed-interval snapshots hide compared with event capture? |
| B: Persistence | `bench_stream.py B` | Sync vs async persistence: latency, throughput, integrity |
| C: Load | `bench_stream.py C` | 100 → 20,000 events/s: throughput, P50/P95/P99, CPU, memory, drops |
| D: Model | `bench_model.py D` | XGBoost vs six baselines on the held-out period (51 stocks), with calibration and per-stock results |
| D2: More stocks? | `compare_models.py` | Four-stock vs 51-stock model on identical test rows, paired bootstrap |
| E: Trading | `bench_model.py E` | Paper-trading simulation with 0–20 bps costs, with and without RiskGuard |
| F: Decision path | `bench_model.py F` | Signal and RiskGuard latency breakdown |
| G: Cloud | `bench_api.py` | Local vs Render API latency, WebSocket delivery, in-cloud pipeline metrics |

### Headline results (laptop: Intel Core i3-6006U, Windows 10; cloud: Render free tier, Singapore)

- **Capture:** 100 ms snapshots hide **80–98%** of events; event capture hides none.
- **Persistence:** async Parquet P99 is **65 µs** at 1,000 events/s; synchronous fully durable SQLite manages only **~60 events/s**.
- **Load:** 5,000 events/s with P99 **29 µs** and **0 drops**; saturates at about 8.8k events/s on one CPU core.
- **Model:** macro-F1 **0.372** vs 0.252 (majority) and 0.333 (random); directional hit-rate 22.8% vs 19.6% chance, on 43,816 test rows from 51 stocks. Logistic regression performs the same (0.374), and training on 51 stocks was no better than on four.
- **Trading:** without costs, XGBoost signals return +5.1% (above the random-entry 95th percentile) and RiskGuard halves their drawdown; at a realistic 10 bps round-trip cost **no active strategy beats buy-and-hold**.
- **Decision path:** RiskGuard takes **24 µs**; a full signal with explanation takes 51 ms, 40% of it feature recomputation.
- **Cloud:** about 157 ms network floor from Kolkata; in-cloud pipeline P50 **10.5 µs**; zero dropped events.

## Reproduce

```powershell
backend\.venv\Scripts\pip install matplotlib psutil pypandoc_binary python-docx
backend\.venv\Scripts\python.exe thesis\benchmarks\bench_stream.py     # env + A, B, C
backend\.venv\Scripts\python.exe thesis\benchmarks\bench_model.py      # D, E, F (51 stocks, ~20 min)
backend\.venv\Scripts\python.exe thesis\benchmarks\bench_api.py        # G (local + cloud)
backend\.venv\Scripts\python.exe thesis\benchmarks\make_figures.py     # figures
backend\.venv\Scripts\python.exe thesis\build_docx.py                  # Word version
```

## Before submission

Replace every `[PLACEHOLDER]` (names, roll numbers, supervisor, HOD, academic year, date), use the official GCECT certificate wording, insert the screenshots listed in Appendix 5, fill in the team-contribution table truthfully, generate the table of contents in Word, and verify the references.

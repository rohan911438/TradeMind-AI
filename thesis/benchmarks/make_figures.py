"""Render thesis figures from thesis/benchmarks/results/*.json into thesis/figures/*.png.

    backend\.venv\Scripts\python.exe thesis\benchmarks\make_figures.py
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
FIG = HERE.parent / "figures"
FIG.mkdir(exist_ok=True)

# Reference categorical palette (light mode), fixed order - never cycled
S = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
IST = timezone(timedelta(hours=5, minutes=30))

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": INK, "xtick.color": INK2,
    "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
    "lines.linewidth": 2, "figure.dpi": 160, "savefig.bbox": "tight", "figure.facecolor": "white",
})


def load(name: str):
    p = RES / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def out(name: str) -> None:
    plt.savefig(FIG / f"{name}.png")
    plt.close()
    print("  figures/" + name + ".png")


def bars(ax, labels, values, colors, fmt="{:.1f}", log=False):
    x = np.arange(len(labels))
    b = ax.bar(x, values, color=colors, width=0.62, edgecolor="white", linewidth=2)
    ax.set_xticks(x, labels)
    if log:
        ax.set_yscale("log")
    for rect, v in zip(b, values):
        ax.annotate(fmt.format(v), (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9, color=INK)
    ax.grid(axis="x", visible=False)


def fig_a(a):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    for i, run in enumerate(a["runs"]):
        rows = [r for r in run["rows"] if r["interval_ms"] > 0]
        x = [r["interval_ms"] for r in rows]
        lab = f"{run['events_per_symbol_per_s']:.0f} events/s per symbol"
        axes[0].plot(x, [r["hidden_events_pct"] for r in rows], marker="o", ms=6, color=S[i], label=lab)
        axes[1].plot(x, [r["mean_intra_interval_range_bps"] for r in rows], marker="o", ms=6, color=S[i], label=lab)
    for ax in axes:
        ax.set_xscale("log")
        ax.set_xticks([10, 50, 100, 500, 1000], ["10", "50", "100", "500", "1000"])
        ax.set_xlabel("Snapshot interval (ms)")
    axes[0].set_ylabel("Events not visible to the sampler (%)")
    axes[0].set_title("Events hidden by fixed-interval sampling")
    axes[1].set_ylabel("Mean price range inside interval (bps)")
    axes[1].set_title("Price movement invisible between snapshots")
    axes[0].legend(loc="lower right")
    out("fig_A_capture_interval")


def fig_b(b):
    names = {"none": "None", "async_parquet": "Async\nParquet*",
             "sync_sqlite_wal": "Sync SQLite\nWAL", "sync_sqlite_full": "Sync SQLite\nFULL"}
    paced = b["paced"]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    labels = [names[r["mode"]] for r in paced]
    bars(axes[0], labels, [r["processing_path_us"]["p99"] for r in paced], [S[0], S[2], S[1], S[3]], "{:,.0f}", log=True)
    axes[0].set_ylabel("P99 processing-path latency (µs, log)")
    axes[0].set_title("Latency at 1,000 events/s")
    dr = b["drain"]
    bars(axes[1], [names[r["mode"]] for r in dr], [r["processing_throughput"] for r in dr], [S[0], S[2], S[1], S[3]],
         "{:,.0f}", log=True)
    axes[1].set_ylabel("Events processed per second (log)")
    axes[1].set_title("Maximum processing throughput")
    fig.text(0.5, -0.07, "* TradeMind's production design", ha="center", fontsize=8.5, color=INK2)
    out("fig_B_persistence")


def agg_c(c):
    rates = c["rates"]
    def m(f):
        return [float(np.mean([f(r) for r in c["runs"] if r["target_rate"] == rate])) for rate in rates]
    return rates, m


def fig_c(c):
    rates, m = agg_c(c)
    fig, ax = plt.subplots(figsize=(5.6, 4))
    ax.plot(rates, rates, ls="--", lw=1.2, color=INK2, label="Target (ideal)")
    ax.plot(rates, m(lambda r: r["achieved_rate"]), marker="o", ms=6, color=S[0], label="Achieved")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Target feed rate (events/s)"); ax.set_ylabel("Processed events/s")
    ax.set_title("Throughput: target vs achieved")
    ax.legend(loc="upper left")
    out("fig_C_throughput")

    fig, ax = plt.subplots(figsize=(6.2, 4))
    for i, (k, lab) in enumerate((("p50", "P50"), ("p95", "P95"), ("p99", "P99"))):
        ax.plot(rates, m(lambda r: r["state_update_us"][k]), marker="o", ms=6, color=S[i], label=lab)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Target feed rate (events/s)"); ax.set_ylabel("Processing latency (µs, log)")
    ax.set_title("StreamX processing latency under load")
    ax.legend(loc="upper left")
    out("fig_C_latency")

    fig, ax = plt.subplots(figsize=(6.2, 4))
    for i, (k, lab) in enumerate((("p50", "P50"), ("p99", "P99"))):
        ax.plot(rates, m(lambda r: r["end_to_end_us"][k] / 1000), marker="o", ms=6, color=S[i], label=lab)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Target feed rate (events/s)"); ax.set_ylabel("End-to-end latency (ms, log)")
    ax.set_title("End-to-end latency (creation → processed)")
    ax.legend(loc="upper left")
    out("fig_C_end_to_end")

    fig, ax = plt.subplots(figsize=(6.2, 4))
    ax.plot(rates, m(lambda r: r["cpu_percent_one_core"]), marker="o", ms=6, color=S[0])
    ax.set_xscale("log")
    ax.set_xlabel("Target feed rate (events/s)"); ax.set_ylabel("CPU (% of one core)")
    ax.set_title("Process CPU utilisation")
    out("fig_C_cpu")


def fig_d(d):
    short = {"Majority class (always HOLD)": "Majority", "Stratified random (mean of 50 seeds)": "Random",
             "Momentum rule (5-bar return)": "Momentum", "RSI rule (30/70)": "RSI rule",
             "Logistic regression (balanced)": "Logistic\nregression", "Random forest (balanced)": "Random\nforest",
             "XGBoost (TradeMind PredictX)": "XGBoost\n(PredictX)"}
    t = d["table"]
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    cols = [S[0] if "XGBoost" in r["model"] else "#a9a8a3" for r in t]
    bars(ax, [short[r["model"]] for r in t], [r["macro_f1"] for r in t], cols, "{:.3f}")
    ax.set_ylabel("Macro-F1 (test set)")
    ax.set_title("Model comparison on the held-out test period")
    out("fig_D_models")

    cm = np.array(d["confusion"]["XGBoost"])
    norm = cm / cm.sum(1, keepdims=True)
    fig, ax = plt.subplots(figsize=(4.4, 3.8))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue", ["#f2f6fc", "#2a78d6", "#0d3a73"])
    ax.imshow(norm, cmap=cmap, vmin=0, vmax=1)
    labs = ["SELL", "HOLD", "BUY"]
    ax.set_xticks(range(3), labs); ax.set_yticks(range(3), labs)
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
    ax.grid(False)
    for i in range(3):
        for j in range(3):
            ax.text(j, i, f"{cm[i, j]}\n{norm[i, j]:.0%}", ha="center", va="center", fontsize=9,
                    color="white" if norm[i, j] > 0.45 else INK)
    ax.set_title("XGBoost confusion matrix (test)")
    out("fig_D_confusion")

    fi = d["feature_importance"]
    names = list(fi)[::-1]
    fig, ax = plt.subplots(figsize=(6, 3.8))
    ax.barh(names, [fi[n] for n in names], color=S[0], height=0.62, edgecolor="white", linewidth=2)
    for y, n in enumerate(names):
        ax.text(fi[n] + 0.002, y, f"{fi[n]:.3f}", va="center", fontsize=8.5, color=INK)
    ax.set_xlabel("Importance (gain share)"); ax.grid(axis="y", visible=False)
    ax.set_title("XGBoost feature importance")
    out("fig_D_importance")

    cal = [c for c in d["calibration"] if c["n"] >= 100]   # tiny bins (e.g. 8 rows) are noise, not evidence
    fig, ax = plt.subplots(figsize=(4.8, 4))
    lo = min(c["mean_confidence"] for c in cal) - 0.03
    hi = max(max(c["mean_confidence"] for c in cal), max(c["accuracy"] for c in cal)) + 0.05
    ax.plot([lo, hi], [lo, hi], ls="--", lw=1.2, color=INK2, label="Perfect calibration")
    ax.plot([c["mean_confidence"] for c in cal], [c["accuracy"] for c in cal], marker="o", ms=7, color=S[0],
            label=f"XGBoost (ECE {d['ece']:.3f})")
    ax.set_xlabel("Mean predicted confidence"); ax.set_ylabel("Observed accuracy")
    ax.set_title("Reliability of model confidence")
    ax.legend(loc="lower right")
    ax.text(0.02, 0.98, "bins with at least 100 rows", transform=ax.transAxes, va="top", fontsize=8, color=INK2)
    out("fig_D_calibration")


def fig_e(e):
    names = {"buy_and_hold": "Buy & hold", "xgb_raw": "XGBoost (raw BUY)", "xgb_riskguard": "XGBoost + RiskGuard",
             "momentum": "Momentum rule", "rsi": "RSI rule"}
    order = ["buy_and_hold", "xgb_raw", "xgb_riskguard", "momentum", "rsi"]
    fig, ax = plt.subplots(figsize=(9, 4))
    ends = []
    for i, s in enumerate(order):
        r = next(x for x in e["results"] if x["strategy"] == s and x["cost_bps_round_trip"] == 10)
        days = [datetime.fromtimestamp(p[0], IST).strftime("%d %b") for p in r["curve"]]
        y = [(p[1] / e["starting_capital"] - 1) * 100 for p in r["curve"]]
        x = np.arange(len(y))                       # trading time: overnight gaps removed
        ax.plot(x, y, color=S[i], lw=1.6, label=names[s])
        ends.append((y[-1], x[-1]))
    # end labels, nudged apart so they do not collide
    ends_sorted = sorted(ends)
    lo_y, hi_y = ax.get_ylim()
    gap = 0.05 * (hi_y - lo_y)                      # minimum label spacing, relative to the axis range
    placed = []
    for v, xe in ends_sorted:
        yy = v if not placed or v - placed[-1] > gap else placed[-1] + gap
        placed.append(yy)
        ax.annotate(f"{v:+.2f}%", (xe, v), xytext=(xe + 3, yy), textcoords="data", fontsize=8.5,
                    color=INK, va="center")
    starts = [k for k in range(len(days)) if k == 0 or days[k] != days[k - 1]]
    ax.set_xticks(starts, [days[k] for k in starts], rotation=45, ha="right", fontsize=8.5)
    ax.set_xlim(0, len(days) + 18)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_ylabel("Return on ₹10 lakh (%)")
    ax.set_xlabel("Trading session (overnight gaps removed)")
    ax.set_title("Equity curves on the test period (10 bps round-trip cost)")
    ax.legend(loc="lower left", ncol=3, fontsize=8.5)
    out("fig_E_equity")

    costs = e["costs_bps"]
    fig, ax = plt.subplots(figsize=(6.5, 4))
    for i, s in enumerate(order):
        ys = [next(x for x in e["results"] if x["strategy"] == s and x["cost_bps_round_trip"] == c)["total_return_pct"]
              for c in costs]
        ax.plot(costs, ys, marker="o", ms=6, color=S[i], label=names[s])
    rnd = e["random_entry"]["by_cost"]
    ax.plot(costs, [rnd[str(c)]["mean_return_pct"] if str(c) in rnd else rnd[c]["mean_return_pct"] for c in costs],
            marker="o", ms=6, ls="--", color="#a9a8a3", label="Random entries (mean)")
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xlabel("Round-trip transaction cost (bps)"); ax.set_ylabel("Total return (%)")
    ax.set_title("Sensitivity to transaction costs")
    ax.legend(fontsize=8.5, loc="lower left")
    out("fig_E_costs")


def fig_g(g):
    if not g or "cloud" not in g:
        return
    loc = {r["endpoint"]: r["p50_ms"] for r in g["local"]["endpoints"]}
    cld = {r["endpoint"]: r["p50_ms"] for r in g["cloud"]["endpoints"]}
    eps = list(loc)
    short = [e.split(" ", 1)[1].replace("/api/", "").replace("/RELIANCE", "") for e in eps]
    x = np.arange(len(eps))
    fig, ax = plt.subplots(figsize=(9, 3.8))
    w = 0.38
    b1 = ax.bar(x - w / 2 - 0.01, [loc[e] for e in eps], w, color=S[0], label="Local (laptop)", edgecolor="white", linewidth=2)
    b2 = ax.bar(x + w / 2 + 0.01, [cld[e] for e in eps], w, color=S[1], label="Render cloud (Singapore)",
                edgecolor="white", linewidth=2)
    for b in list(b1) + list(b2):
        ax.annotate(f"{b.get_height():.0f}", (b.get_x() + b.get_width() / 2, b.get_height()), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(x, short, fontsize=8.5)
    ax.set_ylabel("Median response time (ms)")
    ax.set_title("Client-observed API latency")
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)
    out("fig_G_api")


if __name__ == "__main__":
    for name, fn in (("A_capture_interval", fig_a), ("B_persistence", fig_b), ("C_load", fig_c),
                     ("D_model", fig_d), ("E_trading", fig_e), ("G_api", fig_g)):
        data = load(name)
        if data:
            fn(data)

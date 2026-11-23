"""PredictX + RiskGuard benchmarks: thesis Experiments D, E and F.

    backend\.venv\Scripts\python.exe thesis\benchmarks\bench_model.py

D  Model evaluation on the chronological held-out test set: XGBoost (production model) vs
   majority class, stratified random, momentum rule, RSI rule, logistic regression, random forest.
   Includes per-symbol results and confidence calibration.
E  Paper-trading simulation on the same test period with transaction costs: XGBoost signals with
   and without the real RiskGuard engine, technical rules, random entries and buy-and-hold.
F  Decision-path latency: feature build + inference + explanation, and RiskGuard evaluation.

Uses the cached real NSE 5-minute data (backend/data/raw) and the saved model (backend/models).
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, log_loss, precision_score,
                             recall_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.predictx.data import load_history  # noqa: E402
from app.predictx.features import FEATURES, LABELS, build_features, make_labels  # noqa: E402
from app.predictx.train import METRICS_PATH, MODEL_PATH  # noqa: E402
from app.riskguard.engine import evaluate  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
H = settings.HORIZON
TH = settings.LABEL_THRESHOLD
BARS_PER_YEAR = 75 * 252
SELL, HOLD, BUY = 0, 1, 2


def save(name: str, obj) -> None:
    (RESULTS / f"{name}.json").write_text(json.dumps(obj, indent=2))
    print(f"  -> results/{name}.json")


# --------------------------------------------------------------------------- data (same split as train.py)
def load_split() -> dict:
    out = {}
    for sym in settings.SYMBOLS:
        df, _ = load_history(sym)
        d = build_features(df)
        d["label"] = make_labels(df, H, TH)
        d = d.dropna()
        n = len(d)
        i1, i2 = int(n * 0.68), int(n * 0.80)
        split = np.array(["train"] * n, dtype=object)
        split[i1:i2] = "val"
        split[i2:] = "test"
        split[max(0, i1 - H):i1] = "gap"
        split[max(0, i2 - H):i2] = "gap"
        d["split"] = split
        d["symbol"] = sym
        out[sym] = (df, d)
    return out


DATA = load_split()
ALL = pd.concat([d for _, d in DATA.values()])
TR, VA, TE = (ALL[ALL.split == s] for s in ("train", "val", "test"))
XGB = XGBClassifier()
XGB.load_model(MODEL_PATH)
MET = json.loads(METRICS_PATH.read_text())
THR = float(MET["confidence_threshold"])


def scores(y, pred, proba=None) -> dict:
    y = np.asarray(y).astype(int)
    pred = np.asarray(pred).astype(int)
    share = pd.Series(y).value_counts(normalize=True)
    dmask = pred != HOLD
    out = {
        "accuracy": accuracy_score(y, pred),
        "macro_precision": precision_score(y, pred, average="macro", zero_division=0),
        "macro_recall": recall_score(y, pred, average="macro", zero_division=0),
        "macro_f1": f1_score(y, pred, average="macro", zero_division=0),
        "f1_per_class": dict(zip(LABELS, f1_score(y, pred, labels=[0, 1, 2], average=None, zero_division=0).tolist())),
        "directional_coverage": float(dmask.mean()),
        "directional_hit_rate": float((pred[dmask] == y[dmask]).mean()) if dmask.any() else None,
        "directional_chance": float(np.mean([share.get(p, 0) for p in pred[dmask]])) if dmask.any() else None,
    }
    if proba is not None:
        out["log_loss"] = log_loss(y, proba, labels=[0, 1, 2])
        onehot = np.eye(3)[y]
        out["brier"] = float(((proba - onehot) ** 2).sum(1).mean())
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in out.items()}


def rule_momentum(d: pd.DataFrame) -> np.ndarray:
    return np.where(d.ret_5 > TH, BUY, np.where(d.ret_5 < -TH, SELL, HOLD))


def rule_rsi(d: pd.DataFrame) -> np.ndarray:
    return np.where(d.rsi_14 < 30, BUY, np.where(d.rsi_14 > 70, SELL, HOLD))


# --------------------------------------------------------------------------- Experiment D
def experiment_d() -> dict:
    print("Experiment D: model evaluation")
    X_tr, y_tr = TR[FEATURES], TR.label.astype(int)
    X_te, y_te = TE[FEATURES], TE.label.astype(int)
    w = compute_sample_weight("balanced", y_tr)
    models = {}

    models["Majority class (always HOLD)"] = (np.full(len(y_te), HOLD), None)
    prior = y_tr.value_counts(normalize=True).sort_index().values
    rand = [scores(y_te, np.random.default_rng(s).choice(3, len(y_te), p=prior)) for s in range(50)]
    models["Momentum rule (5-bar return)"] = (rule_momentum(TE), None)
    models["RSI rule (30/70)"] = (rule_rsi(TE), None)

    t0 = time.perf_counter()
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, class_weight="balanced"))
    lr.fit(X_tr, y_tr)
    lr_t = time.perf_counter() - t0
    p = lr.predict_proba(X_te)
    models["Logistic regression (balanced)"] = (p.argmax(1), p)

    t0 = time.perf_counter()
    rf = RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=20, class_weight="balanced",
                                random_state=42, n_jobs=-1)
    rf.fit(X_tr, y_tr)
    rf_t = time.perf_counter() - t0
    p = rf.predict_proba(X_te)
    models["Random forest (balanced)"] = (p.argmax(1), p)

    t0 = time.perf_counter()
    xg_check = XGBClassifier(n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                             min_child_weight=5, objective="multi:softprob", eval_metric="mlogloss",
                             early_stopping_rounds=40, random_state=42, n_jobs=-1)
    xg_check.fit(X_tr, y_tr, sample_weight=w, eval_set=[(VA[FEATURES], VA.label.astype(int))], verbose=False)
    xgb_t = time.perf_counter() - t0
    p = XGB.predict_proba(X_te)
    models["XGBoost (TradeMind PredictX)"] = (p.argmax(1), p)

    table = []
    for name, (pred, proba) in models.items():
        table.append({"model": name, **scores(y_te, pred, proba)})
    rand_avg = {k: round(float(np.mean([r[k] for r in rand])), 4)
                for k in ("accuracy", "macro_precision", "macro_recall", "macro_f1", "directional_hit_rate",
                          "directional_coverage", "directional_chance")}
    table.insert(1, {"model": "Stratified random (mean of 50 seeds)", **rand_avg})

    # XGBoost details
    xp = models["XGBoost (TradeMind PredictX)"][1]
    xpred = xp.argmax(1)
    conf = xp.max(1)
    bins = [0.0, 0.36, 0.39, 0.42, 0.45, 0.50, 1.01]
    calib, ece = [], 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (conf >= lo) & (conf < hi)
        if m.sum():
            acc = float((xpred[m] == y_te.values[m]).mean())
            calib.append({"bin": f"{lo:.2f}-{min(hi, 1):.2f}", "n": int(m.sum()),
                          "mean_confidence": round(float(conf[m].mean()), 4), "accuracy": round(acc, 4)})
            ece += m.mean() * abs(acc - conf[m].mean())
    per_symbol = []
    for sym in settings.SYMBOLS:
        m = (TE.symbol == sym).values
        s = scores(y_te[m], xpred[m])
        per_symbol.append({"symbol": sym, "test_rows": int(m.sum()), "accuracy": s["accuracy"],
                           "macro_f1": s["macro_f1"], "directional_hit_rate": s["directional_hit_rate"],
                           "majority_macro_f1": scores(y_te[m], np.full(m.sum(), HOLD))["macro_f1"]})
    conf_mask = (conf >= THR) & (xpred != HOLD)
    out = {
        "test_rows": int(len(y_te)), "train_rows": int(len(y_tr)), "val_rows": int(len(VA)),
        "label_distribution_train": {LABELS[k]: round(float(v), 4) for k, v in y_tr.value_counts(normalize=True).sort_index().items()},
        "label_distribution_test": {LABELS[k]: round(float(v), 4) for k, v in y_te.value_counts(normalize=True).sort_index().items()},
        "test_period": [str(pd.Timestamp(TE.index.min() if False else 0)), ""],
        "table": table,
        "confusion": {"XGBoost": confusion_matrix(y_te, xpred, labels=[0, 1, 2]).tolist(),
                      "Logistic regression": confusion_matrix(y_te, models["Logistic regression (balanced)"][0], labels=[0, 1, 2]).tolist()},
        "calibration": calib, "ece": round(float(ece), 4),
        "confident_signals": {"threshold": THR, "coverage": round(float(conf_mask.mean()), 4),
                              "precision": round(float((xpred[conf_mask] == y_te.values[conf_mask]).mean()), 4)},
        "per_symbol": per_symbol,
        "training_time_s": {"logistic_regression": round(lr_t, 2), "random_forest": round(rf_t, 2),
                            "xgboost_retrain_check": round(xgb_t, 2)},
        "xgboost_retrain_reproduces_saved_model": bool(np.allclose(xg_check.predict_proba(X_te), xp, atol=1e-5)),
        "feature_importance": MET["feature_importance"],
        "best_iteration": MET["best_iteration"],
    }
    out.pop("test_period")
    for r in table:
        print(f"  {r['model']:40s} acc {r['accuracy']:.3f}  macroF1 {r['macro_f1']:.3f}  hit {r['directional_hit_rate']}")
    save("D_model", out)
    return out


# --------------------------------------------------------------------------- Experiment E
def test_frames() -> dict:
    """Per symbol: OHLC arrays (full history) + the positions of test rows + XGBoost probabilities."""
    out = {}
    for sym, (df, d) in DATA.items():
        te = d[d.split == "test"]
        pos = df.index.get_indexer(te.index)
        out[sym] = {"df": df.reset_index(drop=True), "pos": pos, "feat": te.reset_index(drop=True),
                    "proba": XGB.predict_proba(te[FEATURES])}
    return out


FR = None


def simulate(strategy: str, cost_bps: float, seed: int = 0, entry_prob: float = 0.0) -> dict:
    """Long-only paper-trading simulation over the test period, one shared ₹10 lakh account."""
    rng = np.random.default_rng(seed)
    cash = settings.STARTING_CAPITAL
    side_cost = cost_bps / 2 / 1e4
    positions: dict = {}
    pending: dict = {}
    trades = []
    realised_by_day = defaultdict(float)
    last_close = {}
    timeline = sorted({int(FR[s]["df"].time[p]) for s in FR for p in FR[s]["pos"]})
    by_time = defaultdict(list)
    for s in FR:
        for j, p in enumerate(FR[s]["pos"]):
            by_time[int(FR[s]["df"].time[p])].append((s, j, p))
    last_pos = {s: FR[s]["pos"][-1] for s in FR}
    equity_curve = []

    def equity() -> float:
        return cash + sum(v["qty"] * last_close[s] for s, v in positions.items())

    if strategy == "buy_and_hold":
        first = {s: FR[s]["pos"][0] for s in FR}
    for T in timeline:
        day = time.strftime("%Y-%m-%d", time.gmtime(T + 19800))
        for s, j, p in by_time[T]:
            df = FR[s]["df"]
            o, h, l, c = df.open[p], df.high[p], df.low[p], df.close[p]
            if strategy == "buy_and_hold" and p == first[s]:
                qty = math.floor(0.25 * settings.STARTING_CAPITAL / o)
                cash -= qty * o * (1 + side_cost)
                positions[s] = {"qty": qty, "entry": o, "stop": None, "target": None, "exit_pos": None}
            if s in pending and pending[s]["pos"] == p:
                pe = pending.pop(s)
                qty = pe["qty"] if pe["qty"] is not None else math.floor(pe["frac"] * equity() / o)
                qty = min(qty, math.floor(cash / (o * (1 + side_cost))))
                if qty > 0:
                    cash -= qty * o * (1 + side_cost)
                    positions[s] = {"qty": qty, "entry": o, "stop": pe["stop"], "target": pe["target"],
                                    "exit_pos": pe["exit_pos"], "day": day}
            if s in positions and strategy != "buy_and_hold":
                ps = positions[s]
                px = None
                if ps["stop"] is not None and l <= ps["stop"]:
                    px, why = min(o, ps["stop"]), "stop"
                elif ps["target"] is not None and h >= ps["target"]:
                    px, why = max(o, ps["target"]), "target"
                elif p >= ps["exit_pos"] or p == last_pos[s]:
                    px, why = c, "time"
                if px is not None:
                    proceeds = ps["qty"] * px * (1 - side_cost)
                    cost_in = ps["qty"] * ps["entry"] * (1 + side_cost)
                    cash += proceeds
                    pnl = proceeds - cost_in
                    realised_by_day[day] += pnl
                    trades.append({"symbol": s, "ret": pnl / cost_in, "pnl": pnl, "exit": why})
                    del positions[s]
            last_close[s] = c
        # signals at the close of bar T -> enter at the next bar's open
        for s, j, p in by_time[T]:
            if s in positions or s in pending or p + H > last_pos[s]:
                continue
            f = FR[s]["feat"].iloc[j]
            pr = FR[s]["proba"][j]
            view, conf = int(pr.argmax()), float(pr.max())
            enter, frac, qty, stop, target = False, 0.20, None, None, None
            if strategy == "xgb_raw":
                enter = view == BUY
            elif strategy == "momentum":
                enter = f.ret_5 > TH
            elif strategy == "rsi":
                enter = f.rsi_14 < 30
            elif strategy == "random":
                enter = rng.random() < entry_prob
            elif strategy == "xgb_riskguard":
                ann_vol = float(f.vol_20 * math.sqrt(BARS_PER_YEAR))
                if view == BUY and conf >= THR and ann_vol <= 0.8:
                    c = float(FR[s]["df"].close[p])
                    port = {"equity": equity(), "cash": cash, "starting_cash": settings.STARTING_CAPITAL,
                            "realised_today": realised_by_day[day],
                            "positions": {k: {"qty": v["qty"], "avg_price": v["entry"],
                                              "market_value": v["qty"] * last_close[k]} for k, v in positions.items()}}
                    v = evaluate(s, "BUY", None, bid=c, ask=c, atr=float(f.atr_pct * c), ann_vol=ann_vol,
                                 signal={"signal": "BUY", "confidence": conf}, portfolio=port)
                    if v["status"] in ("APPROVED", "REDUCED") and v["approved_qty"] > 0:
                        enter, qty = True, v["approved_qty"]
                        stop, target = v["stop_loss"], v["target"]
            if enter:
                pending[s] = {"pos": p + 1, "frac": frac, "qty": qty, "stop": stop, "target": target,
                              "exit_pos": p + H}
        equity_curve.append((T, equity()))

    if strategy == "buy_and_hold":
        for s, ps in positions.items():
            cash += ps["qty"] * last_close[s] * (1 - side_cost)
            trades.append({"symbol": s, "ret": last_close[s] * (1 - side_cost) / (ps["entry"] * (1 + side_cost)) - 1,
                           "pnl": 0, "exit": "end"})
        positions.clear()
        equity_curve[-1] = (equity_curve[-1][0], cash)
    eq = np.array([e for _, e in equity_curve])
    r = np.diff(eq) / eq[:-1]
    peak = np.maximum.accumulate(eq)
    rets = np.array([t["ret"] for t in trades]) if trades else np.array([])
    return {
        "strategy": strategy, "cost_bps_round_trip": cost_bps,
        "final_equity": round(float(eq[-1]), 2),
        "total_return_pct": round(float((eq[-1] / settings.STARTING_CAPITAL - 1) * 100), 3),
        "sharpe_annualised": round(float(r.mean() / r.std() * math.sqrt(BARS_PER_YEAR)), 3) if r.std() > 0 else 0.0,
        "max_drawdown_pct": round(float(((eq - peak) / peak).min() * 100), 3),
        "trades": len(trades),
        "win_rate_pct": round(float((rets > 0).mean() * 100), 2) if rets.size else None,
        "avg_trade_ret_pct": round(float(rets.mean() * 100), 4) if rets.size else None,
        "exits": {k: sum(1 for t in trades if t["exit"] == k) for k in ("stop", "target", "time", "end")},
        "curve": [(int(t), round(float(e), 2)) for t, e in (equity_curve[::6] + [equity_curve[-1]])],
    }


def experiment_e() -> dict:
    global FR
    print("Experiment E: paper-trading simulation with costs")
    FR = test_frames()
    costs = [0, 5, 10, 20]
    strategies = ["buy_and_hold", "xgb_raw", "xgb_riskguard", "momentum", "rsi"]
    results = []
    for c in costs:
        for s in strategies:
            res = simulate(s, c)
            if c != 10:
                res.pop("curve")
            results.append(res)
            print(f"  cost {c:>2} bps  {s:14s} ret {res['total_return_pct']:7.3f}%  sharpe {res['sharpe_annualised']:7.3f}  "
                  f"mdd {res['max_drawdown_pct']:7.3f}%  trades {res['trades']}")
    # random entries with the same entry probability as raw XGBoost BUY views
    n_signal_bars = sum(len(FR[s]["pos"]) for s in FR)
    p_buy = float(np.mean([(FR[s]["proba"].argmax(1) == BUY).mean() for s in FR]))
    rand = {}
    for c in costs:
        runs = [simulate("random", c, seed=k, entry_prob=p_buy) for k in range(100)]
        tr = np.array([x["total_return_pct"] for x in runs])
        rand[c] = {"mean_return_pct": round(float(tr.mean()), 3), "p05": round(float(np.percentile(tr, 5)), 3),
                   "p95": round(float(np.percentile(tr, 95)), 3),
                   "mean_sharpe": round(float(np.mean([x["sharpe_annualised"] for x in runs])), 3),
                   "mean_trades": round(float(np.mean([x["trades"] for x in runs])), 1)}
        print(f"  cost {c:>2} bps  random(100)     mean {rand[c]['mean_return_pct']:.3f}%  [{rand[c]['p05']}, {rand[c]['p95']}]")
    times = sorted({int(FR[s]["df"].time[p]) for s in FR for p in FR[s]["pos"]})
    out = {"period_utc": [time.strftime("%Y-%m-%d %H:%M", time.gmtime(times[0])),
                          time.strftime("%Y-%m-%d %H:%M", time.gmtime(times[-1]))],
           "trading_days": len({time.strftime("%Y-%m-%d", time.gmtime(t + 19800)) for t in times}),
           "bars": len(times), "signal_bars": n_signal_bars, "starting_capital": settings.STARTING_CAPITAL,
           "horizon_bars": H, "confidence_threshold": THR, "costs_bps": costs,
           "results": results, "random_entry": {"entry_probability": round(p_buy, 4), "by_cost": rand}}
    save("E_trading", out)
    return out


# --------------------------------------------------------------------------- Experiment F
def experiment_f() -> dict:
    print("Experiment F: decision-path latency")
    from app.predictx.model import Predictor
    pred = Predictor()
    df, _ = DATA["RELIANCE"]
    candles = df.tail(400).reset_index(drop=True)
    sent = {"score": 0.1, "label": "Neutral"}

    def bench(fn, n):
        fn()
        ts = []
        for _ in range(n):
            t0 = time.perf_counter_ns()
            fn()
            ts.append((time.perf_counter_ns() - t0) / 1000)
        a = np.array(ts)
        return {"n": n, "p50_us": round(float(np.percentile(a, 50)), 1), "p95_us": round(float(np.percentile(a, 95)), 1),
                "p99_us": round(float(np.percentile(a, 99)), 1), "mean_us": round(float(a.mean()), 1)}

    import xgboost as xgb
    row = candles.pipe(build_features).iloc[[-1]][FEATURES]
    row_np = row.to_numpy(dtype=np.float32)
    booster = XGB.get_booster()
    port = {"equity": 1e6, "cash": 1e6, "starting_cash": 1e6, "realised_today": 0.0, "positions": {}}
    out = {
        "feature_build_400_bars": bench(lambda: build_features(candles), 300),
        "xgboost_predict_proba_1_row": bench(lambda: XGB.predict_proba(row), 1000),
        "xgboost_inplace_predict_1_row": bench(lambda: booster.inplace_predict(row_np), 1000),
        "xgboost_pred_contribs_1_row": bench(lambda: booster.predict(xgb.DMatrix(row), pred_contribs=True), 300),
        "full_signal_with_explanation": bench(lambda: pred.predict("RELIANCE", candles, 0.1, 0.2, sent), 300),
        "riskguard_evaluate": bench(lambda: evaluate("RELIANCE", "BUY", 100, bid=1400, ask=1400.05, atr=4.0,
                                                     ann_vol=0.2, signal={"signal": "BUY", "confidence": 0.4},
                                                     portfolio=port), 20000),
    }
    for k, v in out.items():
        print(f"  {k:32s} p50 {v['p50_us']:9.1f} us  p99 {v['p99_us']:9.1f} us")
    save("F_decision_latency", out)
    return out


if __name__ == "__main__":
    which = set(sys.argv[1:]) or {"D", "E", "F"}
    if "D" in which:
        experiment_d()
    if "E" in which:
        experiment_e()
    if "F" in which:
        experiment_f()

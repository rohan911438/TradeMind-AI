"""Experiment D2: 4-stock model vs 51-stock model on identical test rows.

    backend\.venv\Scripts\python.exe thesis\benchmarks\compare_models.py <path-to-4-stock-xgb_model.json>

The 4-stock model is the version first deployed (git tag v1.0.0: backend/models/xgb_model.json).
"""
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score
from xgboost import XGBClassifier

sys.argv, old_path = sys.argv[:1], sys.argv[1]
import bench_model as b  # noqa: E402  (loads the 51-stock split and the current model)

ORIG = ["RELIANCE", "TCS", "INFY", "HDFCBANK"]
old = XGBClassifier()
old.load_model(old_path)
te = b.TE
y = te.label.astype(int).to_numpy()
groups = {"Original 4 stocks": te.symbol.isin(ORIG).to_numpy(),
          "47 added stocks": (~te.symbol.isin(ORIG)).to_numpy(),
          "All 51 stocks": np.ones(len(te), bool)}


def stats(model, m):
    pred = model.predict_proba(te[b.FEATURES][m]).argmax(1)
    yy = y[m]
    d = pred != b.HOLD
    share = {k: (yy == k).mean() for k in range(3)}
    return {"rows": int(m.sum()), "macro_f1": round(float(f1_score(yy, pred, average="macro")), 4),
            "hit_rate": round(float((pred[d] == yy[d]).mean()), 4),
            "chance": round(float(np.mean([share[p] for p in pred[d]])), 4)}


out = {g: {"model_4_stocks": stats(old, m), "model_51_stocks": stats(b.XGB, m)} for g, m in groups.items()}
print(json.dumps(out, indent=2))
(Path(__file__).parent / "results" / "D2_model_comparison.json").write_text(json.dumps(out, indent=2))

# Paired bootstrap of the macro-F1 difference (51-stock minus 4-stock), resampling test rows.
# Rows are autocorrelated in time, so this interval is optimistic (too narrow) and is reported as indicative.
rng = np.random.default_rng(0)
po = old.predict_proba(te[b.FEATURES]).argmax(1)
pn = b.XGB.predict_proba(te[b.FEATURES]).argmax(1)
boot = {}
for g, m in groups.items():
    idx_all = np.flatnonzero(m)
    diffs = []
    for _ in range(500):
        i = rng.choice(idx_all, len(idx_all))
        diffs.append(f1_score(y[i], pn[i], average="macro") - f1_score(y[i], po[i], average="macro"))
    boot[g] = {"diff": round(float(np.mean(diffs)), 4), "ci95": [round(float(np.percentile(diffs, 2.5)), 4),
                                                              round(float(np.percentile(diffs, 97.5)), 4)]}
print(json.dumps(boot, indent=2))
out["bootstrap_macro_f1_diff_new_minus_old"] = boot
(Path(__file__).parent / "results" / "D2_model_comparison.json").write_text(json.dumps(out, indent=2))

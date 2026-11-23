"""Train the PredictX XGBoost model.

    python -m app.predictx.train            # use cached data if present
    python -m app.predictx.train --refresh  # re-download from Yahoo Finance

Split per symbol in time order: 68 % train | 12 % validation | 20 % test.
The last HORIZON rows before each boundary are dropped ("purged") because their labels
look into the next period - this prevents look-ahead leakage.
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from ..config import settings
from .data import load_history
from .features import FEATURES, LABELS, build_features, make_labels

MODEL_PATH = settings.MODEL_DIR / "xgb_model.json"
METRICS_PATH = settings.MODEL_DIR / "metrics.json"


def build_dataset(refresh: bool) -> tuple[pd.DataFrame, dict]:
    parts, sources = [], {}
    h = settings.HORIZON
    for sym in settings.SYMBOLS:
        df, src = load_history(sym, refresh=refresh)
        sources[sym] = {"source": src, "bars": len(df)}
        d = build_features(df)
        d["label"] = make_labels(df, h, settings.LABEL_THRESHOLD)
        d["time"] = df["time"].values
        d["symbol"] = sym
        d = d.dropna().reset_index(drop=True)
        n = len(d)
        i1, i2 = int(n * 0.68), int(n * 0.80)
        split = np.array(["train"] * n, dtype=object)
        split[i1:i2] = "val"
        split[i2:] = "test"
        split[max(0, i1 - h):i1] = "gap"   # purge
        split[max(0, i2 - h):i2] = "gap"
        d["split"] = split
        parts.append(d)
    return pd.concat(parts, ignore_index=True), sources


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download data")
    args = ap.parse_args()

    t0 = time.time()
    data, sources = build_dataset(args.refresh)
    tr, va, te = (data[data.split == s] for s in ("train", "val", "test"))
    X_tr, y_tr = tr[FEATURES], tr["label"].astype(int)
    X_va, y_va = va[FEATURES], va["label"].astype(int)
    X_te, y_te = te[FEATURES], te["label"].astype(int)

    model = XGBClassifier(
        n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
        min_child_weight=5, objective="multi:softprob", eval_metric="mlogloss",
        early_stopping_rounds=40, random_state=42, n_jobs=-1,
    )
    model.fit(X_tr, y_tr, sample_weight=compute_sample_weight("balanced", y_tr),
              eval_set=[(X_va, y_va)], verbose=False)

    proba = model.predict_proba(X_te)
    pred = proba.argmax(1)
    majority = int(y_tr.mode()[0])
    class_share = y_te.value_counts(normalize=True)

    # Confidence threshold for NO_TRADE: median of max-probability on the validation set
    val_conf = model.predict_proba(X_va).max(1)
    threshold = float(np.clip(np.quantile(val_conf, 0.5), 0.34, 0.65))

    conf_mask = (proba.max(1) >= threshold) & (pred != 1)
    signal_precision = float((pred[conf_mask] == y_te.values[conf_mask]).mean()) if conf_mask.any() else None
    dir_mask = pred != 1
    directional_hit = float((pred[dir_mask] == y_te.values[dir_mask]).mean()) if dir_mask.any() else None
    # chance level for the same BUY/SELL calls = prevalence of the predicted class
    directional_chance = float(np.mean([class_share.get(p, 0) for p in pred[dir_mask]])) if dir_mask.any() else None
    baseline_macro_f1 = float(f1_score(y_te, np.full(len(y_te), majority), average="macro"))

    metrics = {
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "XGBoost multi-class (SELL/HOLD/BUY)",
        "model_version": "xgb-" + time.strftime("%Y%m%d-%H%M"),
        "features": FEATURES,
        "horizon_bars": settings.HORIZON,
        "label_threshold": settings.LABEL_THRESHOLD,
        "data_sources": sources,
        "rows": {"train": len(tr), "val": len(va), "test": len(te)},
        "test_period": [int(te.time.min()), int(te.time.max())],
        "best_iteration": int(getattr(model, "best_iteration", 0) or 0),
        "accuracy": float(accuracy_score(y_te, pred)),
        "macro_f1": float(f1_score(y_te, pred, average="macro")),
        "baseline_majority_accuracy": float((y_te == majority).mean()),
        "baseline_majority_class": LABELS[majority],
        "baseline_random_accuracy": float((class_share ** 2).sum()),
        "baseline_majority_macro_f1": baseline_macro_f1,
        "directional_hit_rate": directional_hit,
        "directional_chance_rate": directional_chance,
        "confident_signal_precision": signal_precision,
        "confident_signal_coverage": float(conf_mask.mean()),
        "confidence_threshold": threshold,
        "label_distribution_test": {LABELS[int(k)]: float(v) for k, v in class_share.sort_index().items()},
        "confusion_matrix": confusion_matrix(y_te, pred, labels=[0, 1, 2]).tolist(),
        "classification_report": classification_report(y_te, pred, labels=[0, 1, 2], target_names=LABELS,
                                                        output_dict=True, zero_division=0),
        "feature_importance": dict(sorted(zip(FEATURES, map(float, model.feature_importances_)),
                                          key=lambda kv: -kv[1])),
    }
    model.save_model(MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))

    print("\n=== PredictX training summary ===")
    for s, info in sources.items():
        print(f"  {s:10s} {info['bars']:6d} bars  [{info['source']}]")
    print(f"  rows train/val/test      : {len(tr)}/{len(va)}/{len(te)}")
    print(f"  test accuracy            : {metrics['accuracy']:.3f}")
    print(f"  baseline (always {metrics['baseline_majority_class']}) : {metrics['baseline_majority_accuracy']:.3f}")
    print(f"  baseline (random)        : {metrics['baseline_random_accuracy']:.3f}")
    print(f"  macro F1                 : {metrics['macro_f1']:.3f}  (baseline {baseline_macro_f1:.3f})")
    print(f"  directional hit rate     : {directional_hit}  (chance {directional_chance})")
    print(f"  confident precision      : {signal_precision} (coverage {metrics['confident_signal_coverage']:.2%})")
    print(f"  NO_TRADE threshold       : {threshold:.3f}")
    print(f"  saved -> {MODEL_PATH}  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()

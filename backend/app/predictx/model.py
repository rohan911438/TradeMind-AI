"""PredictX inference: signal + confidence + explanation."""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import xgboost as xgb

from ..config import DISCLAIMER, settings
from .features import FEATURES, LABELS, build_features
from .train import METRICS_PATH, MODEL_PATH


def _describe(feature: str, v: float) -> str:
    if feature == "rsi_14":
        zone = "oversold" if v < 30 else "overbought" if v > 70 else "weak" if v < 45 else "strong" if v > 55 else "neutral"
        return f"RSI is {v:.0f} ({zone})"
    if feature in ("ret_1", "ret_5", "ret_15"):
        n = feature.split("_")[1]
        return f"Price moved {v * 100:+.2f}% over the last {n} bar(s)"
    if feature == "macd_hist":
        return "MACD histogram is positive (bullish momentum)" if v > 0 else "MACD histogram is negative (bearish momentum)"
    if feature == "ema_ratio":
        return "Short-term EMA is above long-term EMA (uptrend)" if v > 0 else "Short-term EMA is below long-term EMA (downtrend)"
    if feature == "bb_pctb":
        if v > 1:
            return "Price is above the upper Bollinger band"
        if v < 0:
            return "Price is below the lower Bollinger band"
        return f"Price sits at {v * 100:.0f}% of the Bollinger band range"
    if feature == "atr_pct":
        return f"Average true range is {v * 100:.2f}% of price"
    if feature == "vol_20":
        return f"Recent bar volatility is {v * 100:.2f}%"
    if feature == "volume_z":
        return f"Volume is {v:+.1f} std-dev vs its 20-bar average"
    return f"{feature} = {v:.4f}"


class Predictor:
    def __init__(self) -> None:
        self.model: xgb.XGBClassifier | None = None
        self.metrics: dict = {}
        self.load()

    def load(self) -> None:
        if MODEL_PATH.exists():
            self.model = xgb.XGBClassifier()
            self.model.load_model(MODEL_PATH)
        if METRICS_PATH.exists():
            self.metrics = json.loads(METRICS_PATH.read_text())

    @property
    def threshold(self) -> float:
        return float(self.metrics.get("confidence_threshold", 0.45))

    def predict(self, symbol: str, candles: pd.DataFrame, imbalance: float, ann_vol: float,
                sentiment: dict) -> dict:
        pressure = "Positive" if imbalance > 0.2 else "Negative" if imbalance < -0.2 else "Neutral"
        base = {
            "symbol": symbol, "market_pressure": pressure, "imbalance": round(imbalance, 3),
            "annualised_volatility": round(ann_vol, 4),
            "sentiment": {k: sentiment[k] for k in ("score", "label")},
            "horizon": f"next {settings.HORIZON} bars (~{settings.HORIZON * 5} simulated minutes)",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "model_version": self.metrics.get("model_version", "untrained"),
            "disclaimer": DISCLAIMER,
        }
        if self.model is None:
            return {**base, "signal": "NO_TRADE", "model_view": "NONE", "confidence": 0.0,
                    "probabilities": {}, "top_factors": [],
                    "explanation": "Model not trained yet. Run: python -m app.predictx.train"}

        feats = build_features(candles).iloc[[-1]][FEATURES].fillna(0.0)
        probs = self.model.predict_proba(feats)[0]
        idx = int(np.argmax(probs))
        view = LABELS[idx]
        conf = float(probs[idx])

        # Per-prediction feature contributions (XGBoost's built-in SHAP-style values)
        contribs = self.model.get_booster().predict(xgb.DMatrix(feats), pred_contribs=True)
        contribs = np.asarray(contribs).reshape(1, len(LABELS), -1)[0, idx, :-1]
        order = np.argsort(-np.abs(contribs))[:4]
        factors = []
        for i in order:
            f, val, c = FEATURES[i], float(feats.iloc[0, i]), float(contribs[i])
            factors.append({
                "feature": f, "value": round(val, 5), "contribution": round(c, 4),
                "text": f"{_describe(f, val)}, which {'supports' if c > 0 else 'argues against'} {view}",
            })

        # Heuristic blend with live order-book pressure and news sentiment (documented, simple)
        adj = 0.0
        if view in ("BUY", "SELL"):
            agrees = (view == "BUY" and pressure == "Positive") or (view == "SELL" and pressure == "Negative")
            disagrees = (view == "BUY" and pressure == "Negative") or (view == "SELL" and pressure == "Positive")
            adj += 0.04 if agrees else -0.05 if disagrees else 0.0
            s = sentiment["score"]
            adj += 0.02 if (view == "BUY" and s > 0.15) or (view == "SELL" and s < -0.15) else 0.0
        final_conf = float(np.clip(conf + adj, 0.0, 0.95))

        signal = view
        reasons_no_trade = []
        if final_conf < self.threshold:
            reasons_no_trade.append(f"confidence {final_conf:.0%} is below the {self.threshold:.0%} threshold")
        if ann_vol > 0.8:
            reasons_no_trade.append(f"volatility is extreme ({ann_vol:.0%} annualised)")
        if reasons_no_trade:
            signal = "NO_TRADE"

        top = " and ".join(f["text"].split(", which")[0].lower() for f in factors[:2])
        expl = f"The model leans {view} ({conf:.0%} raw probability) mainly because {top}. "
        expl += f"Order-book pressure is {pressure.lower()} (imbalance {imbalance:+.2f})"
        expl += f" and sample news sentiment is {sentiment['label'].lower()}, giving adjusted confidence {final_conf:.0%}. "
        if signal == "NO_TRADE":
            expl += "The system recommends NO TRADE because " + " and ".join(reasons_no_trade) + "."
        elif signal == "HOLD":
            expl += "No strong directional edge is expected over the horizon."
        else:
            expl += "RiskGuard must still approve size and risk before any simulated trade."

        return {**base, "signal": signal, "model_view": view, "confidence": round(final_conf, 4),
                "raw_confidence": round(conf, 4), "threshold": self.threshold,
                "probabilities": {LABELS[i]: round(float(p), 4) for i, p in enumerate(probs)},
                "top_factors": factors, "explanation": expl}

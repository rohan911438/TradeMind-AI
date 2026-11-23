"""Feature engineering. Every feature uses ONLY past and current bars (no look-ahead).

All features are scale-free (returns, ratios, z-scores), so a model trained on one stock
works on another, and on the live simulated feed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LABELS = ["SELL", "HOLD", "BUY"]  # class 0, 1, 2

FEATURES = [
    "ret_1", "ret_5", "ret_15",   # momentum over 1, 5, 15 bars
    "rsi_14",                     # Relative Strength Index
    "macd_hist",                  # MACD histogram / price
    "ema_ratio",                  # EMA9 / EMA21 - 1  (trend)
    "bb_pctb",                    # position inside Bollinger bands
    "atr_pct",                    # Average True Range / price
    "vol_20",                     # rolling std of 1-bar returns
    "volume_z",                   # volume z-score vs last 20 bars
]


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=1).mean()


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"].astype(float)
    out = pd.DataFrame(index=df.index)
    out["ret_1"] = c.pct_change(1)
    out["ret_5"] = c.pct_change(5)
    out["ret_15"] = c.pct_change(15)
    out["rsi_14"] = rsi(c)

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    out["macd_hist"] = (macd - macd.ewm(span=9, adjust=False).mean()) / c

    out["ema_ratio"] = c.ewm(span=9, adjust=False).mean() / c.ewm(span=21, adjust=False).mean() - 1

    ma20 = c.rolling(20).mean()
    sd20 = c.rolling(20).std()
    out["bb_pctb"] = (c - (ma20 - 2 * sd20)) / (4 * sd20).replace(0, np.nan)

    out["atr_pct"] = atr(df) / c
    out["vol_20"] = out["ret_1"].rolling(20).std()

    v = df["volume"].astype(float)
    vz = (v - v.rolling(20).mean()) / v.rolling(20).std().replace(0, np.nan)
    out["volume_z"] = vz.replace([np.inf, -np.inf], np.nan).fillna(0).clip(-3, 3)
    return out.replace([np.inf, -np.inf], np.nan)


def make_labels(df: pd.DataFrame, horizon: int = 6, threshold: float = 0.0025) -> pd.Series:
    """BUY (2) if the return over the next `horizon` bars > +threshold, SELL (0) if < -threshold, else HOLD (1)."""
    c = df["close"].astype(float)
    fwd = c.shift(-horizon) / c - 1
    label = pd.Series(1.0, index=df.index)
    label[fwd > threshold] = 2.0
    label[fwd < -threshold] = 0.0
    label[fwd.isna()] = np.nan
    return label

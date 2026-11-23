"""Historical market data: real NSE 5-minute bars from Yahoo Finance (yfinance), cached to CSV.

If the download fails (no internet) and no cache exists, a synthetic series is generated so the
system still runs. The data source is recorded in data/raw/sources.json and shown in the UI.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from ..config import settings

# (approximate price, daily volatility) used only when real data is unavailable
FALLBACK = {
    "RELIANCE": (1450.0, 0.014),
    "TCS": (3100.0, 0.013),
    "INFY": (1500.0, 0.016),
    "HDFCBANK": (950.0, 0.012),
}
BARS_PER_DAY = 75  # NSE: 09:15-15:30 = 75 five-minute bars

_SOURCES_FILE = settings.RAW_DIR / "sources.json"


def _cache_path(symbol: str):
    return settings.RAW_DIR / f"{symbol}_5m.csv"


def _read_sources() -> dict:
    try:
        return json.loads(_SOURCES_FILE.read_text())
    except Exception:
        return {}


def _write_source(symbol: str, source: str) -> None:
    src = _read_sources()
    src[symbol] = source
    _SOURCES_FILE.write_text(json.dumps(src, indent=2))


def download(symbol: str) -> pd.DataFrame | None:
    try:
        import yfinance as yf

        df = yf.download(f"{symbol}.NS", period="59d", interval="5m", progress=False,
                         auto_adjust=False, threads=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
        df = df[df["close"] > 0]
        idx = pd.DatetimeIndex(df.index)
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
        epoch = pd.Timestamp("1970-01-01", tz="UTC")
        df.insert(0, "time", ((idx.tz_convert("UTC") - epoch) // pd.Timedelta(seconds=1)).astype("int64"))
        return df.reset_index(drop=True)
    except Exception as exc:  # network / API problems
        print(f"[data] download failed for {symbol}: {exc}")
        return None


def synthetic(symbol: str, n: int = 4000, seed: int = 7) -> pd.DataFrame:
    """Regime-switching geometric Brownian motion, used only as an offline fallback."""
    price, daily_vol = FALLBACK.get(symbol, (1000.0, 0.015))
    rng = np.random.default_rng(seed + sum(map(ord, symbol)))
    sigma = daily_vol / math.sqrt(BARS_PER_DAY)
    regime, rows = 0.0, []
    t0 = (pd.Timestamp.now("UTC").floor("D") - pd.Timedelta(days=60)).value // 10**9
    for i in range(n):
        if rng.random() < 0.02:
            regime = rng.uniform(-1, 1)
        o = price
        price *= math.exp(regime * 0.3 * sigma + sigma * rng.normal())
        h = max(o, price) * (1 + abs(rng.normal()) * sigma * 0.3)
        lo = min(o, price) * (1 - abs(rng.normal()) * sigma * 0.3)
        rows.append((t0 + i * 300, o, h, lo, price, int(rng.integers(20_000, 200_000))))
    return pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"])


def load_history(symbol: str, refresh: bool = False) -> tuple[pd.DataFrame, str]:
    """Return (bars, source). Uses the CSV cache unless refresh=True."""
    path = _cache_path(symbol)
    if path.exists() and not refresh:
        return pd.read_csv(path), _read_sources().get(symbol, "yfinance")

    df = download(symbol)
    if df is not None and len(df) > 200:
        df.to_csv(path, index=False)
        _write_source(symbol, "yfinance (NSE 5-min)")
        return df, "yfinance (NSE 5-min)"

    if path.exists():
        return pd.read_csv(path), _read_sources().get(symbol, "cache")

    df = synthetic(symbol)
    df.to_csv(path, index=False)
    _write_source(symbol, "synthetic (offline fallback)")
    return df, "synthetic (offline fallback)"


def daily_volatility(df: pd.DataFrame) -> float:
    r = np.log(df["close"]).diff().dropna()
    r = r[r.abs() < 0.05]  # ignore overnight gaps
    return float(r.std() * math.sqrt(BARS_PER_DAY)) if len(r) > 10 else 0.015

"""Real-time market state per symbol (the in-memory equivalent of a Redis cache)."""
from __future__ import annotations

import math
import time
from collections import deque

import numpy as np
import pandas as pd

from .events import MarketEvent

BAR_TIME_STEP = 300  # each live candle represents one simulated 5-minute bar


class SymbolState:
    def __init__(self, symbol: str, history: pd.DataFrame, bar_seconds: float) -> None:
        self.symbol = symbol
        self.bar_seconds = bar_seconds
        hist = history.tail(400)
        self.candles: deque[dict] = deque(
            ({"time": int(r.time), "open": float(r.open), "high": float(r.high), "low": float(r.low),
              "close": float(r.close), "volume": float(r.volume)} for r in hist.itertuples()),
            maxlen=1000)
        self.hist_last_time = self.candles[-1]["time"]
        self.avg_bar_volume = float(hist["volume"].tail(100).mean() or 100_000)
        self.last = self.candles[-1]["close"]
        self.prev_close = self.last          # reference for "change %"
        self.bid = self.ask = self.last
        self.bids: list = []
        self.asks: list = []
        self.imbalance = 0.0
        self.events = 0
        self._t_start = time.monotonic()
        self._last_t = self._t_start
        self._bar_idx = -1
        self._cur: dict | None = None

    def update(self, ev: MarketEvent) -> None:
        self.events += 1
        self.last = ev.price
        self.bids, self.asks = ev.bids, ev.asks
        self.bid, self.ask = ev.bids[0][0], ev.asks[0][0]
        bq = sum(q for _, q in ev.bids)
        aq = sum(q for _, q in ev.asks)
        self.imbalance = (bq - aq) / (bq + aq) if bq + aq else 0.0

        now = time.monotonic()
        bar_idx = int((now - self._t_start) / self.bar_seconds)
        # scale by elapsed time so a live bar's volume is similar to a real 5-minute bar,
        # whatever the event rate (qty averages ~125)
        dt = min(now - self._last_t, self.bar_seconds)
        self._last_t = now
        vol = self.avg_bar_volume * (dt / self.bar_seconds) * (ev.qty / 125)
        if bar_idx != self._bar_idx:
            if self._cur is not None:
                self.candles.append(self._cur)
            self._bar_idx = bar_idx
            t = self.hist_last_time + BAR_TIME_STEP * (bar_idx + 1)
            self._cur = {"time": t, "open": ev.price, "high": ev.price, "low": ev.price,
                         "close": ev.price, "volume": vol}
        else:
            c = self._cur
            c["high"] = max(c["high"], ev.price)
            c["low"] = min(c["low"], ev.price)
            c["close"] = ev.price
            c["volume"] += vol

    # ---- read helpers -------------------------------------------------
    def all_candles(self) -> list[dict]:
        out = list(self.candles)
        if self._cur is not None:
            out.append(dict(self._cur))
        return out

    def candles_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.all_candles())

    def ann_vol(self) -> float:
        closes = np.array([c["close"] for c in self.all_candles()[-60:]])
        if len(closes) < 10:
            return 0.0
        r = np.diff(np.log(closes))
        r = r[np.abs(r) < 0.05]
        return float(r.std() * math.sqrt(75 * 252))

    def summary(self) -> dict:
        return {"symbol": self.symbol, "last": round(self.last, 2), "bid": self.bid, "ask": self.ask,
                "change_pct": round((self.last / self.prev_close - 1) * 100, 3),
                "imbalance": round(self.imbalance, 3)}

    def snapshot(self) -> dict:
        return {**self.summary(), "spread": round(self.ask - self.bid, 2), "bids": self.bids,
                "asks": self.asks, "candle": dict(self._cur) if self._cur else None,
                "events": self.events}

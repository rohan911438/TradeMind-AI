"""Simulated live market feed, seeded from the last REAL price of each stock.

Price: geometric Brownian motion with the stock's historical volatility, scaled to real
elapsed time, so the event rate does not change price behaviour.
A slowly drifting hidden "regime" (-1..+1) adds a trend AND skews order-book quantities,
which makes order-book imbalance informative, the way it is in real markets.
"""
from __future__ import annotations

import asyncio
import math
import random
import time
from dataclasses import dataclass

from .bus import EventBus
from .events import MarketEvent

TICK = 0.05  # NSE tick size


def _round_tick(p: float) -> float:
    return round(round(p / TICK) * TICK, 2)


@dataclass
class _SymSim:
    price: float
    bar_sigma: float           # std-dev of one 5-minute bar return
    regime: float = 0.0
    regime_target: float = 0.0
    last_t: float = 0.0


class FeedSimulator:
    def __init__(self, bus: EventBus, seeds: dict[str, tuple[float, float]], events_per_sec: int,
                 bar_seconds: float, seed: int = 42) -> None:
        self.bus = bus
        self.rate = events_per_sec
        self.bar_seconds = bar_seconds
        self.rng = random.Random(seed)
        now = time.perf_counter()
        # seeds: symbol -> (last real price, daily volatility); 75 five-minute bars per NSE day
        self.sims = {s: _SymSim(p, dv / math.sqrt(75), last_t=now) for s, (p, dv) in seeds.items()}
        self.symbols = list(self.sims)
        self.seq = 0
        self.paused = False

    def set_rate(self, rate: int) -> None:
        self.rate = max(1, min(int(rate), 20_000))

    def next_event(self) -> MarketEvent:
        sym = self.symbols[self.seq % len(self.symbols)]
        s = self.sims[sym]
        rng = self.rng
        now = time.perf_counter()
        dt_bars = max(now - s.last_t, 1e-6) / self.bar_seconds
        s.last_t = now

        # hidden regime: occasionally pick a new target, drift smoothly towards it
        if rng.random() < dt_bars / 5:          # ~ every 5 bars on average
            s.regime_target = rng.uniform(-1, 1)
        s.regime += (s.regime_target - s.regime) * min(1.0, dt_bars)

        drift = s.regime * 0.35 * s.bar_sigma * dt_bars
        shock = s.bar_sigma * math.sqrt(dt_bars) * rng.gauss(0, 1)
        s.price *= math.exp(drift + shock)

        mid = _round_tick(s.price)
        spread = TICK * rng.randint(1, 3)
        best_bid = _round_tick(mid - spread / 2)
        best_ask = _round_tick(best_bid + spread)
        skew = 0.7 * s.regime
        bids = [(_round_tick(best_bid - i * TICK), max(10, int(rng.randint(200, 1500) * (1 + skew) * (1 + i * 0.3))))
                for i in range(5)]
        asks = [(_round_tick(best_ask + i * TICK), max(10, int(rng.randint(200, 1500) * (1 - skew) * (1 + i * 0.3))))
                for i in range(5)]
        trade_px = best_ask if rng.random() < 0.5 + 0.3 * s.regime else best_bid

        self.seq += 1
        return MarketEvent(seq=self.seq, symbol=sym, type="TRADE", price=trade_px,
                           qty=rng.randint(1, 250), bids=bids, asks=asks, created_ns=time.perf_counter_ns())

    async def run(self) -> None:
        # Pace by REAL elapsed time (asyncio sleep is imprecise on Windows, ~15 ms granularity),
        # so the achieved rate matches the target whatever the timer resolution.
        last = time.perf_counter()
        carry = 0.0
        while True:
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            elapsed = min(now - last, 0.25)   # cap catch-up after a stall
            last = now
            if self.paused:
                continue
            n_float = self.rate * elapsed + carry
            n = int(n_float)
            carry = n_float - n
            for _ in range(n):
                self.bus.publish(self.next_event())

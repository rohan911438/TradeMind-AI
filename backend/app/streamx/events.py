from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MarketEvent:
    """One market event. Three nanosecond timestamps (time.perf_counter_ns, a monotonic
    high-resolution clock) let us measure latency at each stage."""
    seq: int
    symbol: str
    type: str                      # "TRADE" (a trade print + book update)
    price: float                   # last traded price
    qty: int                       # traded quantity
    bids: list = field(default_factory=list)   # [(price, qty)] x 5, best first
    asks: list = field(default_factory=list)
    created_ns: int = 0            # when the feed produced it
    ingest_ns: int = 0             # when the processor picked it up from the bus
    processed_ns: int = 0          # when market state finished updating

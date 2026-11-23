"""Event bus abstraction.

The rest of StreamX only uses `publish` and `get`, so the in-memory bus can be swapped for
Apache Kafka (AWS MSK in the cloud) without touching the simulator or processor.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from .events import MarketEvent


class EventBus(ABC):
    @abstractmethod
    def publish(self, event: MarketEvent) -> bool: ...

    @abstractmethod
    async def get(self) -> MarketEvent: ...

    @abstractmethod
    def depth(self) -> int: ...


class InMemoryEventBus(EventBus):
    """Bounded asyncio queue. If consumers fall behind, new events are dropped and counted (back-pressure)."""

    def __init__(self, maxsize: int = 100_000) -> None:
        self._q: asyncio.Queue[MarketEvent] = asyncio.Queue(maxsize=maxsize)
        self.dropped = 0

    def publish(self, event: MarketEvent) -> bool:
        try:
            self._q.put_nowait(event)
            return True
        except asyncio.QueueFull:
            self.dropped += 1
            return False

    async def get(self) -> MarketEvent:
        return await self._q.get()

    def depth(self) -> int:
        return self._q.qsize()


class KafkaEventBus(EventBus):
    """Cloud deployment target (not enabled in the prototype).

    publish -> aiokafka producer.send("market-events", key=symbol, value=serialised event)
    get     -> aiokafka consumer on the same topic. Partitioning by symbol keeps per-symbol ordering
               and lets several processor instances share the load (horizontal scaling).
    """

    def publish(self, event: MarketEvent) -> bool:
        raise NotImplementedError("Kafka bus is future work; set EVENT_BUS=memory")

    async def get(self) -> MarketEvent:
        raise NotImplementedError

    def depth(self) -> int:
        return 0

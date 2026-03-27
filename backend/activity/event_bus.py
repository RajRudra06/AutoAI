import asyncio
from typing import Any


class ActivityEventBus:
    """In-process pub/sub bus used to fan out activity events to websocket clients."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, event: dict[str, Any]) -> None:
        async with self._lock:
            subscribers = list(self._subscribers)

        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest entry so slow clients can still receive latest events.
                try:
                    _ = queue.get_nowait()
                except asyncio.QueueEmpty:
                    continue
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    continue


event_bus = ActivityEventBus()

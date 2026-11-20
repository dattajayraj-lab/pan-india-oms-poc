"""In-process pub/sub for WebSocket and GraphQL subscription push (FRD API-05, UI-04, RTO-*).

Sync request handlers run in a thread pool, so `publish()` hands the event to the
event loop captured at startup with `run_coroutine_threadsafe`.
"""
import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket


class EventHub:
    def __init__(self) -> None:
        self.sockets: dict[str, set[WebSocket]] = defaultdict(set)
        self.queues: set[asyncio.Queue] = set()
        self.loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, channel: str, ws: WebSocket) -> None:
        await ws.accept()
        self.sockets[channel].add(ws)

    def disconnect(self, channel: str, ws: WebSocket) -> None:
        self.sockets[channel].discard(ws)

    async def _broadcast(self, channel: str, event: dict) -> None:
        msg = json.dumps(event, default=str)
        for ch in {channel, "ALL"}:
            for ws in list(self.sockets.get(ch, ())):
                try:
                    await ws.send_text(msg)
                except Exception:  # noqa: BLE001
                    self.sockets[ch].discard(ws)
        for q in list(self.queues):
            q.put_nowait({"channel": channel, **event})

    def publish(self, channel: str, event_type: str, data: dict | None = None) -> None:
        event = {"type": event_type, "channel": channel, "data": data or {}}
        if self.loop is None or self.loop.is_closed():
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self.loop:
            self.loop.create_task(self._broadcast(channel, event))
        else:
            asyncio.run_coroutine_threadsafe(self._broadcast(channel, event), self.loop)

    def subscribe_queue(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.queues.add(q)
        return q

    def unsubscribe_queue(self, q: asyncio.Queue) -> None:
        self.queues.discard(q)


hub = EventHub()

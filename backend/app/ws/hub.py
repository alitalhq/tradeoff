"""In-process fan-out of server messages to the WebSockets watching a session."""

import asyncio
import threading
from collections import defaultdict

from app.ws.messages import ServerMessage, server_message_adapter


class Hub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[int, set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = defaultdict(set)

    def subscribe(self, session_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subscribers[session_id].add((asyncio.get_running_loop(), queue))
        return queue

    def unsubscribe(self, session_id: int, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subscribers[session_id] = {s for s in self._subscribers[session_id] if s[1] is not queue}

    def publish(self, session_id: int, msg: ServerMessage) -> None:
        """Safe to call from any thread; each subscriber receives the message as a JSON string."""
        payload = server_message_adapter.dump_json(msg).decode()
        with self._lock:
            targets = list(self._subscribers.get(session_id, ()))
        for loop, queue in targets:
            loop.call_soon_threadsafe(queue.put_nowait, payload)


hub = Hub()

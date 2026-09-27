import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """Tracks the WebSocket connections held open by *this* process.

    A user may have several simultaneous sessions (laptop + phone). Each
    connection is kept in a per-user set so a message can be fanned out to
    every active session for that user. State lives only in this process;
    cross-process fanout (needed once you run more than one app replica) is
    handled by publishing events on Redis (see services/redis_bus.py), with
    every replica draining the same channel and delivering to its own local
    connections.
    """

    def __init__(self) -> None:
        self._by_user: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._by_user[user_id].add(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._by_user.get(user_id)
            if connections is not None:
                connections.discard(websocket)
                if not connections:
                    self._by_user.pop(user_id, None)

    async def send_to_user(self, user_id: str, message: str) -> None:
        async with self._lock:
            connections = list(self._by_user.get(user_id, ()))
        await self._send_all(connections, message)

    async def broadcast(self, message: str) -> None:
        async with self._lock:
            connections = [ws for conns in self._by_user.values() for ws in conns]
        await self._send_all(connections, message)

    @staticmethod
    async def _send_all(connections: list[WebSocket], message: str) -> None:
        if not connections:
            return
        # Fire concurrently and non-blockingly; a slow/dead client must not
        # stall delivery to everyone else. Failures are swallowed here and
        # cleaned up lazily when the socket's receive loop raises and the
        # route's disconnect handler removes it from the registry.
        await asyncio.gather(
            *(ws.send_text(message) for ws in connections), return_exceptions=True
        )

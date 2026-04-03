"""WebSocket connection manager with channel-based pub/sub."""

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger("session_pulse.ws")


class WebSocketManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[channel].add(websocket)
        logger.debug(f"WS connected to channel: {channel}")

    async def disconnect(self, websocket: WebSocket, channel: str) -> None:
        async with self._lock:
            self._connections[channel].discard(websocket)

    async def broadcast(self, channel: str, message: dict) -> None:
        connections = self._connections.get(channel)
        if not connections:
            return

        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections[channel].discard(ws)

    @property
    def connection_count(self) -> int:
        return sum(len(conns) for conns in self._connections.values())

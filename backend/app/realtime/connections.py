"""In-memory registry of live sockets, grouped by game.

This state is per process. Game data itself lives in PostgreSQL, but broadcasts only reach sockets
connected to the same process, so the API must run as a single instance. Scaling out would require
a pub/sub layer (for example Redis or PostgreSQL LISTEN/NOTIFY) behind `broadcast`.
"""

import asyncio
import contextlib
import logging
import uuid
import weakref
from typing import Any

from fastapi import WebSocket

from app.realtime.protocol import CloseCode

logger = logging.getLogger(__name__)


class Connection:
    def __init__(self, websocket: WebSocket, user_id: int, send_timeout: float) -> None:
        self.websocket = websocket
        self.user_id = user_id
        self._send_timeout = send_timeout
        self._send_lock = asyncio.Lock()  # frames from concurrent tasks must not interleave

    async def send(self, message: dict[str, Any]) -> None:
        """Best effort: a dead or stalled socket is closed and never breaks other recipients."""
        try:
            async with self._send_lock:
                await asyncio.wait_for(self.websocket.send_json(message), self._send_timeout)
        except Exception:
            logger.info("Dropping unresponsive socket for user %s", self.user_id)
            await self.close(1011)

    async def close(self, code: int) -> None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self.websocket.close(code=code), self._send_timeout)


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[uuid.UUID, dict[int, Connection]] = {}
        # Weak values: a lock lives exactly as long as someone is holding or waiting for it.
        self._locks: weakref.WeakValueDictionary[uuid.UUID, asyncio.Lock] = weakref.WeakValueDictionary()

    def game_lock(self, game_id: uuid.UUID) -> asyncio.Lock:
        """Serialises "commit, then broadcast" so clients see events in commit order."""
        lock = self._locks.get(game_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[game_id] = lock
        return lock

    async def register(self, game_id: uuid.UUID, connection: Connection) -> None:
        """Add a socket. A player has one live socket per game: the newest wins."""
        room = self._rooms.setdefault(game_id, {})
        previous = room.get(connection.user_id)
        room[connection.user_id] = connection
        if previous is not None:
            await previous.close(CloseCode.REPLACED)

    def unregister(self, game_id: uuid.UUID, connection: Connection) -> bool:
        """Remove a socket. Returns False if it had already been replaced by a newer one."""
        room = self._rooms.get(game_id)
        if room is None or room.get(connection.user_id) is not connection:
            return False
        del room[connection.user_id]
        if not room:
            del self._rooms[game_id]
        return True

    def connected_users(self, game_id: uuid.UUID) -> set[int]:
        return set(self._rooms.get(game_id, {}))

    def active_rooms(self) -> list[uuid.UUID]:
        return list(self._rooms)

    async def broadcast(
        self, game_id: uuid.UUID, message: dict[str, Any], *, exclude_user: int | None = None
    ) -> None:
        targets = [c for uid, c in self._rooms.get(game_id, {}).items() if uid != exclude_user]
        if targets:
            await asyncio.gather(*(connection.send(message) for connection in targets))

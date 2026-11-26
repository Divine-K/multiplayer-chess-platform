"""Background task for events no client request triggers: flag falls and abandoned games.

It works purely from database state, so clocks still expire correctly after a server restart and
when neither player is connected.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable
from datetime import datetime, timedelta
from functools import partial

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chess_core.clock import ClockState
from app.core.config import Settings
from app.core.time import utc_now
from app.models import Game, GameStatus, PlayerColor
from app.realtime.commands import GameCommands, read_state, run_db
from app.realtime.protocol import ServerEvent, server_message

logger = logging.getLogger(__name__)


def find_expired_games(session: Session, now: datetime) -> list[uuid.UUID]:
    rows = session.execute(
        select(
            Game.id, Game.current_fen, Game.white_remaining_ms, Game.black_remaining_ms, Game.turn_started_at
        ).where(Game.status == GameStatus.ACTIVE, Game.turn_started_at.is_not(None))
    ).all()
    expired = []
    for row in rows:
        side = PlayerColor.WHITE if row.current_fen.split()[1] == "w" else PlayerColor.BLACK
        clock = ClockState(row.white_remaining_ms, row.black_remaining_ms, side, row.turn_started_at)
        if clock.is_flagged(now):
            expired.append(row.id)
    return expired


def find_unstarted_games(session: Session, now: datetime, start_timeout: timedelta) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(Game.id).where(Game.status == GameStatus.WAITING, Game.created_at <= now - start_timeout)
        )
    )


def has_unfinished_games(session: Session) -> bool:
    unfinished = Game.status.in_((GameStatus.WAITING, GameStatus.ACTIVE))
    return session.scalar(select(Game.id).where(unfinished).limit(1)) is not None


class Sweeper:
    def __init__(self, commands: GameCommands, settings: Settings) -> None:
        self._commands = commands
        self._interval = settings.sweeper_interval_seconds
        self._sync_interval = settings.clock_sync_interval_seconds
        self._start_timeout = timedelta(seconds=settings.game_start_timeout_seconds)
        self._idle_recheck = settings.sweeper_idle_recheck_seconds
        self._next_sync: float | None = None  # None while there is nothing to keep in step
        self._next_idle_recheck = 0.0

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self.tick()
            except Exception:
                logger.exception("Sweeper pass failed; will retry")

    async def tick(self) -> None:
        """One pass. With nothing to watch, it does not touch the database at all.

        That lets a database which suspends when unused (common on free hosting) actually suspend.
        """
        now = asyncio.get_running_loop().time()
        pending = self._commands.games_pending
        if not pending.is_set() and now < self._next_idle_recheck:
            return
        self._next_idle_recheck = now + self._idle_recheck
        # Cleared before looking, so a game created while we look sets it again.
        pending.clear()
        try:
            await self.sweep()
            if self._next_sync is None:
                self._next_sync = now + self._sync_interval
            elif now >= self._next_sync:
                self._next_sync = now + self._sync_interval
                await self.broadcast_clocks()
            if await run_db(has_unfinished_games):
                pending.set()
            else:
                self._next_sync = None
        except Exception:
            pending.set()
            raise

    async def sweep(self) -> None:
        now = utc_now()
        for game_id in await run_db(lambda s: find_expired_games(s, now)):
            await self._isolated(game_id, self._commands.expire(game_id))
        for game_id in await run_db(lambda s: find_unstarted_games(s, now, self._start_timeout)):
            await self._isolated(game_id, self._commands.abort_unstarted(game_id, self._start_timeout))

    @staticmethod
    async def _isolated(game_id: uuid.UUID, action: Awaitable[None]) -> None:
        """One game that fails to process must not stop the others being swept."""
        try:
            await action
        except Exception:
            logger.exception("Sweeper could not process game %s", game_id)

    async def broadcast_clocks(self) -> None:
        """Periodically re-send authoritative clocks so client-side countdowns cannot drift."""
        connections = self._commands.connections
        for game_id in connections.active_rooms():
            async with connections.game_lock(game_id):
                snapshot = await run_db(partial(_clock_snapshot, game_id=game_id))
                if snapshot is not None:
                    await connections.broadcast(
                        game_id, server_message(ServerEvent.CLOCK_UPDATED, game_id, snapshot)
                    )


def _clock_snapshot(session: Session, game_id: uuid.UUID) -> dict[str, object] | None:
    state = read_state(session, game_id)
    if state.status != GameStatus.ACTIVE:
        return None
    return {
        "clocks": state.clocks.model_dump(mode="json"),
        "version": state.version,
        "server_time": state.server_time.isoformat(),
    }

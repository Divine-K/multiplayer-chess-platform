"""Game commands: run the database transaction, then publish the resulting events.

WebSocket handlers, REST endpoints and the timeout sweeper all go through here, so every change to
a game reaches both players no matter how it was triggered.
"""

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.time import utc_now
from app.db.session import get_session_factory
from app.models import GameStatus
from app.realtime.connections import ConnectionManager
from app.realtime.protocol import ServerEvent, server_message
from app.schemas.game import GameState
from app.services import game_queries, game_service


async def run_db[T](work: Callable[[Session], T]) -> T:
    """Run blocking database work in a worker thread with its own short-lived session."""

    def call() -> T:
        with get_session_factory()() as session:
            return work(session)

    return await run_in_threadpool(call)


def _is_over(state: GameState) -> bool:
    return state.status in (GameStatus.FINISHED, GameStatus.ABORTED)


def _state_payload(state: GameState) -> dict[str, Any]:
    return {"state": state.model_dump(mode="json")}


def read_state(session: Session, game_id: uuid.UUID) -> GameState:
    return game_queries.build_state(game_service.load_game(session, game_id), utc_now())


class GameCommands:
    def __init__(self, connections: ConnectionManager) -> None:
        self.connections = connections

    async def publish(
        self, event: ServerEvent, state: GameState, extra: dict[str, Any] | None = None
    ) -> None:
        payload = (extra or {}) | _state_payload(state)
        await self.connections.broadcast(state.game_id, server_message(event, state.game_id, payload))

    async def publish_finished(self, state: GameState) -> None:
        await self.publish(
            ServerEvent.GAME_FINISHED,
            state,
            {"status": state.status, "result": state.result, "result_reason": state.result_reason},
        )

    async def start_if_ready(self, game_id: uuid.UUID, player_ids: set[int]) -> None:
        """Start the game once both players have a live socket."""
        async with self.connections.game_lock(game_id):
            if not player_ids <= self.connections.connected_users(game_id):
                return

            def work(session: Session) -> GameState | None:
                if not game_service.start_game(session, game_id, utc_now()):
                    return None
                return read_state(session, game_id)

            state = await run_db(work)
            if state is not None:
                await self.publish(ServerEvent.GAME_STARTED, state)

    async def move(
        self, game_id: uuid.UUID, user_id: int, from_square: str, to_square: str, promotion: str | None
    ) -> bool:
        """Returns False if the move arrived after the mover's time ran out.

        Raises MoveError or DomainError for any other rejection; nothing is broadcast then.
        """
        async with self.connections.game_lock(game_id):

            def work(session: Session) -> tuple[GameState, bool]:
                now = utc_now()
                outcome = game_service.submit_move(
                    session, game_id, user_id, from_square, to_square, promotion, now
                )
                return game_queries.build_state(outcome.game, now), outcome.timed_out

            state, timed_out = await run_db(work)
            if timed_out:
                await self.publish_finished(state)
                return False

            move = state.moves[-1]
            mover = "white" if move.ply % 2 == 1 else "black"
            await self.publish(
                ServerEvent.MOVE_ACCEPTED, state, {"move": move.model_dump() | {"color": mover}}
            )
            if _is_over(state):
                await self.publish_finished(state)
            else:
                await self.connections.broadcast(
                    game_id,
                    server_message(
                        ServerEvent.TURN_CHANGED,
                        game_id,
                        {"turn": state.turn, "ply": state.ply, "version": state.version},
                    ),
                )
            return True

    async def resign(self, game_id: uuid.UUID, user_id: int) -> GameState:
        async with self.connections.game_lock(game_id):

            def work(session: Session) -> GameState:
                game_service.resign(session, game_id, user_id, utc_now())
                return read_state(session, game_id)

            state = await run_db(work)
            await self.publish_finished(state)
            return state

    async def offer_draw(self, game_id: uuid.UUID, user_id: int) -> None:
        async with self.connections.game_lock(game_id):

            def work(session: Session) -> GameState:
                game_service.offer_draw(session, game_id, user_id, utc_now())
                return read_state(session, game_id)

            state = await run_db(work)
            if _is_over(state):
                await self.publish_finished(state)
            else:
                await self.publish(ServerEvent.DRAW_OFFERED, state, {"by": state.draw_offered_by})

    async def respond_to_draw(self, game_id: uuid.UUID, user_id: int, accept: bool) -> None:
        async with self.connections.game_lock(game_id):

            def work(session: Session) -> GameState:
                game_service.respond_to_draw(session, game_id, user_id, accept, utc_now())
                return read_state(session, game_id)

            state = await run_db(work)
            if _is_over(state):
                await self.publish_finished(state)
            else:
                await self.publish(ServerEvent.DRAW_DECLINED, state)

    async def expire(self, game_id: uuid.UUID) -> None:
        """Flag a game whose running clock has reached zero."""
        async with self.connections.game_lock(game_id):

            def work(session: Session) -> GameState | None:
                if game_service.claim_timeout(session, game_id, utc_now()) is None:
                    return None
                return read_state(session, game_id)

            state = await run_db(work)
            if state is not None:
                await self.publish_finished(state)

    async def abort_unstarted(self, game_id: uuid.UUID, start_timeout: timedelta) -> None:
        async with self.connections.game_lock(game_id):

            def work(session: Session) -> GameState | None:
                if game_service.abort_if_never_started(session, game_id, utc_now(), start_timeout) is None:
                    return None
                return read_state(session, game_id)

            state = await run_db(work)
            if state is not None:
                await self.publish_finished(state)

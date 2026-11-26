"""The game WebSocket: `/ws/games/{game_id}`.

Authentication happens in the first message, not in the URL, so tokens never appear in access logs.
Disconnect policy: the clock keeps running. A player may reconnect at any time before the game ends
and receives the full authoritative state.
"""

import asyncio
import contextlib
import json
import logging
import uuid
from collections import deque

import anyio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.chess_core.engine import MoveError
from app.core.config import Settings
from app.core.security import InvalidTokenError, decode_access_token
from app.models import PlayerColor
from app.realtime.commands import GameCommands, read_state, run_db
from app.realtime.connections import Connection
from app.realtime.protocol import (
    AuthMessage,
    CloseCode,
    MoveMessage,
    ServerEvent,
    SimpleMessage,
    client_message_adapter,
    closing_message,
    server_message,
)
from app.schemas.game import GameState
from app.services import game_service
from app.services.errors import DomainError, GameNotFoundError, NotAParticipantError
from app.services.user_service import get_active_user_by_id

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_CONSECUTIVE_INVALID_MESSAGES = 5


class _Reject(Exception):
    """Close the socket with an application close code."""

    def __init__(self, code: CloseCode) -> None:
        self.code = code


async def _close_with_reason(
    websocket: WebSocket, game_id: uuid.UUID, code: CloseCode, send_timeout: float
) -> None:
    with contextlib.suppress(Exception):
        await asyncio.wait_for(websocket.send_json(closing_message(game_id, code)), send_timeout)
    with contextlib.suppress(Exception):
        await websocket.close(code=code)


class _RateLimiter:
    def __init__(self, per_second: int) -> None:
        self._limit = per_second
        self._times: deque[float] = deque()

    def allow(self) -> bool:
        now = asyncio.get_running_loop().time()
        while self._times and now - self._times[0] > 1.0:
            self._times.popleft()
        self._times.append(now)
        return len(self._times) <= self._limit


async def _receive_text(websocket: WebSocket, timeout: float, max_bytes: int) -> str | None:
    """Return the next text frame, or None for a binary frame."""
    frame = await asyncio.wait_for(websocket.receive(), timeout)
    if frame["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(frame.get("code", 1000))
    text = frame.get("text")
    if text is None:
        return None
    if len(text.encode()) > max_bytes:
        raise _Reject(CloseCode.MESSAGE_TOO_LARGE)
    return str(text)


async def _authenticate(
    websocket: WebSocket, game_id: uuid.UUID, settings: Settings
) -> tuple[int, PlayerColor, set[int]]:
    try:
        raw = await _receive_text(websocket, settings.ws_auth_timeout_seconds, settings.ws_max_message_bytes)
    except TimeoutError as exc:
        raise _Reject(CloseCode.AUTH_TIMEOUT) from exc
    try:
        message = client_message_adapter.validate_json(raw or "")
    except ValidationError as exc:
        raise _Reject(CloseCode.UNAUTHORIZED) from exc
    if not isinstance(message, AuthMessage) or message.game_id not in (None, game_id):
        raise _Reject(CloseCode.UNAUTHORIZED)
    try:
        user_id = decode_access_token(message.payload.token)
    except InvalidTokenError as exc:
        raise _Reject(CloseCode.UNAUTHORIZED) from exc

    def authorise(session: Session) -> tuple[PlayerColor, set[int]]:
        if get_active_user_by_id(session, user_id) is None:
            raise _Reject(CloseCode.UNAUTHORIZED)
        game = game_service.load_game(session, game_id)
        color = game_service.participant_for(game, user_id).color
        return color, {p.user_id for p in game.participants}

    try:
        color, player_ids = await run_db(authorise)
    except GameNotFoundError as exc:
        raise _Reject(CloseCode.GAME_NOT_FOUND) from exc
    except NotAParticipantError as exc:
        raise _Reject(CloseCode.FORBIDDEN) from exc
    return user_id, color, player_ids


class _Session:
    """One authenticated player's connection to one game."""

    def __init__(
        self, commands: GameCommands, connection: Connection, game_id: uuid.UUID, color: PlayerColor
    ) -> None:
        self.commands = commands
        self.connection = connection
        self.game_id = game_id
        self.color = color

    async def send(self, event: ServerEvent, payload: dict[str, object]) -> None:
        await self.connection.send(server_message(event, self.game_id, payload))

    async def current_state(self) -> GameState:
        return await run_db(lambda s: read_state(s, self.game_id))

    async def send_state(self) -> None:
        async with self.commands.connections.game_lock(self.game_id):
            state = await self.current_state()
            await self.send(ServerEvent.STATE, {"state": state.model_dump(mode="json")})

    async def handle(self, message: MoveMessage | SimpleMessage) -> None:
        user_id = self.connection.user_id
        try:
            if isinstance(message, MoveMessage):
                move = message.payload
                accepted = await self.commands.move(
                    self.game_id, user_id, move.from_square, move.to_square, move.promotion
                )
                if not accepted:
                    await self.reject_move("flag_fallen", "Your time ran out before this move arrived.")
                return
            match message.type:
                case "ping":
                    await self.send(ServerEvent.PONG, {})
                case "sync":
                    await self.send_state()
                case "resign":
                    await self.commands.resign(self.game_id, user_id)
                case "offer_draw":
                    await self.commands.offer_draw(self.game_id, user_id)
                case "accept_draw" | "decline_draw":
                    await self.commands.respond_to_draw(self.game_id, user_id, message.type == "accept_draw")
        except (MoveError, DomainError) as exc:
            if isinstance(message, MoveMessage):
                await self.reject_move(exc.code, str(exc))
            else:
                await self.send(ServerEvent.ERROR, {"code": exc.code, "message": str(exc)})
        except Exception:
            logger.exception("Failed to handle %s for game %s", message.type, self.game_id)
            await self.send(ServerEvent.ERROR, {"code": "internal_error", "message": "Something went wrong."})

    async def reject_move(self, code: str, reason: str) -> None:
        """Only the sender hears about a rejection, along with the true state so it can resync."""
        state = await self.current_state()
        await self.send(
            ServerEvent.MOVE_REJECTED,
            {"code": code, "message": reason, "state": state.model_dump(mode="json")},
        )


async def _message_loop(websocket: WebSocket, session: _Session, settings: Settings) -> None:
    limiter = _RateLimiter(settings.ws_max_messages_per_second)
    invalid_in_a_row = 0
    while True:
        try:
            raw = await _receive_text(
                websocket, settings.ws_idle_timeout_seconds, settings.ws_max_message_bytes
            )
        except TimeoutError as exc:
            raise _Reject(CloseCode.IDLE_TIMEOUT) from exc
        if not limiter.allow():
            raise _Reject(CloseCode.RATE_LIMITED)

        problem: str | None = None
        message = None
        try:
            message = client_message_adapter.validate_python(json.loads(raw or ""))
        except (json.JSONDecodeError, ValidationError, RecursionError):
            problem = "Message does not match the protocol."
        if isinstance(message, AuthMessage):
            problem = "Already authenticated."
        elif message is not None and message.game_id not in (None, session.game_id):
            problem = "game_id does not match this connection."

        if problem is not None or not isinstance(message, MoveMessage | SimpleMessage):
            invalid_in_a_row += 1
            await session.send(ServerEvent.ERROR, {"code": "invalid_message", "message": problem})
            if invalid_in_a_row >= MAX_CONSECUTIVE_INVALID_MESSAGES:
                raise _Reject(CloseCode.PROTOCOL_VIOLATION)
            continue
        invalid_in_a_row = 0
        await session.handle(message)


@router.websocket("/ws/games/{game_id}")
async def game_socket(websocket: WebSocket, game_id: uuid.UUID) -> None:
    settings: Settings = websocket.app.state.settings
    commands: GameCommands = websocket.app.state.commands
    connections = commands.connections

    # Browsers always send Origin on WebSocket requests, and CORS does not apply to them, so
    # enforce the allow-list here. Non-browser clients send no Origin and still need a token.
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in settings.cors_origins:
        await websocket.close(code=CloseCode.FORBIDDEN)
        return

    await websocket.accept()
    app_state = websocket.app.state
    if app_state.unauthenticated_sockets >= settings.ws_max_unauthenticated:
        await _close_with_reason(websocket, game_id, CloseCode.RATE_LIMITED, settings.ws_send_timeout_seconds)
        return
    connection: Connection | None = None
    color: PlayerColor | None = None
    try:
        app_state.unauthenticated_sockets += 1
        try:
            user_id, color, player_ids = await _authenticate(websocket, game_id, settings)
        finally:
            app_state.unauthenticated_sockets -= 1
        connection = Connection(websocket, user_id, settings.ws_send_timeout_seconds)
        session = _Session(commands, connection, game_id, color)

        async with connections.game_lock(game_id):
            await connections.register(game_id, connection)
            state = await session.current_state()
            await session.send(
                ServerEvent.CONNECTED,
                {
                    "color": color.value,
                    "opponent_connected": bool(connections.connected_users(game_id) - {user_id}),
                    "state": state.model_dump(mode="json"),
                },
            )
            await connections.broadcast(
                game_id,
                server_message(ServerEvent.PLAYER_CONNECTED, game_id, {"color": color.value}),
                exclude_user=user_id,
            )
        await commands.start_if_ready(game_id, player_ids)
        await _message_loop(websocket, session, settings)
    except _Reject as rejection:
        await _close_with_reason(websocket, game_id, rejection.code, settings.ws_send_timeout_seconds)
    except (WebSocketDisconnect, RuntimeError):
        pass  # the client went away, or the socket was closed because a newer one replaced it
    finally:
        if connection is not None and connections.unregister(game_id, connection):
            assert color is not None
            # Shielded: if this task is cancelled while cleaning up, the opponent must still hear.
            with anyio.CancelScope(shield=True):
                await connections.broadcast(
                    game_id,
                    server_message(ServerEvent.PLAYER_DISCONNECTED, game_id, {"color": color.value}),
                )

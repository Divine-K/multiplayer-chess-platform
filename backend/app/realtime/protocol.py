"""WebSocket message contract. Every message is `{"type": ..., "game_id": ..., "payload": {...}}`.

See docs/WEBSOCKET_PROTOCOL.md for the full description.
"""

import enum
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class ServerEvent(enum.StrEnum):
    CONNECTED = "connected"
    GAME_STARTED = "game_started"
    MOVE_ACCEPTED = "move_accepted"
    MOVE_REJECTED = "move_rejected"
    TURN_CHANGED = "turn_changed"
    CLOCK_UPDATED = "clock_updated"
    DRAW_OFFERED = "draw_offered"
    DRAW_DECLINED = "draw_declined"
    PLAYER_CONNECTED = "player_connected"
    PLAYER_DISCONNECTED = "player_disconnected"
    GAME_FINISHED = "game_finished"
    STATE = "state"
    PONG = "pong"
    ERROR = "error"


class CloseCode(enum.IntEnum):
    """Application close codes (the 4000-4999 range is reserved for applications)."""

    PROTOCOL_VIOLATION = 4400
    UNAUTHORIZED = 4401
    FORBIDDEN = 4403
    GAME_NOT_FOUND = 4404
    AUTH_TIMEOUT = 4408
    REPLACED = 4409
    IDLE_TIMEOUT = 4410
    RATE_LIMITED = 4429
    MESSAGE_TOO_LARGE = 1009


def server_message(event: ServerEvent, game_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": event.value, "game_id": str(game_id), "payload": payload}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _ClientMessage(_Strict):
    game_id: uuid.UUID | None = None  # optional; must match the socket's game when present


class AuthPayload(_Strict):
    token: str = Field(min_length=1, max_length=2048)


class MovePayload(_Strict):
    from_square: str = Field(alias="from", min_length=2, max_length=2)
    to_square: str = Field(alias="to", min_length=2, max_length=2)
    promotion: Literal["q", "r", "b", "n"] | None = None


class EmptyPayload(_Strict):
    pass


class AuthMessage(_ClientMessage):
    type: Literal["auth"]
    payload: AuthPayload


class MoveMessage(_ClientMessage):
    type: Literal["move"]
    payload: MovePayload


class SimpleMessage(_ClientMessage):
    type: Literal["resign", "offer_draw", "accept_draw", "decline_draw", "sync", "ping"]
    payload: EmptyPayload = Field(default_factory=EmptyPayload)


ClientMessage = Annotated[AuthMessage | MoveMessage | SimpleMessage, Field(discriminator="type")]

client_message_adapter: TypeAdapter[AuthMessage | MoveMessage | SimpleMessage] = TypeAdapter(
    ClientMessage  # type: ignore[arg-type]  # mypy cannot express an Annotated union here
)

"""Helpers for driving the REST API and WebSocket protocol in tests."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.testclient import WebSocketTestSession

from app.core.security import create_access_token
from tests.factories import make_user


@dataclass(frozen=True)
class Account:
    id: int
    username: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


def make_account(session: Session, username: str) -> Account:
    user = make_user(session, username)
    return Account(user.id, username, create_access_token(user.id))


def match(
    client: TestClient, first: Account, second: Account, seconds: int = 180
) -> tuple[str, Account, Account]:
    """Pair two players through the real API. Returns (game_id, white, black)."""
    body = {"time_control_seconds": seconds}
    assert client.post("/api/v1/matchmaking", json=body, headers=first.headers).json()["status"] == "queued"
    matched = client.post("/api/v1/matchmaking", json=body, headers=second.headers).json()
    assert matched["status"] == "matched"
    if matched["color"] == "white":
        return matched["game_id"], second, first
    return matched["game_id"], first, second


class Socket:
    def __init__(self, raw: WebSocketTestSession) -> None:
        self.raw = raw

    def send(self, type_: str, payload: dict[str, Any] | None = None) -> None:
        self.raw.send_json({"type": type_, "payload": payload or {}})

    def move(self, uci: str) -> None:
        payload = {"from": uci[:2], "to": uci[2:4]}
        if uci[4:]:
            payload["promotion"] = uci[4:]
        self.send("move", payload)

    def expect(self, type_: str) -> dict[str, Any]:
        """Assert the very next event has this type and return its payload."""
        message = self.raw.receive_json()
        assert message["type"] == type_, f"expected {type_}, got {message['type']}: {message['payload']}"
        return dict(message["payload"])

    def assert_nothing_pending(self) -> None:
        """A ping answered immediately proves no other event was queued ahead of it."""
        self.send("ping")
        self.expect("pong")


@contextmanager
def socket_for(client: TestClient, game_id: str, account: Account) -> Iterator[Socket]:
    with client.websocket_connect(f"/ws/games/{game_id}") as raw:
        socket = Socket(raw)
        socket.send("auth", {"token": account.token})
        yield socket


@contextmanager
def live_game(
    client: TestClient, game_id: str, white: Account, black: Account
) -> Iterator[tuple[Socket, Socket]]:
    """Connect both players and consume the start-up events."""
    with socket_for(client, game_id, white) as w:
        w.expect("connected")
        with socket_for(client, game_id, black) as b:
            b.expect("connected")
            w.expect("player_connected")
            w.expect("game_started")
            b.expect("game_started")
            yield w, b


def play(white: Socket, black: Socket, moves: list[str]) -> list[dict[str, Any]]:
    """Play moves in turn, asserting both clients get identical updates. Returns accepted states."""
    states = []
    for index, uci in enumerate(moves):
        (white if index % 2 == 0 else black).move(uci)
        seen_by_white = white.expect("move_accepted")
        seen_by_black = black.expect("move_accepted")
        assert seen_by_white == seen_by_black
        state = seen_by_white["state"]
        states.append(state)
        if state["status"] == "active":
            assert white.expect("turn_changed") == black.expect("turn_changed")
    return states

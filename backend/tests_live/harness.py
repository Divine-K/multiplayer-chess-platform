"""Helpers for match tests against a real API process: real HTTP, real WebSockets, real PostgreSQL.

An independent python-chess board follows every game, so the server's positions are checked
against a second source on each move. Every game that is played is written to a session log.
"""

import asyncio
import contextlib
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import chess
import httpx
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed
from websockets.typing import Origin

BACKEND_DIR = Path(__file__).resolve().parent.parent
PASSWORD = "live-test-password-1"
ORIGIN = "http://localhost:5173"
# Stay under the server's per-socket message limit.
MOVE_PAUSE_SECONDS = 0.03


class ApiServer:
    """A uvicorn process that the tests own, so they can stop and restart it."""

    def __init__(self, env: dict[str, str], log_path: Path) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.env = os.environ | env
        self.log_path = log_path
        self.process: subprocess.Popen[bytes] | None = None

    @property
    def http_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def ws_url(self) -> str:
        return f"ws://127.0.0.1:{self.port}"

    def start(self) -> None:
        with self.log_path.open("ab") as log:
            self.process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(self.port)],
                cwd=BACKEND_DIR,
                env=self.env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            with contextlib.suppress(httpx.HTTPError):
                if httpx.get(f"{self.http_url}/health/ready", timeout=1).status_code == 200:
                    return
            time.sleep(0.1)
        raise RuntimeError(f"API did not become ready; see {self.log_path}")

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None

    def restart(self) -> None:
        self.stop()
        self.start()


@dataclass
class SessionLog:
    """One entry per game actually created during the run."""

    entries: dict[str, dict[str, Any]] = field(default_factory=dict)
    scenario: str = "unknown"

    def opened(self, game_id: str) -> None:
        self.entries[game_id] = {"scenario": self.scenario, "plies": 0, "status": "created"}

    def update(self, state: dict[str, Any]) -> None:
        entry = self.entries.get(state["game_id"])
        if entry is not None:
            entry.update(
                plies=state["ply"],
                status=state["status"],
                result=state["result"],
                reason=state["result_reason"],
            )


@dataclass
class User:
    api: httpx.AsyncClient
    id: int
    username: str
    email: str
    token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.api.get(f"/api/v1{path}", headers=self.headers, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return await self.api.post(f"/api/v1{path}", headers=self.headers, **kwargs)

    async def statistics(self) -> dict[str, int]:
        return cast(dict[str, int], (await self.get("/users/me/statistics")).json())

    async def join(self, seconds: int = 180) -> httpx.Response:
        return await self.post("/matchmaking", json={"time_control_seconds": seconds, "increment_seconds": 0})


class Player:
    """One user's socket on one game, with every received message kept in order."""

    def __init__(self, user: User, color: str, game_id: str, ws_url: str, log: SessionLog) -> None:
        self.user = user
        self.color = color
        self.game_id = game_id
        self.ws_url = ws_url
        self.log = log
        self.socket: ClientConnection | None = None

    async def connect(self, origin: str | None = ORIGIN) -> dict[str, Any]:
        self.socket = await connect(
            f"{self.ws_url}/ws/games/{self.game_id}", origin=None if origin is None else Origin(origin)
        )
        await self.send("auth", {"token": self.user.token})
        return await self.expect("connected")

    async def disconnect(self) -> None:
        assert self.socket is not None
        await self.socket.close()

    async def send(self, type_: str, payload: dict[str, Any] | None = None) -> None:
        assert self.socket is not None
        await self.socket.send(json.dumps({"type": type_, "payload": payload or {}}))

    async def receive(self, timeout: float = 10) -> dict[str, Any]:
        assert self.socket is not None
        message: dict[str, Any] = json.loads(await asyncio.wait_for(self.socket.recv(), timeout))
        if "state" in message["payload"]:
            self.log.update(message["payload"]["state"])
        return message

    async def expect(self, type_: str, timeout: float = 10) -> dict[str, Any]:
        """Read until a message of this type arrives; presence and clock events may precede it."""
        deadline = time.monotonic() + timeout
        seen: list[str] = []
        while True:
            try:
                message = await self.receive(max(0.01, deadline - time.monotonic()))
            except TimeoutError:
                raise AssertionError(f"No '{type_}' for {self.color}; saw {seen}") from None
            if message["type"] == type_:
                return message
            if message["type"] in ("error", "move_rejected"):
                raise AssertionError(f"Unexpected {message['type']}: {message['payload']}")
            seen.append(message["type"])

    async def expect_error(self) -> str:
        while (message := await self.receive())["type"] != "error":
            assert message["type"] != "move_accepted"
        return str(message["payload"]["code"])

    async def close_code(self, timeout: float = 10) -> int:
        try:
            while True:
                await self.receive(timeout)
        except ConnectionClosed as closed:
            assert closed.rcvd is not None
            return closed.rcvd.code

    async def move(self, uci: str) -> None:
        payload = {"from": uci[:2], "to": uci[2:4]}
        if len(uci) > 4:
            payload["promotion"] = uci[4]
        await self.send("move", payload)

    async def sync(self) -> dict[str, Any]:
        await self.send("sync")
        return cast(dict[str, Any], (await self.expect("state"))["payload"]["state"])


Scenario = Callable[["World"], Coroutine[Any, Any, None]]
Run = Callable[[Scenario], None]


@dataclass
class Match:
    game_id: str
    white: Player
    black: Player
    board: chess.Board = field(default_factory=chess.Board)

    def player(self, color: str) -> Player:
        return self.white if color == "white" else self.black

    @property
    def mover(self) -> Player:
        return self.white if self.board.turn == chess.WHITE else self.black

    @property
    def waiter(self) -> Player:
        return self.black if self.board.turn == chess.WHITE else self.white

    async def connect(self) -> dict[str, Any]:
        await self.white.connect()
        await self.black.connect()
        started = await self.white.expect("game_started")
        await self.black.expect("game_started")
        return cast(dict[str, Any], started["payload"]["state"])

    async def play(self, uci: str) -> dict[str, Any]:
        """Play one move and check that both players receive the same, correct position."""
        mover = self.mover
        await mover.move(uci)
        states = []
        for player in (self.white, self.black):
            states.append((await player.expect("move_accepted"))["payload"]["state"])
        self.board.push_uci(uci)
        for state in states:
            assert state["fen"] == self.board.fen(en_passant="legal"), uci
            assert state["ply"] == len(self.board.move_stack)
            assert state["is_check"] == self.board.is_check()
        assert states[0]["version"] == states[1]["version"]
        await asyncio.sleep(MOVE_PAUSE_SECONDS)
        return cast(dict[str, Any], states[0])

    async def play_all(self, moves: str) -> dict[str, Any]:
        state: dict[str, Any] = {}
        for uci in moves.split():
            state = await self.play(uci)
        return state

    async def reject(self, player: Player, uci: str, code: str) -> None:
        """The server refuses the move, tells only the sender and changes nothing."""
        before = await player.sync()
        await player.move(uci)
        while (message := await player.receive())["type"] != "move_rejected":
            assert message["type"] != "move_accepted", f"{uci} was accepted"
        assert message["payload"]["code"] == code, message["payload"]
        after = await player.sync()
        assert (after["fen"], after["ply"], after["version"]) == (
            before["fen"],
            before["ply"],
            before["version"],
        )

    async def finished(self, result: str | None, reason: str, timeout: float = 10) -> dict[str, Any]:
        states = []
        for player in (self.white, self.black):
            states.append((await player.expect("game_finished", timeout))["payload"]["state"])
        for state in states:
            assert (state["result"], state["result_reason"]) == (result, reason)
            assert state["legal_moves"] == []
        return cast(dict[str, Any], states[0])

    async def close(self) -> None:
        for player in (self.white, self.black):
            if player.socket is not None:
                await player.socket.close()


class World:
    """Factory for users and matches against one running API."""

    def __init__(self, server: ApiServer, api: httpx.AsyncClient, log: SessionLog) -> None:
        self.server = server
        self.api = api
        self.log = log
        # Two pairings in flight could otherwise be matched with each other.
        self._pairing = asyncio.Lock()

    async def user(self) -> User:
        name = f"live_{uuid.uuid4().hex[:12]}"
        email = f"{name}@live-players.dev"
        created = await self.api.post(
            "/api/v1/auth/register", json={"username": name, "email": email, "password": PASSWORD}
        )
        assert created.status_code == 201, created.text
        login = await self.api.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        assert login.status_code == 200, login.text
        return User(self.api, created.json()["id"], name, email, login.json()["access_token"])

    async def pair(self, first: User, second: User, seconds: int = 180) -> Match:
        async with self._pairing:
            queued = await first.join(seconds)
            assert queued.json()["status"] == "queued", queued.text
            matched = (await second.join(seconds)).json()
        assert matched["status"] == "matched", matched
        game_id = matched["game_id"]
        self.log.opened(game_id)
        colors = {second.id: matched["color"]}
        colors[first.id] = "black" if matched["color"] == "white" else "white"
        players = {
            colors[u.id]: Player(u, colors[u.id], game_id, self.server.ws_url, self.log)
            for u in (first, second)
        }
        return Match(game_id, players["white"], players["black"])

    async def match(self, seconds: int = 180) -> Match:
        """Two new users, matched, connected and playing."""
        match = await self.pair(await self.user(), await self.user(), seconds)
        state = await match.connect()
        assert state["status"] == "active" and state["ply"] == 0
        return match


@contextlib.asynccontextmanager
async def world_for(server: ApiServer, log: SessionLog) -> AsyncIterator[World]:
    async with httpx.AsyncClient(base_url=server.http_url, timeout=20) as api:
        yield World(server, api, log)

"""Authentication, authorisation and hostile input against the running API."""

import asyncio
import json
import uuid
from collections.abc import Awaitable

import httpx
import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.typing import Origin

from tests_live.harness import PASSWORD, Player, Run, World


def test_registration_and_login_rules(run: Run) -> None:
    async def scenario(world: World) -> None:
        user = await world.user()
        api = world.api
        duplicate = {"username": user.username, "email": f"x_{user.email}", "password": PASSWORD}
        assert (await api.post("/api/v1/auth/register", json=duplicate)).status_code == 409
        same_email = {"username": "x" + user.username, "email": user.email.upper(), "password": PASSWORD}
        assert (await api.post("/api/v1/auth/register", json=same_email)).status_code == 409
        weak = {"username": "weakling_1", "email": "weak@live-players.dev", "password": "short"}
        assert (await api.post("/api/v1/auth/register", json=weak)).status_code == 422
        wrong = await api.post("/api/v1/auth/login", json={"email": user.email, "password": "nope-nope"})
        unknown = await api.post(
            "/api/v1/auth/login", json={"email": "ghost@live-players.dev", "password": "nope-nope"}
        )
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json() == unknown.json()
        profile = (await user.get(f"/users/{user.username}")).json()
        assert "email" not in profile and "password_hash" not in json.dumps(profile)

    run(scenario)


def test_validation_errors_do_not_echo_the_password(run: Run) -> None:
    async def scenario(world: World) -> None:
        secret = "s3cr3t!"  # too short, so the request fails validation
        for path, body in [
            ("register", {"username": "someone_1", "email": "a@live-players.dev", "password": secret}),
            ("register", {"username": "someone_1", "password": "a-long-secret-value"}),
            ("login", {"email": "not-an-email", "password": "a-long-secret-value"}),
        ]:
            response = await world.api.post(f"/api/v1/auth/{path}", json=body)
            assert response.status_code == 422
            assert body["password"] not in response.text, response.text

    run(scenario)


@pytest.mark.parametrize("header", [None, "Bearer", "Bearer nonsense", "Basic abc"])
def test_protected_routes_need_a_valid_token(run: Run, header: str | None) -> None:
    async def scenario(world: World) -> None:
        headers = {} if header is None else {"Authorization": header}
        for path in ("users/me", "games/active", "games/history", "matchmaking/status"):
            assert (await world.api.get(f"/api/v1/{path}", headers=headers)).status_code == 401

    run(scenario)


def test_outsiders_cannot_read_or_join_a_game(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        outsider = await world.user()
        assert (await outsider.get(f"/games/{match.game_id}")).status_code == 403
        assert (await outsider.get(f"/games/{match.game_id}/result")).status_code == 403
        assert (await outsider.post(f"/games/{match.game_id}/resign")).status_code == 403
        spy = Player(outsider, "none", match.game_id, world.server.ws_url, world.log)
        with pytest.raises(ConnectionClosed) as closed:
            await spy.connect()
        assert closed.value.rcvd is not None and closed.value.rcvd.code == 4403
        await match.play("e2e4")  # the real game is unaffected
        await match.close()

    run(scenario)


def test_socket_rejections(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        url = f"{world.server.ws_url}/ws/games/{match.game_id}"

        async def close_code(first: str, target: str = url) -> int:
            async with connect(target) as ws:
                await ws.send(first)
                try:
                    while True:
                        await asyncio.wait_for(ws.recv(), 10)
                except ConnectionClosed as closed:
                    assert closed.rcvd is not None
                    return int(closed.rcvd.code)

        auth = json.dumps({"type": "auth", "payload": {"token": match.white.user.token}})
        assert await close_code('{"type":"auth","payload":{"token":"forged"}}') == 4401
        assert await close_code('{"type":"move","payload":{"from":"e2","to":"e4"}}') == 4401
        assert await close_code("not json") == 4401
        assert await close_code("x" * 5000) == 1009
        assert await close_code(auth, f"{world.server.ws_url}/ws/games/{uuid.uuid4()}") == 4404
        with pytest.raises((InvalidStatus, ConnectionClosed)):
            async with connect(url, origin=Origin("https://evil.example")) as ws:
                await ws.send(auth)
                await ws.recv()
        await match.play("e2e4")
        await match.close()

    run(scenario)


def test_flooding_and_garbage_close_the_socket(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        for _ in range(60):
            try:
                await match.black.send("ping")
            except ConnectionClosed:
                break
        assert await match.black.close_code() == 4429
        await match.black.connect()
        assert match.black.socket is not None
        for _ in range(5):
            await match.black.socket.send('{"type":"teleport","payload":{}}')
        assert await match.black.close_code() == 4400
        await match.black.connect()
        await match.play("e2e4")
        await match.close()

    run(scenario)


def test_client_cannot_dictate_results_or_clocks(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        for forged in (
            {"type": "game_finished", "payload": {"result": "white_win"}},
            {"type": "move", "payload": {"from": "e2", "to": "e4", "white_ms": 999999999}},
            {"type": "resign", "payload": {"color": "black"}},
        ):
            assert match.white.socket is not None
            await match.white.socket.send(json.dumps(forged))
            assert (await match.white.expect_error()) == "invalid_message"
        state = await match.white.sync()
        assert (state["status"], state["ply"]) == ("active", 0)
        assert state["clocks"]["white_ms"] <= 180_000
        await match.close()

    run(scenario)


def test_cors_allows_only_the_configured_origin(run: Run) -> None:
    async def scenario(world: World) -> None:
        def preflight(origin: str) -> Awaitable[httpx.Response]:
            return world.api.options(
                "/api/v1/auth/login",
                headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
            )

        good = await preflight("http://localhost:5173")
        assert good.headers.get("access-control-allow-origin") == "http://localhost:5173"
        bad = await preflight("https://evil.example")
        assert "access-control-allow-origin" not in bad.headers

    run(scenario)

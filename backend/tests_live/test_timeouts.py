"""Real flag falls. The shortest time control is three minutes, so these games run side by side."""

import asyncio
import time
from typing import Any, cast

import pytest

from tests_live import scripts_for_endings as endings
from tests_live.harness import Match, Player, Run, World

FLAG_WAIT_SECONDS = 200


async def _quiet_wait(match: Match, result: str, reason: str) -> dict[str, Any]:
    """Wait for the flag while pinging, so the sockets are not closed as idle."""

    async def wait_on(player: Player) -> dict[str, Any]:
        deadline = time.monotonic() + FLAG_WAIT_SECONDS
        while time.monotonic() < deadline:
            try:
                message = await player.receive(timeout=20)
            except TimeoutError:
                message = None
            if message and message["type"] == "game_finished":
                return cast(dict[str, Any], message["payload"]["state"])
            if message is None or message["type"] == "clock_updated":
                await player.send("ping")
        raise AssertionError("The flag never fell")

    states = await asyncio.gather(wait_on(match.white), wait_on(match.black))
    for state in states:
        assert (state["result"], state["result_reason"]) == (result, reason)
    return states[0]


@pytest.mark.slow
@pytest.mark.timeout(300)
def test_real_flag_falls(run: Run) -> None:
    async def scenario(world: World) -> None:
        async def white_flags() -> None:
            match = await world.match()
            started = time.monotonic()
            state = await _quiet_wait(match, "black_win", "timeout")
            assert 178 <= time.monotonic() - started <= 183
            assert state["clocks"]["white_ms"] == 0
            await match.reject(match.white, "e2e4", "game_not_active")
            assert (await match.black.user.statistics())["wins"] == 1
            await match.close()

        async def black_flags() -> None:
            match = await world.match()
            await match.play("e2e4")
            state = await _quiet_wait(match, "white_win", "timeout")
            assert state["clocks"]["black_ms"] == 0 and state["clocks"]["white_ms"] > 170_000
            await match.close()

        async def flag_while_both_are_away() -> None:
            match = await world.match()
            await match.play_all("e2e4 e7e5")
            await match.close()
            await asyncio.sleep(185)
            result = (await match.white.user.get(f"/games/{match.game_id}")).json()
            world.log.update(result)
            assert (result["result"], result["result_reason"]) == ("black_win", "timeout")
            history = (await match.black.user.get("/games/history")).json()
            assert history["items"][0]["outcome"] == "win"

        async def flag_against_insufficient_material() -> None:
            match = await world.match()
            await match.play_all(" ".join(endings.bare_opponent_position()))
            await _quiet_wait(match, "draw", "timeout_vs_insufficient_material")
            assert (await match.white.user.statistics())["draws"] == 1
            await match.close()

        await asyncio.gather(
            white_flags(), black_flags(), flag_while_both_are_away(), flag_against_insufficient_material()
        )

    run(scenario)

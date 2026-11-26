"""Resignation, draws, connections, restarts, matchmaking and saved results."""

import asyncio

import pytest

from tests_live.harness import Match, Player, Run, World


async def _record(player: Player) -> tuple[int, int, int, int]:
    s = await player.user.statistics()
    return s["games_played"], s["wins"], s["losses"], s["draws"]


@pytest.mark.parametrize("quitter", ["white", "black"])
def test_resignation_over_the_socket(run: Run, quitter: str) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all("e2e4 e7e5")
        await match.player(quitter).send("resign")
        winner = "black" if quitter == "white" else "white"
        await match.finished(f"{winner}_win", "resignation")
        assert await _record(match.player(winner)) == (1, 1, 0, 0)
        assert await _record(match.player(quitter)) == (1, 0, 1, 0)
        await match.close()

    run(scenario)


def test_resignation_over_rest_reaches_both_sockets(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        response = await match.black.user.post(f"/games/{match.game_id}/resign")
        assert response.status_code == 200
        await match.finished("white_win", "resignation")
        again = await match.black.user.post(f"/games/{match.game_id}/resign")
        assert again.status_code == 409
        await match.close()

    run(scenario)


def test_draw_by_agreement(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all("e2e4 e7e5")
        await match.white.send("offer_draw")
        await match.black.expect("draw_offered")
        await match.black.send("accept_draw")
        await match.finished("draw", "draw_agreement")
        for player in (match.white, match.black):
            assert await _record(player) == (1, 0, 0, 1)
        await match.close()

    run(scenario)


def test_declined_draw_and_play_continues(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.white.send("offer_draw")
        await match.black.expect("draw_offered")
        await match.black.send("decline_draw")
        declined = await match.white.expect("draw_declined")
        assert declined["payload"]["state"]["draw_offered_by"] is None
        await match.black.expect("draw_declined")
        state = await match.play("e2e4")
        assert state["status"] == "active"
        await match.close()

    run(scenario)


def test_draw_offer_rules(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.white.send("accept_draw")  # nothing to accept
        assert (await match.white.receive())["payload"]["code"] == "invalid_draw_action"
        await match.white.send("offer_draw")
        await match.white.expect("draw_offered")
        await match.black.expect("draw_offered")
        await match.white.send("accept_draw")  # not your own offer
        assert (await match.white.receive())["type"] == "error"
        await match.play("e2e4")  # the offerer moving keeps the offer open
        state = await match.play("e7e5")  # the opponent moving declines it
        assert state["draw_offered_by"] is None
        await match.white.send("offer_draw")
        await match.black.expect("draw_offered")
        await match.black.send("offer_draw")  # crossing offers agree the draw
        await match.finished("draw", "draw_agreement")
        await match.close()

    run(scenario)


def test_simultaneous_resignations_record_one_result(run: Run) -> None:
    async def scenario(world: World) -> None:
        for _ in range(3):
            match = await world.match()
            await asyncio.gather(match.white.send("resign"), match.black.send("resign"))
            await asyncio.sleep(0.5)
            result = (await match.white.user.get(f"/games/{match.game_id}/result")).json()
            assert result["result"] in ("white_win", "black_win")
            for player in (match.white, match.black):
                assert (await _record(player))[0] == 1
            await match.close()

    run(scenario)


def test_move_racing_a_resignation_stays_consistent(run: Run) -> None:
    async def scenario(world: World) -> None:
        for _ in range(3):
            match = await world.match()
            await asyncio.gather(match.white.move("e2e4"), match.black.send("resign"))
            await asyncio.sleep(0.5)
            state = (await match.white.user.get(f"/games/{match.game_id}")).json()
            world.log.update(state)
            assert (state["status"], state["result"]) == ("finished", "white_win")
            assert state["ply"] in (0, 1)
            assert (await _record(match.white)) == (1, 1, 0, 0)
            await match.close()

    run(scenario)


def test_duplicate_move_messages_apply_once(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await asyncio.gather(*(match.white.move("e2e4") for _ in range(5)))
        await asyncio.sleep(1)
        state = (await match.white.user.get(f"/games/{match.game_id}")).json()
        world.log.update(state)
        assert state["ply"] == 1
        await match.close()

    run(scenario)


@pytest.mark.parametrize("dropped", ["white", "black"])
def test_disconnect_and_reconnect(run: Run, dropped: str) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all("e2e4 e7e5 g1f3")
        gone = match.player(dropped)
        stayed = match.player("black" if dropped == "white" else "white")
        await gone.disconnect()
        assert (await stayed.expect("player_disconnected"))["payload"]["color"] == dropped
        connected = await gone.connect()
        assert connected["payload"]["state"]["fen"] == match.board.fen(en_passant="legal")
        assert connected["payload"]["state"]["ply"] == 3
        assert (await stayed.expect("player_connected"))["payload"]["color"] == dropped
        await match.play("b8c6")
        await match.close()

    run(scenario)


def test_opponent_moves_while_player_is_away(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play("e2e4")
        await match.white.disconnect()
        await match.black.expect("player_disconnected")
        await match.black.move("e7e5")
        await match.black.expect("move_accepted")
        match.board.push_uci("e7e5")
        state = (await match.white.connect())["payload"]["state"]
        assert state["fen"] == match.board.fen(en_passant="legal")
        await match.black.expect("player_connected")
        await match.play("g1f3")
        await match.close()

    run(scenario)


def test_clock_runs_while_both_are_away(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play("e2e4")
        before = (await match.black.sync())["clocks"]["black_ms"]
        await match.close()
        await asyncio.sleep(3)
        state = (await match.black.connect())["payload"]["state"]
        assert 2700 <= before - state["clocks"]["black_ms"] <= 5000
        await match.white.connect()
        await match.play("e7e5")
        await match.close()

    run(scenario)


def test_newest_connection_replaces_the_old_one(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        first = match.white
        second = Player(first.user, "white", match.game_id, first.ws_url, world.log)
        await second.connect()
        assert await first.close_code() == 4409
        match.white = second
        await match.play("e2e4")
        await match.close()

    run(scenario)


def test_game_survives_a_server_restart(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.match()
        await match.play_all("e2e4 c7c5 g1f3")
        before = await match.black.sync()
        await match.close()
        await asyncio.to_thread(world.server.restart)
        await match.white.connect()
        after = (await match.black.connect())["payload"]["state"]
        assert (after["fen"], after["ply"]) == (before["fen"], 3)
        assert after["clocks"]["black_ms"] < before["clocks"]["black_ms"]
        await match.play("d7d6")
        await match.close()

    run(scenario)


def test_unstarted_game_is_aborted_without_statistics(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.pair(await world.user(), await world.user())
        await match.white.connect()  # the opponent never arrives
        finished = await match.white.expect("game_finished", timeout=15)
        state = finished["payload"]["state"]
        assert (state["status"], state["result_reason"]) == ("aborted", "never_started")
        for player in (match.white, match.black):
            assert await _record(player) == (0, 0, 0, 0)
        again = await match.white.user.join()
        assert again.json()["status"] == "queued"
        await match.white.user.api.delete("/api/v1/matchmaking", headers=match.white.user.headers)
        await match.close()

    run(scenario)


def test_leaving_before_the_start_aborts(run: Run) -> None:
    async def scenario(world: World) -> None:
        match = await world.pair(await world.user(), await world.user())
        response = await match.black.user.post(f"/games/{match.game_id}/resign")
        world.log.update(response.json())
        assert response.json()["status"] == "aborted"
        assert await _record(match.black) == (0, 0, 0, 0)

    run(scenario)


def test_concurrent_matchmaking_pairs_everyone_once(run: Run) -> None:
    async def scenario(world: World) -> None:
        users = await asyncio.gather(*(world.user() for _ in range(20)))
        responses = await asyncio.gather(*(u.join(300) for u in users))
        assert all(r.status_code == 200 for r in responses)
        statuses = await asyncio.gather(*(u.get("/matchmaking/status") for u in users))
        assigned = [s.json() for s in statuses]
        assert all(a["status"] == "matched" for a in assigned), assigned
        games: dict[str, list[str]] = {}
        for item in assigned:
            games.setdefault(item["game_id"], []).append(item["color"])
        assert len(games) == 10
        assert all(sorted(colors) == ["black", "white"] for colors in games.values())
        # These games are real: play one move in each through both sockets.
        matches: list[Match] = []
        for game_id in games:
            world.log.opened(game_id)
            seats = {
                a["color"]: Player(u, a["color"], game_id, world.server.ws_url, world.log)
                for u, a in zip(users, assigned, strict=True)
                if a["game_id"] == game_id
            }
            matches.append(Match(game_id, seats["white"], seats["black"]))

        async def play(match: Match) -> None:
            await match.connect()
            await match.play("e2e4")
            await match.black.send("resign")
            await match.finished("white_win", "resignation")
            await match.close()

        await asyncio.gather(*(play(m) for m in matches))

    run(scenario)


def test_matchmaking_rules(run: Run) -> None:
    async def scenario(world: World) -> None:
        a, b, c = [await world.user() for _ in range(3)]
        assert (await a.join(180)).json()["status"] == "queued"
        assert (await a.join(180)).status_code == 409
        assert (await b.join(600)).json()["status"] == "queued"  # different time control
        assert (await a.join(120)).status_code == 422
        cancelled = await a.api.delete("/api/v1/matchmaking", headers=a.headers)
        assert cancelled.json()["status"] == "idle"
        assert (await c.join(180)).json()["status"] == "queued"  # a really left
        matched = (await a.join(600)).json()
        assert matched["status"] == "matched"
        world.log.opened(matched["game_id"])
        assert (await a.join(180)).status_code == 409  # already in a game
        response = await a.post(f"/games/{matched['game_id']}/resign")
        world.log.update(response.json())
        await c.api.delete("/api/v1/matchmaking", headers=c.headers)

    run(scenario)


def test_history_and_statistics_across_several_games(run: Run) -> None:
    async def scenario(world: World) -> None:
        a, b = await world.user(), await world.user()
        expected: dict[int, list[str]] = {a.id: [], b.id: []}
        for ending in ("a_resigns", "b_resigns", "draw"):
            match = await world.pair(a, b)
            await match.connect()
            await match.play_all("e2e4 e7e5")
            seat = {p.user.id: p for p in (match.white, match.black)}
            if ending == "draw":
                await match.white.send("offer_draw")
                await match.black.expect("draw_offered")
                await match.black.send("accept_draw")
                outcomes = {a.id: "draw", b.id: "draw"}
            else:
                loser, winner = (a, b) if ending == "a_resigns" else (b, a)
                await seat[loser.id].send("resign")
                outcomes = {loser.id: "loss", winner.id: "win"}
            for player in (match.white, match.black):
                await player.expect("game_finished")
            for user_id, outcome in outcomes.items():
                expected[user_id].insert(0, outcome)
            await match.close()
        for user in (a, b):
            history = (await user.get("/games/history", params={"limit": 2})).json()
            assert history["total"] == 3
            rest = (await user.get("/games/history", params={"limit": 2, "offset": 2})).json()
            rows = history["items"] + rest["items"]
            assert [r["outcome"] for r in rows] == expected[user.id]
            assert all(r["move_count"] == 2 for r in rows)
            assert await user.statistics() == {"games_played": 3, "wins": 1, "losses": 1, "draws": 1}

    run(scenario)

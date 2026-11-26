"""The WebSocket protocol, exercised end to end through the ASGI app and a real database."""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.main import create_app
from tests.factories import FASTEST_STALEMATE
from tests.gameplay_helpers import Account, Socket, live_game, make_account, match, play, socket_for

Game = tuple[str, Account, Account]


@pytest.fixture
def game(client: TestClient, db_session: Session) -> Game:
    return match(client, make_account(db_session, "ann"), make_account(db_session, "ben"))


def tuned_client(**settings: Any) -> Iterator[TestClient]:
    with TestClient(create_app(get_settings().model_copy(update=settings))) as test_client:
        yield test_client


def expect_close(socket: Socket, code: int) -> None:
    """The reason is announced as a message, then repeated as the close code."""
    assert socket.expect("closing") == {"code": code}
    with pytest.raises(WebSocketDisconnect) as closed:
        socket.raw.receive_json()
    assert closed.value.code == code


# ----- Connection and synchronisation ---------------------------------------------------------


def test_game_starts_only_when_both_players_are_connected(client: TestClient, game: Game) -> None:
    game_id, white, black = game
    with socket_for(client, game_id, white) as w:
        hello = w.expect("connected")
        assert (hello["color"], hello["opponent_connected"]) == ("white", False)
        assert hello["state"]["status"] == "waiting" and hello["state"]["clocks"]["running"] is None
        w.assert_nothing_pending()

        with socket_for(client, game_id, black) as b:
            hello = b.expect("connected")
            assert (hello["color"], hello["opponent_connected"]) == ("black", True)
            assert w.expect("player_connected") == {"color": "black"}
            started_w, started_b = w.expect("game_started"), b.expect("game_started")
            assert started_w == started_b
            assert started_w["state"]["status"] == "active"
            assert started_w["state"]["clocks"]["running"] == "white"
            assert len(started_w["state"]["legal_moves"]) == 20


def test_moves_are_synchronised_to_both_players(client: TestClient, game: Game) -> None:
    with live_game(client, *game) as (w, b):
        states = play(w, b, ["e2e4", "e7e5", "g1f3"])
        final = states[-1]
        assert final["turn"] == "black" and final["ply"] == 3
        assert [m["san"] for m in final["moves"]] == ["e4", "e5", "Nf3"]
        assert [s["version"] for s in states] == sorted({s["version"] for s in states})


def test_rejections_go_only_to_the_sender_with_the_true_state(client: TestClient, game: Game) -> None:
    with live_game(client, *game) as (w, b):
        w.move("e2e5")
        rejected = w.expect("move_rejected")
        assert rejected["code"] == "illegal_move" and rejected["state"]["ply"] == 0
        b.move("e7e5")
        assert b.expect("move_rejected")["code"] == "not_your_turn"
        w.assert_nothing_pending()
        b.assert_nothing_pending()


def test_a_player_cannot_move_the_opponents_pieces(client: TestClient, game: Game) -> None:
    with live_game(client, *game) as (w, _):
        w.move("e7e5")
        assert w.expect("move_rejected")["code"] == "illegal_move"


@pytest.mark.parametrize(
    ("moves", "san"),
    [
        (["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6", "e1g1"], "O-O"),
        (["e2e4", "a7a6", "e4e5", "d7d5", "e5d6"], "exd6"),
        (["b2b4", "a7a5", "b4a5", "b7b6", "a5b6", "c8b7", "b6c7", "b7c6", "c7d8q"], "cxd8=Q+"),
    ],
    ids=["castling", "en-passant", "promotion"],
)
def test_special_moves_over_the_socket(client: TestClient, game: Game, moves: list[str], san: str) -> None:
    with live_game(client, *game) as (w, b):
        assert play(w, b, moves)[-1]["moves"][-1]["san"] == san


def test_promotion_without_a_choice_is_rejected(client: TestClient, game: Game) -> None:
    with live_game(client, *game) as (w, b):
        play(w, b, ["b2b4", "a7a5", "b4a5", "b7b6", "a5b6", "c8b7", "b6c7", "b7c6"])
        w.move("c7d8")
        assert w.expect("move_rejected")["code"] == "promotion_required"


@pytest.mark.parametrize(
    ("moves", "result", "reason"),
    [
        (["f2f3", "e7e5", "g2g4", "d8h4"], "black_win", "checkmate"),
        (["e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7"], "white_win", "checkmate"),
        (FASTEST_STALEMATE, "draw", "stalemate"),
        (["g1f3", "g8f6", "f3g1", "f6g8"] * 2, "draw", "threefold_repetition"),
    ],
    ids=["fools-mate", "scholars-mate", "stalemate", "threefold"],
)
def test_games_played_to_completion(
    client: TestClient, game: Game, moves: list[str], result: str, reason: str
) -> None:
    with live_game(client, *game) as (w, b):
        play(w, b, moves)
        for socket in (w, b):
            finished = socket.expect("game_finished")
            assert (finished["result"], finished["result_reason"]) == (result, reason)
            assert finished["state"]["legal_moves"] == []
        w.move("a2a3")
        assert w.expect("move_rejected")["code"] == "game_not_active"


def test_resign_over_the_socket(client: TestClient, game: Game) -> None:
    with live_game(client, *game) as (w, b):
        b.send("resign")
        assert w.expect("game_finished") == b.expect("game_finished")


def test_draw_negotiation_over_the_socket(client: TestClient, game: Game) -> None:
    with live_game(client, *game) as (w, b):
        w.send("offer_draw")
        assert w.expect("draw_offered")["by"] == "white"
        b.expect("draw_offered")
        w.send("accept_draw")
        assert w.expect("error")["code"] == "invalid_draw_action"
        b.send("decline_draw")
        w.expect("draw_declined")
        b.expect("draw_declined")
        b.send("offer_draw")
        w.expect("draw_offered")
        b.expect("draw_offered")
        w.send("accept_draw")
        for socket in (w, b):
            assert socket.expect("game_finished")["result_reason"] == "draw_agreement"


def test_sync_returns_the_current_state(client: TestClient, game: Game) -> None:
    with live_game(client, *game) as (w, b):
        play(w, b, ["d2d4"])
        b.send("sync")
        assert b.expect("state")["state"]["last_move"] == "d2d4"


# ----- Authentication and authorisation -------------------------------------------------------


@pytest.mark.parametrize(
    "first_message",
    [
        {"type": "auth", "payload": {"token": "not-a-real-token"}},
        {"type": "ping", "payload": {}},
        {"type": "move", "payload": {"from": "e2", "to": "e4"}},
        {"nonsense": True},
    ],
)
def test_connection_must_authenticate_first(
    client: TestClient, game: Game, first_message: dict[str, Any]
) -> None:
    with client.websocket_connect(f"/ws/games/{game[0]}") as raw:
        raw.send_json(first_message)
        expect_close(Socket(raw), 4401)


def test_outsiders_cannot_join_a_game(client: TestClient, game: Game, db_session: Session) -> None:
    eve = make_account(db_session, "eve")
    with socket_for(client, game[0], eve) as socket:
        expect_close(socket, 4403)


def test_unknown_game_is_reported(client: TestClient, game: Game) -> None:
    with socket_for(client, str(uuid.uuid4()), game[1]) as socket:
        expect_close(socket, 4404)


def test_auth_for_a_different_game_id_is_refused(client: TestClient, game: Game) -> None:
    game_id, white, _ = game
    with client.websocket_connect(f"/ws/games/{game_id}") as raw:
        raw.send_json({"type": "auth", "game_id": str(uuid.uuid4()), "payload": {"token": white.token}})
        expect_close(Socket(raw), 4401)


def test_cross_site_origins_are_refused(client: TestClient, game: Game) -> None:
    url = f"/ws/games/{game[0]}"
    with (
        pytest.raises(WebSocketDisconnect) as refused,
        client.websocket_connect(url, headers={"origin": "http://evil.example"}),
    ):
        pass
    assert refused.value.code == 4403
    with client.websocket_connect(url, headers={"origin": "http://localhost:5173"}) as raw:
        raw.send_json({"type": "auth", "payload": {"token": game[1].token}})
        assert raw.receive_json()["type"] == "connected"


# ----- Hostile and malformed input ------------------------------------------------------------


@pytest.mark.parametrize(
    "frame",
    [
        "not json",
        "[1,2,3]",
        '{"type":"teleport","payload":{}}',
        '{"type":"move","payload":{"from":"e2"}}',
        '{"type":"move","payload":{"from":"e2","to":"e4","clock_ms":999999}}',
        '{"type":"resign","payload":{},"game_id":"00000000-0000-0000-0000-000000000000"}',
        '{"type":"auth","payload":{"token":"again"}}',
    ],
)
def test_invalid_messages_get_an_error_and_the_socket_survives(
    client: TestClient, game: Game, frame: str
) -> None:
    with live_game(client, *game) as (w, b):
        w.raw.send_text(frame)
        assert w.expect("error")["code"] == "invalid_message"
        w.assert_nothing_pending()
        b.assert_nothing_pending()


def test_binary_frames_are_rejected(client: TestClient, game: Game) -> None:
    with live_game(client, *game) as (w, _):
        w.raw.send_bytes(b"\x00\x01")
        assert w.expect("error")["code"] == "invalid_message"


def test_repeated_garbage_closes_the_socket(client: TestClient, game: Game) -> None:
    with socket_for(client, game[0], game[1]) as w:
        w.expect("connected")
        for _ in range(5):
            w.raw.send_text("garbage")
        for _ in range(5):
            w.expect("error")
        expect_close(w, 4400)


def test_oversized_messages_close_the_socket(client: TestClient, game: Game) -> None:
    with socket_for(client, game[0], game[1]) as w:
        w.expect("connected")
        w.raw.send_text("x" * 5000)
        expect_close(w, 1009)


def test_message_flood_is_cut_off(client: TestClient, game: Game) -> None:
    with socket_for(client, game[0], game[1]) as w:
        w.expect("connected")
        for _ in range(25):
            w.send("ping")
        for _ in range(20):
            w.expect("pong")
        expect_close(w, 4429)


# ----- Disconnection and reconnection ---------------------------------------------------------


def test_disconnect_is_announced_and_reconnect_restores_the_game(client: TestClient, game: Game) -> None:
    game_id, white, black = game
    with socket_for(client, game_id, white) as w:
        w.expect("connected")
        with socket_for(client, game_id, black) as b:
            b.expect("connected")
            w.expect("player_connected")
            w.expect("game_started")
            b.expect("game_started")
            play(w, b, ["e2e4"])
        assert w.expect("player_disconnected") == {"color": "black"}

        with socket_for(client, game_id, black) as back:
            hello = back.expect("connected")
            assert hello["state"]["status"] == "active"
            assert [m["uci"] for m in hello["state"]["moves"]] == ["e2e4"]
            assert hello["state"]["clocks"]["running"] == "black"
            assert w.expect("player_connected") == {"color": "black"}
            back.move("e7e5")
            assert w.expect("move_accepted") == back.expect("move_accepted")


def test_a_newer_socket_replaces_the_old_one_quietly(client: TestClient, game: Game) -> None:
    game_id, white, black = game
    with (
        live_game(client, game_id, white, black) as (old_white, b),
        socket_for(client, game_id, white) as new,
    ):
        new.expect("connected")
        expect_close(old_white, 4409)
        assert b.expect("player_connected") == {"color": "white"}
        b.assert_nothing_pending()  # no spurious "disconnected" for the replaced socket
        new.move("e2e4")
        assert new.expect("move_accepted") == b.expect("move_accepted")


def test_idle_connections_are_closed(db_session: Session, game: Game) -> None:
    for client in tuned_client(ws_idle_timeout_seconds=0.3):
        with socket_for(client, game[0], game[1]) as w:
            w.expect("connected")
            expect_close(w, 4410)


def test_unauthenticated_connections_time_out(game: Game) -> None:
    for client in tuned_client(ws_auth_timeout_seconds=0.2):
        with client.websocket_connect(f"/ws/games/{game[0]}") as raw:
            expect_close(Socket(raw), 4408)


# ----- Server-driven events -------------------------------------------------------------------


def rewind(session: Session, game_id: str, column: str, seconds: int) -> None:
    """Move a server timestamp into the past to simulate elapsed time."""
    assert column in {"turn_started_at", "created_at"}
    session.execute(
        text(f"UPDATE games SET {column} = {column} - make_interval(secs => :s) WHERE id = :id"),
        {"s": seconds, "id": game_id},
    )
    session.commit()


def test_server_flags_a_player_without_any_client_action(
    client: TestClient, game: Game, db_session: Session
) -> None:
    with live_game(client, *game) as (w, b):
        rewind(db_session, game[0], "turn_started_at", 181)
        for socket in (w, b):
            finished = socket.expect("game_finished")
            assert (finished["result"], finished["result_reason"]) == ("black_win", "timeout")
            assert finished["state"]["clocks"]["white_ms"] == 0


def test_clock_expires_even_when_nobody_is_connected(
    client: TestClient, game: Game, db_session: Session
) -> None:
    game_id, white, black = game
    with live_game(client, game_id, white, black):
        pass
    rewind(db_session, game_id, "turn_started_at", 181)
    with socket_for(client, game_id, black) as b:
        state = b.expect("connected")["state"]
        if state["status"] == "active":  # connected before the sweeper's next pass
            b.expect("game_finished")
    result = client.get(f"/api/v1/games/{game_id}/result", headers=white.headers).json()
    assert result["result_reason"] == "timeout"


def test_games_that_never_start_are_aborted(client: TestClient, game: Game, db_session: Session) -> None:
    with socket_for(client, game[0], game[1]) as w:
        w.expect("connected")
        rewind(db_session, game[0], "created_at", 61)
        finished = w.expect("game_finished")
        assert (finished["status"], finished["result"]) == ("aborted", None)
    assert client.get("/api/v1/games/active", headers=game[1].headers).json() is None


def test_clocks_are_rebroadcast_periodically(db_session: Session, game: Game) -> None:
    for client in tuned_client(clock_sync_interval_seconds=0.3):
        with live_game(client, *game) as (w, b):
            first = w.expect("clock_updated")
            assert first["clocks"]["running"] == "white"
            assert b.expect("clock_updated")["clocks"]["running"] == "white"
            later = w.expect("clock_updated")
            assert later["clocks"]["white_ms"] < first["clocks"]["white_ms"]
            assert later["clocks"]["black_ms"] == first["clocks"]["black_ms"] == 180_000


def test_client_cannot_influence_the_clock(client: TestClient, game: Game, db_session: Session) -> None:
    with live_game(client, *game) as (w, b):
        rewind(db_session, game[0], "turn_started_at", 60)
        state = play(w, b, ["e2e4"])[0]
        assert 119_000 <= state["clocks"]["white_ms"] <= 120_000

"""REST endpoints for matchmaking, games, history and profiles."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.gameplay_helpers import Account, live_game, make_account, match, play

Pair = tuple[Account, Account]
QUEUE = "/api/v1/matchmaking"


@pytest.fixture
def pair(db_session: Session) -> Pair:
    return make_account(db_session, "ann"), make_account(db_session, "ben")


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", f"{QUEUE}/status"),
        ("post", QUEUE),
        ("delete", QUEUE),
        ("get", "/api/v1/games/active"),
        ("get", "/api/v1/games/history"),
        ("get", f"/api/v1/games/{uuid.uuid4()}"),
        ("post", f"/api/v1/games/{uuid.uuid4()}/resign"),
        ("get", "/api/v1/users/me/statistics"),
        ("get", "/api/v1/users/ann"),
    ],
)
def test_gameplay_endpoints_require_authentication(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path).status_code == 401


def test_time_controls_are_listed(client: TestClient) -> None:
    options = client.get(f"{QUEUE}/time-controls").json()
    assert [o["time_control_seconds"] for o in options] == [180, 300, 600]


def test_matchmaking_lifecycle(client: TestClient, pair: Pair) -> None:
    ann, ben = pair
    body = {"time_control_seconds": 300}
    assert client.get(f"{QUEUE}/status", headers=ann.headers).json()["status"] == "idle"
    assert client.post(QUEUE, json=body, headers=ann.headers).json()["status"] == "queued"
    assert client.post(QUEUE, json=body, headers=ann.headers).status_code == 409
    assert client.delete(QUEUE, headers=ann.headers).json()["status"] == "idle"

    game_id, white, black = match(client, ann, ben, 300)
    for account, color in ((white, "white"), (black, "black")):
        status = client.get(f"{QUEUE}/status", headers=account.headers).json()
        assert (status["status"], status["game_id"], status["color"]) == ("matched", game_id, color)
        assert client.post(QUEUE, json=body, headers=account.headers).status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"time_control_seconds": 42},
        {"time_control_seconds": "soon"},
        {"time_control_seconds": 300, "x": 1},
    ],
)
def test_matchmaking_validates_input(client: TestClient, pair: Pair, body: dict[str, object]) -> None:
    assert client.post(QUEUE, json=body, headers=pair[0].headers).status_code == 422


def test_game_state_is_private_to_its_players(client: TestClient, pair: Pair, db_session: Session) -> None:
    ann, ben = pair
    outsider = make_account(db_session, "eve")
    game_id, white, black = match(client, ann, ben)

    state = client.get(f"/api/v1/games/{game_id}", headers=white.headers).json()
    assert state["status"] == "waiting"
    assert state["players"]["white"]["username"] == white.username
    assert state["players"]["black"]["username"] == black.username
    assert client.get(f"/api/v1/games/{game_id}", headers=outsider.headers).status_code == 403
    assert client.get(f"/api/v1/games/{game_id}/result", headers=outsider.headers).status_code == 403
    assert client.post(f"/api/v1/games/{game_id}/resign", headers=outsider.headers).status_code == 403
    assert client.get(f"/api/v1/games/{uuid.uuid4()}", headers=white.headers).status_code == 404
    assert client.get("/api/v1/games/not-a-uuid", headers=white.headers).status_code == 422


def test_active_game_endpoint(client: TestClient, pair: Pair) -> None:
    ann, ben = pair
    assert client.get("/api/v1/games/active", headers=ann.headers).json() is None
    game_id, *_ = match(client, ann, ben)
    assert client.get("/api/v1/games/active", headers=ann.headers).json()["game_id"] == game_id


def test_results_history_statistics_and_profiles(client: TestClient, pair: Pair) -> None:
    game_id, white, black = match(client, *pair)
    with live_game(client, game_id, white, black) as (w, b):
        play(w, b, ["f2f3", "e7e5", "g2g4", "d8h4"])
        w.expect("game_finished")
        b.expect("game_finished")

    result = client.get(f"/api/v1/games/{game_id}/result", headers=white.headers).json()
    assert (result["result"], result["result_reason"]) == ("black_win", "checkmate")

    history = client.get("/api/v1/games/history?limit=5", headers=black.headers).json()
    assert history["total"] == 1
    row = history["items"][0]
    assert (row["outcome"], row["color"], row["move_count"]) == ("win", "black", 4)
    assert row["opponent"]["username"] == white.username

    mine = client.get("/api/v1/users/me/statistics", headers=white.headers).json()
    assert mine == {"games_played": 1, "wins": 0, "losses": 1, "draws": 0}

    profile = client.get(f"/api/v1/users/{black.username}", headers=white.headers).json()
    assert profile["statistics"]["wins"] == 1
    assert "email" not in profile and "password_hash" not in profile
    assert client.get("/api/v1/users/nobody_here", headers=white.headers).status_code == 404


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_history_pagination_is_bounded(client: TestClient, pair: Pair, query: str) -> None:
    response = client.get(f"/api/v1/games/history?{query}", headers=pair[0].headers)
    assert response.status_code == 422


def test_rest_resignation_is_pushed_to_both_sockets(client: TestClient, pair: Pair) -> None:
    game_id, white, black = match(client, *pair)
    with live_game(client, game_id, white, black) as (w, b):
        response = client.post(f"/api/v1/games/{game_id}/resign", headers=white.headers)
        assert response.status_code == 200 and response.json()["result"] == "black_win"
        for socket in (w, b):
            assert socket.expect("game_finished")["result_reason"] == "resignation"
    again = client.post(f"/api/v1/games/{game_id}/resign", headers=black.headers)
    assert again.status_code == 409

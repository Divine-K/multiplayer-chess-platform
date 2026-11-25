from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chess_core.engine import ChessEngine, IllegalMoveError
from app.models import GameResult, GameStatus, Move, PlayerColor, ResultReason, User
from app.services import game_queries, game_service
from app.services.errors import (
    DrawOfferError,
    GameNotActiveError,
    NotAParticipantError,
    NotYourTurnError,
)
from tests.factories import (
    FASTEST_STALEMATE,
    FOOLS_MATE,
    at,
    make_game,
    make_user,
    play_moves,
    run_concurrently,
)

Pair = tuple[User, User]


@pytest.fixture
def players(db_session: Session) -> Pair:
    return make_user(db_session, "white_p"), make_user(db_session, "black_p")


def stats(session: Session, user: User) -> tuple[int, int, int, int]:
    s = game_queries.statistics_for(session, user.id)
    return s.games_played, s.wins, s.losses, s.draws


def move_count(session: Session) -> int:
    return session.scalar(select(func.count(Move.id))) or 0


def test_game_starts_once(db_session: Session, players: Pair) -> None:
    game_id = make_game(db_session, *players, started=False)
    assert game_service.start_game(db_session, game_id, at(0))
    assert not game_service.start_game(db_session, game_id, at(9))
    game = game_service.load_game(db_session, game_id)
    assert game.status == GameStatus.ACTIVE
    assert game.started_at == at(0) and game.turn_started_at == at(0)


def test_no_moves_before_the_game_starts(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black, started=False)
    with pytest.raises(GameNotActiveError):
        game_service.submit_move(db_session, game_id, white.id, "e2", "e4", None, at(1))


def test_accepted_move_is_persisted_and_charges_the_clock(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black)
    outcome = game_service.submit_move(db_session, game_id, white.id, "e2", "e4", None, at(5))
    assert outcome.move is not None and outcome.move.san == "e4"

    game = game_service.load_game(db_session, game_id)
    assert [m.uci for m in game.moves] == ["e2e4"]
    assert (game.white_remaining_ms, game.black_remaining_ms) == (175_000, 180_000)
    assert game.turn_started_at == at(5)
    assert game.current_fen == game.moves[-1].fen_after
    state = game_queries.build_state(game, at(8))
    assert state.turn == PlayerColor.BLACK
    assert (state.clocks.white_ms, state.clocks.black_ms) == (175_000, 177_000)


def test_illegal_move_changes_nothing(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black)
    before = game_service.load_game(db_session, game_id).version
    with pytest.raises(IllegalMoveError):
        game_service.submit_move(db_session, game_id, white.id, "e2", "e5", None, at(5))
    game = game_service.load_game(db_session, game_id)
    assert move_count(db_session) == 0
    assert (game.version, game.white_remaining_ms, game.turn_started_at) == (before, 180_000, at(0))


def test_turn_enforcement(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black)
    with pytest.raises(NotYourTurnError):
        game_service.submit_move(db_session, game_id, black.id, "e7", "e5", None, at(1))
    game_service.submit_move(db_session, game_id, white.id, "e2", "e4", None, at(2))
    with pytest.raises(NotYourTurnError):
        game_service.submit_move(db_session, game_id, white.id, "d2", "d4", None, at(3))


@pytest.mark.parametrize("command", ["move", "resign", "draw"])
def test_outsiders_cannot_act_on_a_game(db_session: Session, players: Pair, command: str) -> None:
    game_id = make_game(db_session, *players)
    outsider = make_user(db_session, "outsider")
    with pytest.raises(NotAParticipantError):
        if command == "move":
            game_service.submit_move(db_session, game_id, outsider.id, "e2", "e4", None, at(1))
        elif command == "resign":
            game_service.resign(db_session, game_id, outsider.id, at(1))
        else:
            game_service.offer_draw(db_session, game_id, outsider.id, at(1))


def test_checkmate_finishes_the_game_and_updates_statistics(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black)
    play_moves(db_session, game_id, white.id, black.id, FOOLS_MATE)

    game = game_service.load_game(db_session, game_id)
    assert (game.status, game.result, game.result_reason) == (
        GameStatus.FINISHED,
        GameResult.BLACK_WIN,
        ResultReason.CHECKMATE,
    )
    assert game.finished_at is not None and game.turn_started_at is None
    assert all(not p.is_active and p.final_remaining_ms is not None for p in game.participants)
    assert stats(db_session, white) == (1, 0, 1, 0)
    assert stats(db_session, black) == (1, 1, 0, 0)
    with pytest.raises(GameNotActiveError):
        game_service.submit_move(db_session, game_id, white.id, "a2", "a3", None, at(10))


def test_stalemate_is_recorded_as_a_draw_for_both(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black)
    play_moves(db_session, game_id, white.id, black.id, FASTEST_STALEMATE)
    game = game_service.load_game(db_session, game_id)
    assert (game.result, game.result_reason) == (GameResult.DRAW, ResultReason.STALEMATE)
    assert stats(db_session, white) == stats(db_session, black) == (1, 0, 0, 1)


def test_resignation(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black)
    game = game_service.resign(db_session, game_id, white.id, at(3))
    assert (game.result, game.result_reason) == (GameResult.BLACK_WIN, ResultReason.RESIGNATION)
    assert stats(db_session, white) == (1, 0, 1, 0)
    with pytest.raises(GameNotActiveError):
        game_service.resign(db_session, game_id, black.id, at(4))
    assert stats(db_session, black) == (1, 1, 0, 0)


def test_leaving_an_unstarted_game_aborts_without_statistics(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black, started=False)
    game = game_service.resign(db_session, game_id, black.id, at(1))
    assert (game.status, game.result) == (GameStatus.ABORTED, None)
    assert stats(db_session, white) == stats(db_session, black) == (0, 0, 0, 0)
    assert game_queries.find_active_game(db_session, white.id) is None


def test_move_after_flag_fall_is_rejected_and_loses_on_time(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black)
    outcome = game_service.submit_move(db_session, game_id, white.id, "e2", "e4", None, at(180.001))
    assert outcome.timed_out and outcome.move is None
    game = game_service.load_game(db_session, game_id)
    assert (game.result, game.result_reason) == (GameResult.BLACK_WIN, ResultReason.TIMEOUT)
    assert game.white_remaining_ms == 0
    assert move_count(db_session) == 0


def test_claim_timeout_only_after_expiry(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black)
    assert game_service.claim_timeout(db_session, game_id, at(179.9)) is None
    game = game_service.claim_timeout(db_session, game_id, at(180))
    assert game is not None and game.result_reason == ResultReason.TIMEOUT
    assert game_service.claim_timeout(db_session, game_id, at(200)) is None
    assert stats(db_session, black) == (1, 1, 0, 0)


def test_timeout_is_a_draw_when_opponent_cannot_mate(
    db_session: Session, players: Pair, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_id = make_game(db_session, *players)
    monkeypatch.setattr(ChessEngine, "can_possibly_win", lambda self, color: False)
    game = game_service.claim_timeout(db_session, game_id, at(500))
    assert game is not None
    assert (game.result, game.result_reason) == (
        GameResult.DRAW,
        ResultReason.TIMEOUT_VS_INSUFFICIENT_MATERIAL,
    )


def test_draw_offer_and_acceptance(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black)
    game = game_service.offer_draw(db_session, game_id, white.id, at(1))
    assert game.draw_offered_by == PlayerColor.WHITE
    with pytest.raises(DrawOfferError):
        game_service.offer_draw(db_session, game_id, white.id, at(2))
    with pytest.raises(DrawOfferError):
        game_service.respond_to_draw(db_session, game_id, white.id, True, at(2))
    game = game_service.respond_to_draw(db_session, game_id, black.id, True, at(3))
    assert (game.result, game.result_reason) == (GameResult.DRAW, ResultReason.DRAW_AGREEMENT)


def test_draw_offer_can_be_declined(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black)
    game_service.offer_draw(db_session, game_id, white.id, at(1))
    game = game_service.respond_to_draw(db_session, game_id, black.id, False, at(2))
    assert game.status == GameStatus.ACTIVE and game.draw_offered_by is None
    with pytest.raises(DrawOfferError):
        game_service.respond_to_draw(db_session, game_id, black.id, True, at(3))


def test_offer_survives_own_move_but_opponent_move_declines_it(db_session: Session, players: Pair) -> None:
    white, black = players
    game_id = make_game(db_session, white, black)
    game_service.offer_draw(db_session, game_id, white.id, at(1))
    after_own = game_service.submit_move(db_session, game_id, white.id, "e2", "e4", None, at(2)).game
    assert after_own.draw_offered_by == PlayerColor.WHITE
    after_reply = game_service.submit_move(db_session, game_id, black.id, "e7", "e5", None, at(3)).game
    assert after_reply.draw_offered_by is None


def test_unstarted_games_are_aborted_after_the_start_timeout(db_session: Session, players: Pair) -> None:
    game_id = make_game(db_session, *players, started=False)
    created = game_service.load_game(db_session, game_id).created_at
    window = timedelta(seconds=60)
    early = created + timedelta(seconds=59)
    assert game_service.abort_if_never_started(db_session, game_id, early, window) is None
    game = game_service.abort_if_never_started(db_session, game_id, created + window, window)
    assert game is not None and game.status == GameStatus.ABORTED


def test_history_is_reported_from_each_players_point_of_view(db_session: Session, players: Pair) -> None:
    white, black = players
    first = make_game(db_session, white, black)
    play_moves(db_session, first, white.id, black.id, FOOLS_MATE)
    second = make_game(db_session, black, white)
    game_service.resign(db_session, second, black.id, at(30))
    make_game(db_session, white, black)  # still active, so excluded

    page = game_queries.match_history(db_session, white.id, limit=10, offset=0)
    assert page.total == 2
    assert [(g.game_id, g.color, g.outcome) for g in page.items] == [
        (second, PlayerColor.BLACK, "win"),
        (first, PlayerColor.WHITE, "loss"),
    ]
    assert page.items[1].move_count == 4
    assert page.items[0].opponent.username == "black_p"
    theirs = game_queries.match_history(db_session, black.id, limit=1, offset=1)
    assert theirs.total == 2 and [g.outcome for g in theirs.items] == ["win"]


# ----- Concurrency ----------------------------------------------------------------------------


def test_the_same_move_sent_twice_at_once_is_applied_once(db_session: Session, players: Pair) -> None:
    white, black = players
    white_id = white.id
    game_id = make_game(db_session, white, black)

    def move(session: Session) -> object:
        return game_service.submit_move(session, game_id, white_id, "e2", "e4", None, at(1))

    results = run_concurrently([move] * 5)
    accepted = [r for r in results if isinstance(r, game_service.MoveOutcome)]
    rejected = [r for r in results if isinstance(r, NotYourTurnError)]
    assert (len(accepted), len(rejected)) == (1, 4), results
    assert move_count(db_session) == 1


def test_racing_game_endings_count_statistics_once(db_session: Session, players: Pair) -> None:
    white, black = players
    white_id = white.id
    game_id = make_game(db_session, white, black)

    results = run_concurrently(
        [
            lambda s: game_service.resign(s, game_id, white_id, at(181)),
            lambda s: game_service.claim_timeout(s, game_id, at(181)),
            lambda s: game_service.claim_timeout(s, game_id, at(181)),
        ]
    )
    unexpected = [r for r in results if isinstance(r, Exception) and not isinstance(r, GameNotActiveError)]
    assert unexpected == []
    assert stats(db_session, white) == (1, 0, 1, 0)
    assert stats(db_session, black) == (1, 1, 0, 0)

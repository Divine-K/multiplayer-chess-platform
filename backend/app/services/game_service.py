"""Game use cases. Every command is one transaction that holds a row lock on the game.

The lock serialises concurrent commands for the same game (two sockets, a REST call and the
timeout sweeper), so each one sees the latest committed state and the move list, clocks, result
and statistics can never disagree.

`now` is always passed in by the server layer. Nothing here reads a client-supplied time.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.chess_core.clock import ClockState, opposite
from app.chess_core.engine import ChessEngine, win_for
from app.models import (
    Game,
    GameParticipant,
    GameResult,
    GameStatus,
    Move,
    PlayerColor,
    PlayerStatistics,
    ResultReason,
)
from app.services.errors import (
    DrawOfferError,
    GameNotActiveError,
    GameNotFoundError,
    NotAParticipantError,
    NotYourTurnError,
)


@dataclass(frozen=True)
class MoveOutcome:
    game: Game
    move: Move | None  # None when the mover's flag had already fallen
    timed_out: bool


# ----- Loading --------------------------------------------------------------------------------


def load_game(session: Session, game_id: uuid.UUID, *, for_update: bool = False) -> Game:
    statement = (
        select(Game)
        .where(Game.id == game_id)
        .options(selectinload(Game.participants).selectinload(GameParticipant.user), selectinload(Game.moves))
        .execution_options(populate_existing=True)
    )
    if for_update:
        statement = statement.with_for_update()
    game = session.scalar(statement)
    if game is None:
        raise GameNotFoundError("Game not found.")
    return game


def participant_for(game: Game, user_id: int) -> GameParticipant:
    for participant in game.participants:
        if participant.user_id == user_id:
            return participant
    raise NotAParticipantError("You are not a player in this game.")


@contextmanager
def _locked_game(session: Session, game_id: uuid.UUID) -> Iterator[Game]:
    """Lock the game row, then commit on success or roll back (releasing the lock) on any error."""
    try:
        yield load_game(session, game_id, for_update=True)
        session.commit()
    except Exception:
        session.rollback()
        raise


# ----- Clock mapping --------------------------------------------------------------------------


def side_to_move(game: Game) -> PlayerColor:
    # Standard games always start with white, so ply parity is authoritative.
    return PlayerColor.WHITE if len(game.moves) % 2 == 0 else PlayerColor.BLACK


def clock_of(game: Game) -> ClockState:
    running = side_to_move(game) if game.turn_started_at is not None else None
    return ClockState(game.white_remaining_ms, game.black_remaining_ms, running, game.turn_started_at)


def _store_clock(game: Game, clock: ClockState) -> None:
    game.white_remaining_ms = clock.white_ms
    game.black_remaining_ms = clock.black_ms
    game.turn_started_at = clock.turn_started_at


# ----- Creation and start ---------------------------------------------------------------------


def create_game(
    session: Session, *, white_id: int, black_id: int, time_control_seconds: int, increment_seconds: int
) -> Game:
    """Add a new waiting game to the current transaction. The caller commits."""
    initial_ms = time_control_seconds * 1000
    game = Game(
        status=GameStatus.WAITING,
        time_control_seconds=time_control_seconds,
        increment_seconds=increment_seconds,
        white_remaining_ms=initial_ms,
        black_remaining_ms=initial_ms,
        current_fen=ChessEngine().fen,
        participants=[
            GameParticipant(user_id=white_id, color=PlayerColor.WHITE),
            GameParticipant(user_id=black_id, color=PlayerColor.BLACK),
        ],
    )
    session.add(game)
    session.flush()
    return game


def start_game(session: Session, game_id: uuid.UUID, now: datetime) -> bool:
    """Start white's clock once both players are present. Returns False if not waiting."""
    with _locked_game(session, game_id) as game:
        if game.status != GameStatus.WAITING:
            return False
        game.status = GameStatus.ACTIVE
        game.started_at = now
        game.turn_started_at = now
        game.version += 1
    return True


# ----- Gameplay commands ----------------------------------------------------------------------


def submit_move(
    session: Session,
    game_id: uuid.UUID,
    user_id: int,
    from_square: str,
    to_square: str,
    promotion: str | None,
    now: datetime,
) -> MoveOutcome:
    with _locked_game(session, game_id) as game:
        player = participant_for(game, user_id)
        _require_active(game)

        # Time is checked first: a move that arrives after the flag has fallen never counts.
        if clock_of(game).is_flagged(now):
            _finish_on_time(session, game, now)
            return MoveOutcome(game=game, move=None, timed_out=True)

        if player.color != side_to_move(game):
            raise NotYourTurnError("It is not your turn.")

        engine = ChessEngine(move.uci for move in game.moves)
        applied = engine.apply_move(from_square, to_square, promotion)  # raises MoveError
        clock = clock_of(game).press(now, game.increment_seconds * 1000)

        move = Move(
            ply=len(game.moves) + 1,
            uci=applied.uci,
            san=applied.san,
            fen_after=applied.fen_after,
            played_at=now,
        )
        game.moves.append(move)
        game.current_fen = applied.fen_after
        _store_clock(game, clock)
        # Making a move declines an opponent's pending draw offer.
        if game.draw_offered_by is not None and game.draw_offered_by != player.color:
            game.draw_offered_by = None
        game.version += 1

        if applied.end is not None:
            _finish(session, game, applied.end.result, applied.end.reason, now)
    return MoveOutcome(game=game, move=move, timed_out=False)


def resign(session: Session, game_id: uuid.UUID, user_id: int, now: datetime) -> Game:
    """Resign an active game. Leaving a game that never started aborts it without affecting stats."""
    with _locked_game(session, game_id) as game:
        player = participant_for(game, user_id)
        if game.status == GameStatus.WAITING:
            _abort(game)
            return game
        _require_active(game)
        if clock_of(game).is_flagged(now):
            _finish_on_time(session, game, now)
        else:
            _finish(session, game, win_for(opposite(player.color)), ResultReason.RESIGNATION, now)
    return game


def offer_draw(session: Session, game_id: uuid.UUID, user_id: int, now: datetime) -> Game:
    """Offer a draw. Offering while the opponent's offer is pending accepts it."""
    with _locked_game(session, game_id) as game:
        player = participant_for(game, user_id)
        _require_active(game)
        if clock_of(game).is_flagged(now):
            _finish_on_time(session, game, now)
        elif game.draw_offered_by == player.color:
            raise DrawOfferError("You have already offered a draw.")
        elif game.draw_offered_by is not None:
            _finish(session, game, GameResult.DRAW, ResultReason.DRAW_AGREEMENT, now)
        else:
            game.draw_offered_by = player.color
            game.version += 1
    return game


def respond_to_draw(session: Session, game_id: uuid.UUID, user_id: int, accept: bool, now: datetime) -> Game:
    with _locked_game(session, game_id) as game:
        player = participant_for(game, user_id)
        _require_active(game)
        if clock_of(game).is_flagged(now):
            _finish_on_time(session, game, now)
        elif game.draw_offered_by is None or game.draw_offered_by == player.color:
            raise DrawOfferError("There is no draw offer for you to answer.")
        elif accept:
            _finish(session, game, GameResult.DRAW, ResultReason.DRAW_AGREEMENT, now)
        else:
            game.draw_offered_by = None
            game.version += 1
    return game


# ----- Server-initiated transitions -----------------------------------------------------------


def claim_timeout(session: Session, game_id: uuid.UUID, now: datetime) -> Game | None:
    """Finish the game if the running clock has expired. Returns the game only if it changed."""
    with _locked_game(session, game_id) as game:
        if game.status != GameStatus.ACTIVE or not clock_of(game).is_flagged(now):
            return None
        _finish_on_time(session, game, now)
    return game


def abort_if_never_started(
    session: Session, game_id: uuid.UUID, now: datetime, start_timeout: timedelta
) -> Game | None:
    with _locked_game(session, game_id) as game:
        if game.status != GameStatus.WAITING or now - game.created_at < start_timeout:
            return None
        _abort(game)
    return game


# ----- Internals ------------------------------------------------------------------------------


def _require_active(game: Game) -> None:
    if game.status != GameStatus.ACTIVE:
        raise GameNotActiveError(
            "The game has not started yet." if game.status == GameStatus.WAITING else "The game is over."
        )


def _finish_on_time(session: Session, game: Game, now: datetime) -> None:
    flagged = side_to_move(game)
    winner = opposite(flagged)
    engine = ChessEngine(move.uci for move in game.moves)
    if engine.can_possibly_win(winner):
        _finish(session, game, win_for(winner), ResultReason.TIMEOUT, now)
    else:
        _finish(session, game, GameResult.DRAW, ResultReason.TIMEOUT_VS_INSUFFICIENT_MATERIAL, now)


def _finish(session: Session, game: Game, result: GameResult, reason: ResultReason, now: datetime) -> None:
    """Record the result and update both players' statistics within the caller's transaction."""
    clock = clock_of(game).stop(now)
    _store_clock(game, clock)
    game.status = GameStatus.FINISHED
    game.result = result
    game.result_reason = reason
    game.finished_at = now
    game.draw_offered_by = None
    game.version += 1

    # A stable lock order (by user id) rules out deadlocks between statistics updates.
    for participant in sorted(game.participants, key=lambda p: p.user_id):
        participant.is_active = False
        participant.final_remaining_ms = clock.stored_ms(participant.color)
        drew = result == GameResult.DRAW
        won = result == win_for(participant.color)
        # SQL-side increments cannot lose updates.
        session.execute(
            update(PlayerStatistics)
            .where(PlayerStatistics.user_id == participant.user_id)
            .values(
                games_played=PlayerStatistics.games_played + 1,
                wins=PlayerStatistics.wins + int(won),
                losses=PlayerStatistics.losses + int(not won and not drew),
                draws=PlayerStatistics.draws + int(drew),
                updated_at=now,
            )
        )


def _abort(game: Game) -> None:
    game.status = GameStatus.ABORTED
    game.result_reason = ResultReason.NEVER_STARTED
    game.turn_started_at = None
    game.version += 1
    for participant in game.participants:
        participant.is_active = False

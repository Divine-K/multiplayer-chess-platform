"""Read-only game queries: state snapshots, match history, statistics and profiles."""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.chess_core.engine import ChessEngine
from app.models import (
    Game,
    GameParticipant,
    GameResult,
    GameStatus,
    Move,
    PlayerColor,
    PlayerStatistics,
    User,
)
from app.schemas.game import (
    CapturedPieces,
    ClockInfo,
    GameHistoryPage,
    GameState,
    GameSummary,
    MoveInfo,
    Outcome,
    PlayerInfo,
    Players,
    PublicProfile,
    Statistics,
)
from app.services.errors import UserNotFoundError
from app.services.game_service import clock_of


def build_state(game: Game, now: datetime) -> GameState:
    """Create the complete client-facing snapshot of a game loaded with participants and moves."""
    engine = ChessEngine(move.uci for move in game.moves)
    clock = clock_of(game)
    players = {p.color: PlayerInfo(id=p.user_id, username=p.user.username) for p in game.participants}
    return GameState(
        game_id=game.id,
        status=game.status,
        version=game.version,
        time_control_seconds=game.time_control_seconds,
        increment_seconds=game.increment_seconds,
        players=Players(white=players[PlayerColor.WHITE], black=players[PlayerColor.BLACK]),
        fen=engine.fen,
        turn=engine.turn,
        ply=len(game.moves),
        moves=[MoveInfo(ply=m.ply, uci=m.uci, san=m.san) for m in game.moves],
        last_move=engine.last_move_uci,
        is_check=engine.is_check,
        legal_moves=engine.legal_moves() if game.status == GameStatus.ACTIVE else [],
        captured=CapturedPieces(
            white=engine.captured_by(PlayerColor.WHITE), black=engine.captured_by(PlayerColor.BLACK)
        ),
        clocks=ClockInfo(
            white_ms=clock.remaining_ms(PlayerColor.WHITE, now),
            black_ms=clock.remaining_ms(PlayerColor.BLACK, now),
            running=clock.running,
        ),
        draw_offered_by=game.draw_offered_by,
        result=game.result,
        result_reason=game.result_reason,
        created_at=game.created_at,
        started_at=game.started_at,
        finished_at=game.finished_at,
        server_time=now,
    )


def find_active_game(session: Session, user_id: int) -> tuple[uuid.UUID, PlayerColor] | None:
    row = session.execute(
        select(GameParticipant.game_id, GameParticipant.color).where(
            GameParticipant.user_id == user_id, GameParticipant.is_active
        )
    ).first()
    return None if row is None else (row.game_id, row.color)


def outcome_for(result: GameResult, color: PlayerColor) -> Outcome:
    if result == GameResult.DRAW:
        return "draw"
    winner = PlayerColor.WHITE if result == GameResult.WHITE_WIN else PlayerColor.BLACK
    return "win" if winner == color else "loss"


def match_history(session: Session, user_id: int, *, limit: int, offset: int) -> GameHistoryPage:
    """Finished games, newest first, in a fixed number of queries regardless of page size."""
    mine = aliased(GameParticipant)
    theirs = aliased(GameParticipant)
    move_count = select(func.count(Move.id)).where(Move.game_id == Game.id).correlate(Game).scalar_subquery()
    base = (
        select(Game)
        .join(mine, (mine.game_id == Game.id) & (mine.user_id == user_id))
        .where(Game.status == GameStatus.FINISHED)
    )
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.execute(
        base.add_columns(mine.color, User.id, User.username, move_count)
        .join(theirs, (theirs.game_id == Game.id) & (theirs.user_id != user_id))
        .join(User, User.id == theirs.user_id)
        .order_by(Game.finished_at.desc(), Game.id)
        .limit(limit)
        .offset(offset)
    ).all()
    items = [
        GameSummary(
            game_id=game.id,
            color=color,
            opponent=PlayerInfo(id=opponent_id, username=opponent_name),
            outcome=outcome_for(game.result, color),
            result=game.result,
            result_reason=game.result_reason,
            time_control_seconds=game.time_control_seconds,
            increment_seconds=game.increment_seconds,
            move_count=count,
            finished_at=game.finished_at,
        )
        for game, color, opponent_id, opponent_name, count in rows
    ]
    return GameHistoryPage(items=items, total=total, limit=limit, offset=offset)


def statistics_for(session: Session, user_id: int) -> Statistics:
    row = session.get(PlayerStatistics, user_id, populate_existing=True)
    if row is None:
        return Statistics(games_played=0, wins=0, losses=0, draws=0)
    return Statistics(games_played=row.games_played, wins=row.wins, losses=row.losses, draws=row.draws)


def public_profile(session: Session, username: str) -> PublicProfile:
    user = session.scalar(select(User).where(User.username == username, User.is_active))
    if user is None:
        raise UserNotFoundError("Player not found.")
    return PublicProfile(
        id=user.id,
        username=user.username,
        created_at=user.created_at,
        statistics=statistics_for(session, user.id),
    )

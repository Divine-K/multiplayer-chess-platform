"""Database-level guarantees: constraints must hold even if application code is wrong."""

import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import get_engine
from app.models import Game, GameParticipant, Move, PlayerColor, PlayerStatistics, User


def _game(**overrides: object) -> Game:
    values: dict[str, object] = {
        "time_control_seconds": 300,
        "white_remaining_ms": 300_000,
        "black_remaining_ms": 300_000,
    }
    return Game(**(values | overrides))


def _user(session: Session, name: str) -> User:
    user = User(username=name, email=f"{name}@example.com", password_hash="x")
    session.add(user)
    session.commit()
    return user


def test_models_match_migrations() -> None:
    """Fails if a model was changed without a corresponding Alembic migration."""
    with get_engine().connect() as connection:
        diff = compare_metadata(
            MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata
        )
    assert diff == []


def test_player_cannot_hold_both_colors_or_join_twice(db_session: Session) -> None:
    alice, bob = _user(db_session, "alice"), _user(db_session, "bob")
    game = _game()
    game.participants = [
        GameParticipant(user_id=alice.id, color=PlayerColor.WHITE),
        GameParticipant(user_id=bob.id, color=PlayerColor.BLACK),
    ]
    db_session.add(game)
    db_session.commit()

    db_session.add(GameParticipant(game_id=game.id, user_id=alice.id, color=PlayerColor.BLACK))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_duplicate_ply_in_a_game_is_rejected(db_session: Session) -> None:
    game = _game()
    db_session.add(game)
    db_session.commit()
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    db_session.add(Move(game_id=game.id, ply=1, uci="e2e4", san="e4", fen_after=fen))
    db_session.commit()
    db_session.add(Move(game_id=game.id, ply=1, uci="d2d4", san="d4", fen_after=fen))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_finished_status_requires_finished_timestamp(db_session: Session) -> None:
    db_session.add(_game(status="finished"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_invalid_enum_value_is_rejected_by_database() -> None:
    with pytest.raises(IntegrityError), get_engine().begin() as connection:
        connection.execute(
            text(
                "INSERT INTO games "
                "(id, status, time_control_seconds, white_remaining_ms, black_remaining_ms) "
                "VALUES (:id, 'bogus', 300, 1, 1)"
            ),
            {"id": uuid.uuid4()},
        )


def test_statistics_cannot_exceed_games_played(db_session: Session) -> None:
    user = _user(db_session, "carol")
    db_session.add(PlayerStatistics(user_id=user.id, games_played=1, wins=2))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_deleting_user_cascades_to_participation(db_session: Session) -> None:
    user = _user(db_session, "dave")
    game = _game()
    game.participants = [GameParticipant(user_id=user.id, color=PlayerColor.WHITE)]
    db_session.add(game)
    db_session.commit()
    db_session.delete(user)
    db_session.commit()
    count = db_session.execute(text("SELECT count(*) FROM game_participants")).scalar_one()
    assert count == 0


def test_player_cannot_be_active_in_two_games(db_session: Session) -> None:
    erin = _user(db_session, "erin")
    first, second = _game(), _game()
    first.participants = [GameParticipant(user_id=erin.id, color=PlayerColor.WHITE)]
    db_session.add_all([first, second])
    db_session.commit()
    db_session.add(GameParticipant(game_id=second.id, user_id=erin.id, color=PlayerColor.WHITE))
    with pytest.raises(IntegrityError):
        db_session.commit()

"""Test helpers for building players and games quickly."""

import threading
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.models import PlayerStatistics, User
from app.services import game_service

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

# 1.f3 e5 2.g4 Qh4#
FOOLS_MATE = ["f2f3", "e7e5", "g2g4", "d8h4"]
# Sam Loyd's ten-move stalemate, ending with 10.Qe6.
FASTEST_STALEMATE = [
    "e2e3",
    "a7a5",
    "d1h5",
    "a8a6",
    "h5a5",
    "h7h5",
    "a5c7",
    "a6h6",
    "h2h4",
    "f7f6",
    "c7d7",
    "e8f7",
    "d7b7",
    "d8d3",
    "b7b8",
    "d3h7",
    "b8c8",
    "f7g6",
    "c8e6",
]


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def make_user(session: Session, username: str) -> User:
    """Insert a player directly, skipping password hashing."""
    user = User(username=username, email=f"{username}@example.com", password_hash="unused")
    user.statistics = PlayerStatistics()
    session.add(user)
    session.commit()
    return user


def make_game(
    session: Session, white: User, black: User, *, seconds: int = 180, started: bool = True
) -> uuid.UUID:
    game = game_service.create_game(
        session, white_id=white.id, black_id=black.id, time_control_seconds=seconds, increment_seconds=0
    )
    session.commit()
    if started:
        game_service.start_game(session, game.id, T0)
    return game.id


def play_moves(
    session: Session, game_id: uuid.UUID, white_id: int, black_id: int, moves: Sequence[str]
) -> None:
    """Play moves alternately from the start, one simulated second apart."""
    for index, uci in enumerate(moves):
        mover = white_id if index % 2 == 0 else black_id
        outcome = game_service.submit_move(
            session, game_id, mover, uci[:2], uci[2:4], uci[4:] or None, at(index + 1)
        )
        assert outcome.move is not None


def run_concurrently(tasks: Sequence[Callable[[Session], Any]]) -> list[Any]:
    """Run each task in its own thread and session, released at the same instant.

    Returns each task's result, or the exception it raised, in task order.
    """
    barrier = threading.Barrier(len(tasks))
    results: list[Any] = [None] * len(tasks)

    def worker(index: int) -> None:
        with get_session_factory()() as session:
            barrier.wait()
            try:
                results[index] = tasks[index](session)
            except Exception as exc:
                results[index] = exc

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(tasks))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive(), "worker deadlocked"
    return results

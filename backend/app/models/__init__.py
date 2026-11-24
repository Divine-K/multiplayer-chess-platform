"""Importing this package registers every ORM model on Base.metadata (used by Alembic)."""

from app.models.game import Game, GameParticipant, GameResult, GameStatus, Move, PlayerColor
from app.models.statistics import PlayerStatistics
from app.models.user import User

__all__ = [
    "Game",
    "GameParticipant",
    "GameResult",
    "GameStatus",
    "Move",
    "PlayerColor",
    "PlayerStatistics",
    "User",
]

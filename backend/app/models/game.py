"""Game, participant and move persistence models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base_types import string_enum, utc_now_column

if TYPE_CHECKING:
    from app.models.user import User


class GameStatus(enum.StrEnum):
    WAITING = "waiting"
    ACTIVE = "active"
    FINISHED = "finished"
    ABORTED = "aborted"


class GameResult(enum.StrEnum):
    WHITE_WIN = "white_win"
    BLACK_WIN = "black_win"
    DRAW = "draw"


class PlayerColor(enum.StrEnum):
    WHITE = "white"
    BLACK = "black"


class ResultReason(enum.StrEnum):
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    INSUFFICIENT_MATERIAL = "insufficient_material"
    THREEFOLD_REPETITION = "threefold_repetition"
    FIFTY_MOVE_RULE = "fifty_move_rule"
    RESIGNATION = "resignation"
    TIMEOUT = "timeout"
    TIMEOUT_VS_INSUFFICIENT_MATERIAL = "timeout_vs_insufficient_material"
    DRAW_AGREEMENT = "draw_agreement"
    NEVER_STARTED = "never_started"


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint("time_control_seconds > 0", name="time_control_positive"),
        CheckConstraint("increment_seconds >= 0", name="increment_non_negative"),
        CheckConstraint("white_remaining_ms >= 0 AND black_remaining_ms >= 0", name="clocks_non_negative"),
        CheckConstraint(
            "(status = 'finished') = (finished_at IS NOT NULL)", name="finished_at_matches_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[GameStatus] = mapped_column(
        string_enum(GameStatus, 16),
        default=GameStatus.WAITING,
        server_default=GameStatus.WAITING.value,
        index=True,
    )
    time_control_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    increment_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    result: Mapped[GameResult | None] = mapped_column(
        string_enum(GameResult, 16),
        nullable=True,
    )
    result_reason: Mapped[ResultReason | None] = mapped_column(string_enum(ResultReason, 32), nullable=True)
    # Clock values are "as of turn_started_at"; see app/chess_core/clock.py.
    white_remaining_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    black_remaining_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    turn_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Incremented on every state change so clients can discard out-of-order snapshots.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    draw_offered_by: Mapped[PlayerColor | None] = mapped_column(string_enum(PlayerColor, 8), nullable=True)
    current_fen: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = utc_now_column()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    participants: Mapped[list[GameParticipant]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    moves: Mapped[list[Move]] = relationship(
        back_populates="game", cascade="all, delete-orphan", order_by="Move.ply"
    )


class GameParticipant(Base):
    __tablename__ = "game_participants"
    __table_args__ = (
        UniqueConstraint("game_id", "color", name="uq_game_participants_one_player_per_color"),
        UniqueConstraint("game_id", "user_id", name="uq_game_participants_user_at_most_once_per_game"),
        CheckConstraint(
            "final_remaining_ms IS NULL OR final_remaining_ms >= 0", name="remaining_non_negative"
        ),
        # A player can be seated in at most one unfinished game. Enforced by the database, so it
        # holds even under concurrent requests.
        Index(
            "uq_game_participants_one_active_game_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    color: Mapped[PlayerColor] = mapped_column(
        string_enum(PlayerColor, 8),
        nullable=False,
    )
    final_remaining_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    joined_at: Mapped[datetime] = utc_now_column()

    game: Mapped[Game] = relationship(back_populates="participants")
    user: Mapped[User] = relationship(back_populates="participations")


class Move(Base):
    __tablename__ = "moves"
    __table_args__ = (
        UniqueConstraint("game_id", "ply", name="uq_moves_ply_unique_per_game"),
        CheckConstraint("ply > 0", name="ply_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ply: Mapped[int] = mapped_column(Integer, nullable=False)
    uci: Mapped[str] = mapped_column(String(5), nullable=False)
    san: Mapped[str] = mapped_column(String(16), nullable=False)
    fen_after: Mapped[str] = mapped_column(String(100), nullable=False)
    played_at: Mapped[datetime] = utc_now_column()

    game: Mapped[Game] = relationship(back_populates="moves")

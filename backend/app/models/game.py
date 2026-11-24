"""Game, participant and move persistence models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base_types import utc_now_column

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


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        CheckConstraint("time_control_seconds > 0", name="time_control_positive"),
        CheckConstraint("increment_seconds >= 0", name="increment_non_negative"),
        CheckConstraint(
            "(status = 'finished') = (finished_at IS NOT NULL)", name="finished_at_matches_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[GameStatus] = mapped_column(
        Enum(
            GameStatus,
            native_enum=False,
            create_constraint=True,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=GameStatus.WAITING,
        server_default=GameStatus.WAITING.value,
        index=True,
    )
    time_control_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    increment_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    result: Mapped[GameResult | None] = mapped_column(
        Enum(
            GameResult,
            native_enum=False,
            create_constraint=True,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=True,
    )
    result_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
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
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    color: Mapped[PlayerColor] = mapped_column(
        Enum(
            PlayerColor,
            native_enum=False,
            create_constraint=True,
            length=8,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    final_remaining_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
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

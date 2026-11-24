from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base_types import utc_now_column

if TYPE_CHECKING:
    from app.models.user import User


class PlayerStatistics(Base):
    """Denormalised per-player counters, updated transactionally when a game finishes."""

    __tablename__ = "player_statistics"
    __table_args__ = (
        CheckConstraint("games_played >= 0", name="games_played_non_negative"),
        CheckConstraint("wins >= 0 AND losses >= 0 AND draws >= 0", name="outcomes_non_negative"),
        CheckConstraint("wins + losses + draws <= games_played", name="outcomes_within_games_played"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    games_played: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    draws: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = utc_now_column()

    user: Mapped[User] = relationship(back_populates="statistics")

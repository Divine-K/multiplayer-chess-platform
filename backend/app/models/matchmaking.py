from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base_types import utc_now_column


class MatchmakingEntry(Base):
    """A player waiting for an opponent. The primary key allows one queue entry per user."""

    __tablename__ = "matchmaking_queue"
    __table_args__ = (
        CheckConstraint("time_control_seconds > 0", name="time_control_positive"),
        CheckConstraint("increment_seconds >= 0", name="increment_non_negative"),
        Index("ix_matchmaking_queue_pairing", "time_control_seconds", "increment_seconds", "joined_at"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    time_control_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    increment_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    joined_at: Mapped[datetime] = utc_now_column()
    # Refreshed by status polling; entries that stop being refreshed are treated as abandoned.
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

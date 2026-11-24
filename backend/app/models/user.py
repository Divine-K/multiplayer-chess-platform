from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base_types import utc_now_column


class User(Base):
    """A registered player account. Passwords are stored only as Argon2 hashes."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique=True creates a unique constraint, which Postgres backs with its own index.
    username: Mapped[str] = mapped_column(String(32), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = utc_now_column()
    updated_at: Mapped[datetime] = utc_now_column()

    statistics: Mapped["PlayerStatistics | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    # passive_deletes lets the database's ON DELETE CASCADE remove participations.
    participations: Mapped[list["GameParticipant"]] = relationship(
        back_populates="user", passive_deletes=True
    )


# Imported at the bottom to avoid a circular import while keeping every model registered
# on Base.metadata for Alembic autogenerate.
from app.models.game import GameParticipant  # noqa: E402
from app.models.statistics import PlayerStatistics  # noqa: E402

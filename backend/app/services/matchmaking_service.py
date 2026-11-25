"""Database-backed matchmaking queue.

Concurrency: joining and cancelling take a PostgreSQL transaction-scoped advisory lock, so pairing
decisions happen one at a time. Without it, two players joining simultaneously could each see an
empty queue and both wait forever, or two joiners could claim the same opponent. As a backstop, the
database also forbids a player from being in two unfinished games.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from app.models import MatchmakingEntry, PlayerColor
from app.services.errors import AlreadyInGameError, AlreadyQueuedError, UnsupportedTimeControlError
from app.services.game_queries import find_active_game
from app.services.game_service import create_game
from app.services.time_controls import is_supported

MATCHMAKING_LOCK_KEY = 0x43484553  # arbitrary, application-wide advisory lock id ("CHES")


@dataclass(frozen=True)
class MatchmakingState:
    status: Literal["idle", "queued", "matched"]
    game_id: uuid.UUID | None = None
    color: PlayerColor | None = None
    time_control_seconds: int | None = None
    increment_seconds: int | None = None
    queued_since: datetime | None = None


def _lock_queue(session: Session) -> None:
    """Held until the surrounding transaction commits or rolls back."""
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MATCHMAKING_LOCK_KEY})


def join_queue(
    session: Session,
    user_id: int,
    *,
    time_control_seconds: int,
    increment_seconds: int,
    now: datetime,
    stale_after: timedelta,
) -> MatchmakingState:
    """Pair with the longest-waiting compatible player, or start waiting."""
    if not is_supported(time_control_seconds, increment_seconds):
        raise UnsupportedTimeControlError("That time control is not offered.")
    try:
        _lock_queue(session)
        session.execute(delete(MatchmakingEntry).where(MatchmakingEntry.last_seen_at < now - stale_after))

        if find_active_game(session, user_id) is not None:
            raise AlreadyInGameError("Finish your current game before finding a new one.")
        if session.get(MatchmakingEntry, user_id, populate_existing=True) is not None:
            raise AlreadyQueuedError("You are already searching for a game.")

        opponent_id = session.scalar(
            select(MatchmakingEntry.user_id)
            .where(
                MatchmakingEntry.time_control_seconds == time_control_seconds,
                MatchmakingEntry.increment_seconds == increment_seconds,
                MatchmakingEntry.user_id != user_id,
            )
            .order_by(MatchmakingEntry.joined_at, MatchmakingEntry.user_id)
            .limit(1)
        )

        if opponent_id is None:
            session.add(
                MatchmakingEntry(
                    user_id=user_id,
                    time_control_seconds=time_control_seconds,
                    increment_seconds=increment_seconds,
                    joined_at=now,
                    last_seen_at=now,
                )
            )
            session.commit()
            return MatchmakingState(
                status="queued",
                time_control_seconds=time_control_seconds,
                increment_seconds=increment_seconds,
                queued_since=now,
            )

        session.execute(delete(MatchmakingEntry).where(MatchmakingEntry.user_id == opponent_id))
        i_am_white = secrets.randbelow(2) == 0
        white_id, black_id = (user_id, opponent_id) if i_am_white else (opponent_id, user_id)
        game = create_game(
            session,
            white_id=white_id,
            black_id=black_id,
            time_control_seconds=time_control_seconds,
            increment_seconds=increment_seconds,
        )
        session.commit()
        return MatchmakingState(
            status="matched",
            game_id=game.id,
            color=PlayerColor.WHITE if i_am_white else PlayerColor.BLACK,
            time_control_seconds=time_control_seconds,
            increment_seconds=increment_seconds,
        )
    except Exception:
        session.rollback()
        raise


def poll_status(session: Session, user_id: int, now: datetime) -> MatchmakingState:
    """Report where the player stands. Polling doubles as the queue heartbeat.

    The queue entry is checked before the active game: pairing removes the entry and creates the
    game in one transaction, so a player is never reported as idle in between.
    """
    entry = session.execute(
        update(MatchmakingEntry)
        .where(MatchmakingEntry.user_id == user_id)
        .values(last_seen_at=now)
        .returning(
            MatchmakingEntry.time_control_seconds,
            MatchmakingEntry.increment_seconds,
            MatchmakingEntry.joined_at,
        )
    ).first()
    session.commit()
    if entry is not None:
        return MatchmakingState(
            status="queued",
            time_control_seconds=entry.time_control_seconds,
            increment_seconds=entry.increment_seconds,
            queued_since=entry.joined_at,
        )
    active = find_active_game(session, user_id)
    if active is not None:
        return MatchmakingState(status="matched", game_id=active[0], color=active[1])
    return MatchmakingState(status="idle")


def cancel(session: Session, user_id: int) -> MatchmakingState:
    """Leave the queue. If a match was made first, report it instead of pretending to cancel."""
    try:
        _lock_queue(session)
        session.execute(delete(MatchmakingEntry).where(MatchmakingEntry.user_id == user_id))
        active = find_active_game(session, user_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    if active is not None:
        return MatchmakingState(status="matched", game_id=active[0], color=active[1])
    return MatchmakingState(status="idle")

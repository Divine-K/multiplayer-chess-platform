"""Server-authoritative chess clock as an immutable value object.

The clock never ticks. It stores each side's remaining time as of `turn_started_at`, and derives the
live value from a server-supplied `now`. That makes it trivially persistable, immune to client
clock manipulation, and deterministic to test.
"""

from dataclasses import dataclass, replace
from datetime import datetime

from app.models import PlayerColor


class FlagFallenError(Exception):
    """The side to move has no time left, so it cannot complete a move."""


def opposite(color: PlayerColor) -> PlayerColor:
    return PlayerColor.BLACK if color == PlayerColor.WHITE else PlayerColor.WHITE


@dataclass(frozen=True)
class ClockState:
    white_ms: int
    black_ms: int
    running: PlayerColor | None  # whose clock is counting down; None when stopped
    turn_started_at: datetime | None

    def __post_init__(self) -> None:
        if (self.running is None) != (self.turn_started_at is None):
            raise ValueError("A running clock needs a start time, and a stopped clock must not have one.")

    def stored_ms(self, color: PlayerColor) -> int:
        return self.white_ms if color == PlayerColor.WHITE else self.black_ms

    def remaining_ms(self, color: PlayerColor, now: datetime) -> int:
        stored = self.stored_ms(color)
        if self.running != color or self.turn_started_at is None:
            return stored
        elapsed = int((now - self.turn_started_at).total_seconds() * 1000)
        return max(0, stored - max(0, elapsed))

    def is_flagged(self, now: datetime) -> bool:
        return self.running is not None and self.remaining_ms(self.running, now) <= 0

    def press(self, now: datetime, increment_ms: int = 0) -> "ClockState":
        """Complete the running side's turn: charge elapsed time, add increment, start the opponent."""
        mover = self.running
        if mover is None:
            raise ValueError("Cannot press a stopped clock.")
        left = self.remaining_ms(mover, now)
        if left <= 0:
            raise FlagFallenError
        updated = self._with_side(mover, left + increment_ms)
        return replace(updated, running=opposite(mover), turn_started_at=now)

    def stop(self, now: datetime) -> "ClockState":
        """Freeze both clocks, charging the running side for the time it used."""
        if self.running is None:
            return self
        updated = self._with_side(self.running, self.remaining_ms(self.running, now))
        return replace(updated, running=None, turn_started_at=None)

    def _with_side(self, color: PlayerColor, value: int) -> "ClockState":
        if color == PlayerColor.WHITE:
            return replace(self, white_ms=value)
        return replace(self, black_ms=value)

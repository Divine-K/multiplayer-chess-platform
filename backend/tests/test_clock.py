from datetime import UTC, datetime, timedelta

import pytest

from app.chess_core.clock import ClockState, FlagFallenError
from app.models import PlayerColor

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def running_clock(ms: int = 180_000) -> ClockState:
    return ClockState(white_ms=ms, black_ms=ms, running=PlayerColor.WHITE, turn_started_at=T0)


def test_only_the_running_side_loses_time() -> None:
    clock = running_clock()
    assert clock.remaining_ms(PlayerColor.WHITE, at(10)) == 170_000
    assert clock.remaining_ms(PlayerColor.BLACK, at(10)) == 180_000


def test_press_charges_the_mover_and_starts_the_opponent() -> None:
    pressed = running_clock().press(at(12.5))
    assert pressed.white_ms == 167_500
    assert pressed.running == PlayerColor.BLACK
    assert pressed.remaining_ms(PlayerColor.BLACK, at(20)) == 172_500
    assert pressed.remaining_ms(PlayerColor.WHITE, at(20)) == 167_500


def test_increment_is_added_after_the_move() -> None:
    assert running_clock().press(at(10), increment_ms=2_000).white_ms == 172_000


def test_flag_falls_exactly_at_zero() -> None:
    clock = running_clock(ms=1_000)
    assert not clock.is_flagged(at(0.999))
    assert clock.is_flagged(at(1.0))
    assert clock.remaining_ms(PlayerColor.WHITE, at(99)) == 0


def test_cannot_complete_a_move_after_the_flag_falls_even_with_increment() -> None:
    with pytest.raises(FlagFallenError):
        running_clock(ms=1_000).press(at(2), increment_ms=5_000)


def test_stop_freezes_both_sides() -> None:
    stopped = running_clock().stop(at(30))
    assert stopped.running is None
    assert stopped.remaining_ms(PlayerColor.WHITE, at(500)) == 150_000


def test_a_clock_moving_backwards_never_adds_time() -> None:
    assert running_clock().remaining_ms(PlayerColor.WHITE, at(-5)) == 180_000


def test_inconsistent_state_is_rejected() -> None:
    with pytest.raises(ValueError):
        ClockState(white_ms=1, black_ms=1, running=PlayerColor.WHITE, turn_started_at=None)

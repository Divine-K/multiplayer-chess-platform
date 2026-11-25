"""The time controls players may choose. Add an entry here to offer another one."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeControl:
    time_control_seconds: int
    increment_seconds: int
    label: str


TIME_CONTROLS: tuple[TimeControl, ...] = (
    TimeControl(180, 0, "3 min"),
    TimeControl(300, 0, "5 min"),
    TimeControl(600, 0, "10 min"),
)


def is_supported(time_control_seconds: int, increment_seconds: int) -> bool:
    return any(
        option.time_control_seconds == time_control_seconds and option.increment_seconds == increment_seconds
        for option in TIME_CONTROLS
    )

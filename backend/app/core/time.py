"""The server's clock: the only time source gameplay decisions are allowed to use."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)

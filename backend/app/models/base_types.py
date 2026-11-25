"""Reusable column types and helpers shared by the ORM models."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column


def utc_now_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def string_enum(enum_class: type[enum.StrEnum], length: int) -> Enum:
    """A VARCHAR column restricted to the enum's values by a CHECK constraint."""
    return Enum(
        enum_class,
        native_enum=False,
        create_constraint=True,
        length=length,
        values_callable=lambda members: [member.value for member in members],
    )

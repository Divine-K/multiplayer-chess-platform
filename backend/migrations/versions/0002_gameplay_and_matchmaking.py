"""Gameplay state: persisted clocks, versioning, draw offers, one-active-game rule, matchmaking queue.

Revision ID: 0002_gameplay_and_matchmaking
Revises: 0001_initial_schema
Create Date: 2026-11-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_gameplay_and_matchmaking"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESULT_REASONS = (
    "checkmate",
    "stalemate",
    "insufficient_material",
    "threefold_repetition",
    "fifty_move_rule",
    "resignation",
    "timeout",
    "timeout_vs_insufficient_material",
    "draw_agreement",
    "never_started",
)


def _in_list(column: str, values: Sequence[str]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


def upgrade() -> None:
    # Clock columns get a temporary default so existing rows (if any) can be backfilled.
    op.add_column("games", sa.Column("white_remaining_ms", sa.Integer(), nullable=True))
    op.add_column("games", sa.Column("black_remaining_ms", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE games SET white_remaining_ms = time_control_seconds * 1000, "
        "black_remaining_ms = time_control_seconds * 1000"
    )
    op.alter_column("games", "white_remaining_ms", nullable=False)
    op.alter_column("games", "black_remaining_ms", nullable=False)
    op.add_column("games", sa.Column("turn_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("games", sa.Column("version", sa.Integer(), server_default="0", nullable=False))
    op.add_column("games", sa.Column("draw_offered_by", sa.String(length=8), nullable=True))
    op.create_check_constraint(
        "ck_games_clocks_non_negative", "games", "white_remaining_ms >= 0 AND black_remaining_ms >= 0"
    )
    op.create_check_constraint(
        "ck_games_draw_offered_by_valid", "games", _in_list("draw_offered_by", ("white", "black"))
    )
    op.create_check_constraint(
        "ck_games_result_reason_valid", "games", _in_list("result_reason", RESULT_REASONS)
    )

    op.add_column(
        "game_participants",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.execute(
        "UPDATE game_participants SET is_active = false WHERE game_id IN "
        "(SELECT id FROM games WHERE status IN ('finished', 'aborted'))"
    )
    op.create_index(
        "uq_game_participants_one_active_game_per_user",
        "game_participants",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "matchmaking_queue",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("time_control_seconds", sa.Integer(), nullable=False),
        sa.Column("increment_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_matchmaking_queue"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_matchmaking_queue_user_id_users", ondelete="CASCADE"
        ),
        sa.CheckConstraint("time_control_seconds > 0", name="ck_matchmaking_queue_time_control_positive"),
        sa.CheckConstraint("increment_seconds >= 0", name="ck_matchmaking_queue_increment_non_negative"),
    )
    op.create_index(
        "ix_matchmaking_queue_pairing",
        "matchmaking_queue",
        ["time_control_seconds", "increment_seconds", "joined_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_matchmaking_queue_pairing", table_name="matchmaking_queue")
    op.drop_table("matchmaking_queue")
    op.drop_index("uq_game_participants_one_active_game_per_user", table_name="game_participants")
    op.drop_column("game_participants", "is_active")
    op.drop_constraint("ck_games_result_reason_valid", "games", type_="check")
    op.drop_constraint("ck_games_draw_offered_by_valid", "games", type_="check")
    op.drop_constraint("ck_games_clocks_non_negative", "games", type_="check")
    op.drop_column("games", "draw_offered_by")
    op.drop_column("games", "version")
    op.drop_column("games", "turn_started_at")
    op.drop_column("games", "black_remaining_ms")
    op.drop_column("games", "white_remaining_ms")

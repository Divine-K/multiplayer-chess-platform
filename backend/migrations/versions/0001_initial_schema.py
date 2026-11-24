"""Initial schema: users, games, game_participants, moves, player_statistics.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GAME_STATUS_VALUES = ("waiting", "active", "finished", "aborted")
GAME_RESULT_VALUES = ("white_win", "black_win", "draw")
PLAYER_COLOR_VALUES = ("white", "black")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "games",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*GAME_STATUS_VALUES, name="gamestatus", native_enum=False, length=16, create_constraint=True),
            server_default="waiting",
            nullable=False,
        ),
        sa.Column("time_control_seconds", sa.Integer(), nullable=False),
        sa.Column("increment_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "result",
            sa.Enum(*GAME_RESULT_VALUES, name="gameresult", native_enum=False, length=16, create_constraint=True),
            nullable=True,
        ),
        sa.Column("result_reason", sa.String(length=32), nullable=True),
        sa.Column("current_fen", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_games"),
        sa.CheckConstraint("time_control_seconds > 0", name="ck_games_time_control_positive"),
        sa.CheckConstraint("increment_seconds >= 0", name="ck_games_increment_non_negative"),
        sa.CheckConstraint(
            "(status = 'finished') = (finished_at IS NOT NULL)", name="ck_games_finished_at_matches_status"
        ),
    )
    op.create_index("ix_games_status", "games", ["status"], unique=False)
    op.create_index("ix_games_finished_at", "games", ["finished_at"], unique=False)

    op.create_table(
        "game_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "color",
            sa.Enum(*PLAYER_COLOR_VALUES, name="playercolor", native_enum=False, length=8, create_constraint=True),
            nullable=False,
        ),
        sa.Column("final_remaining_ms", sa.Integer(), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_game_participants"),
        sa.ForeignKeyConstraint(
            ["game_id"], ["games.id"], name="fk_game_participants_game_id_games", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_game_participants_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("game_id", "color", name="uq_game_participants_one_player_per_color"),
        sa.UniqueConstraint("game_id", "user_id", name="uq_game_participants_user_at_most_once_per_game"),
        sa.CheckConstraint(
            "final_remaining_ms IS NULL OR final_remaining_ms >= 0",
            name="ck_game_participants_remaining_non_negative",
        ),
    )
    op.create_index("ix_game_participants_user_id", "game_participants", ["user_id"], unique=False)

    op.create_table(
        "moves",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("ply", sa.Integer(), nullable=False),
        sa.Column("uci", sa.String(length=5), nullable=False),
        sa.Column("san", sa.String(length=16), nullable=False),
        sa.Column("fen_after", sa.String(length=100), nullable=False),
        sa.Column("played_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_moves"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], name="fk_moves_game_id_games", ondelete="CASCADE"),
        sa.UniqueConstraint("game_id", "ply", name="uq_moves_ply_unique_per_game"),
        sa.CheckConstraint("ply > 0", name="ck_moves_ply_positive"),
    )
    op.create_index("ix_moves_game_id", "moves", ["game_id"], unique=False)

    op.create_table(
        "player_statistics",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("games_played", sa.Integer(), server_default="0", nullable=False),
        sa.Column("wins", sa.Integer(), server_default="0", nullable=False),
        sa.Column("losses", sa.Integer(), server_default="0", nullable=False),
        sa.Column("draws", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_player_statistics"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_player_statistics_user_id_users", ondelete="CASCADE"
        ),
        sa.CheckConstraint("games_played >= 0", name="ck_player_statistics_games_played_non_negative"),
        sa.CheckConstraint("wins >= 0 AND losses >= 0 AND draws >= 0", name="ck_player_statistics_outcomes_non_negative"),
        sa.CheckConstraint(
            "wins + losses + draws <= games_played", name="ck_player_statistics_outcomes_within_games_played"
        ),
    )


def downgrade() -> None:
    op.drop_table("player_statistics")
    op.drop_index("ix_moves_game_id", table_name="moves")
    op.drop_table("moves")
    op.drop_index("ix_game_participants_user_id", table_name="game_participants")
    op.drop_table("game_participants")
    op.drop_index("ix_games_finished_at", table_name="games")
    op.drop_index("ix_games_status", table_name="games")
    op.drop_table("games")
    op.drop_table("users")

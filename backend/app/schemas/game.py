"""Response shapes for game data, shared by the REST API and the WebSocket protocol."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models import GameResult, GameStatus, PlayerColor, ResultReason

Outcome = Literal["win", "loss", "draw"]


class PlayerInfo(BaseModel):
    id: int
    username: str


class Players(BaseModel):
    white: PlayerInfo
    black: PlayerInfo


class MoveInfo(BaseModel):
    ply: int
    uci: str
    san: str


class ClockInfo(BaseModel):
    """Remaining time at `GameState.server_time`. `running` is the side currently counting down."""

    white_ms: int
    black_ms: int
    running: PlayerColor | None


class CapturedPieces(BaseModel):
    """Pieces each side has captured, as lowercase letters (p, n, b, r, q)."""

    white: list[str]
    black: list[str]


class GameState(BaseModel):
    game_id: uuid.UUID
    status: GameStatus
    version: int
    time_control_seconds: int
    increment_seconds: int
    players: Players
    fen: str
    turn: PlayerColor
    ply: int
    moves: list[MoveInfo]
    last_move: str | None
    is_check: bool
    legal_moves: list[str]
    captured: CapturedPieces
    clocks: ClockInfo
    draw_offered_by: PlayerColor | None
    result: GameResult | None
    result_reason: ResultReason | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    server_time: datetime


class GameResultInfo(BaseModel):
    game_id: uuid.UUID
    status: GameStatus
    result: GameResult | None
    result_reason: ResultReason | None
    finished_at: datetime | None


class GameSummary(BaseModel):
    """One row of a player's match history, from that player's point of view."""

    game_id: uuid.UUID
    color: PlayerColor
    opponent: PlayerInfo
    outcome: Outcome
    result: GameResult
    result_reason: ResultReason
    time_control_seconds: int
    increment_seconds: int
    move_count: int
    finished_at: datetime


class GameHistoryPage(BaseModel):
    items: list[GameSummary]
    total: int
    limit: int
    offset: int


class Statistics(BaseModel):
    games_played: int
    wins: int
    losses: int
    draws: int


class PublicProfile(BaseModel):
    """What any signed-in player may see about another. Deliberately excludes email."""

    id: int
    username: str
    created_at: datetime
    statistics: Statistics

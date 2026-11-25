"""Authoritative chess rules, built on python-chess. Pure domain code: no database, no HTTP.

A game is always rebuilt from its full move list (not just the latest FEN) because repetition
detection needs the position history, which a FEN does not contain.
"""

from collections.abc import Iterable
from dataclasses import dataclass

import chess

from app.models import GameResult, PlayerColor, ResultReason

PROMOTION_PIECES = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}


class MoveError(Exception):
    """A requested move cannot be applied. `code` is a stable machine-readable identifier."""

    code = "illegal_move"


class IllegalMoveError(MoveError):
    code = "illegal_move"


class InvalidMoveFormatError(MoveError):
    code = "invalid_move_format"


class PromotionRequiredError(MoveError):
    code = "promotion_required"


@dataclass(frozen=True)
class GameEnd:
    result: GameResult
    reason: ResultReason


@dataclass(frozen=True)
class AppliedMove:
    uci: str
    san: str
    fen_after: str
    is_capture: bool
    is_check: bool
    end: GameEnd | None


def to_color(chess_color: chess.Color) -> PlayerColor:
    return PlayerColor.WHITE if chess_color == chess.WHITE else PlayerColor.BLACK


def win_for(color: PlayerColor) -> GameResult:
    return GameResult.WHITE_WIN if color == PlayerColor.WHITE else GameResult.BLACK_WIN


class ChessEngine:
    def __init__(self, moves: Iterable[str] = (), *, starting_fen: str = chess.STARTING_FEN) -> None:
        self._board = chess.Board(starting_fen)
        self._san_history: list[str] = []
        # Pieces captured *by* each color, in order, as lowercase symbols (p, n, b, r, q).
        self._captured: dict[PlayerColor, list[str]] = {PlayerColor.WHITE: [], PlayerColor.BLACK: []}
        for uci in moves:
            try:
                move = self._board.parse_uci(uci)
            except ValueError as exc:
                raise ValueError(f"Stored move history is corrupt at move '{uci}'.") from exc
            self._push(move)

    # ----- Queries ---------------------------------------------------------------------------

    @property
    def fen(self) -> str:
        return self._board.fen()

    @property
    def turn(self) -> PlayerColor:
        return to_color(self._board.turn)

    @property
    def is_check(self) -> bool:
        return self._board.is_check()

    @property
    def san_history(self) -> list[str]:
        return list(self._san_history)

    @property
    def last_move_uci(self) -> str | None:
        return self._board.peek().uci() if self._board.move_stack else None

    def captured_by(self, color: PlayerColor) -> list[str]:
        return list(self._captured[color])

    def legal_moves(self) -> list[str]:
        return [move.uci() for move in self._board.legal_moves]

    def can_possibly_win(self, color: PlayerColor) -> bool:
        """False when `color` has too little material to ever deliver mate."""
        chess_color = chess.WHITE if color == PlayerColor.WHITE else chess.BLACK
        return not self._board.has_insufficient_material(chess_color)

    def detect_end(self) -> GameEnd | None:
        """Report whether the current position ends the game.

        Threefold repetition and the fifty-move rule are applied automatically (as most online
        platforms do), so no separate "claim draw" action is needed.
        """
        board = self._board
        if board.is_checkmate():
            return GameEnd(win_for(to_color(not board.turn)), ResultReason.CHECKMATE)
        if board.is_stalemate():
            return GameEnd(GameResult.DRAW, ResultReason.STALEMATE)
        if board.is_insufficient_material():
            return GameEnd(GameResult.DRAW, ResultReason.INSUFFICIENT_MATERIAL)
        if board.is_repetition(3):
            return GameEnd(GameResult.DRAW, ResultReason.THREEFOLD_REPETITION)
        if board.is_fifty_moves():
            return GameEnd(GameResult.DRAW, ResultReason.FIFTY_MOVE_RULE)
        return None

    # ----- Commands --------------------------------------------------------------------------

    def apply_move(self, from_square: str, to_square: str, promotion: str | None = None) -> AppliedMove:
        if self.detect_end() is not None:
            raise IllegalMoveError("The game is already over.")
        move = self._parse(from_square, to_square, promotion)
        is_capture = self._board.is_capture(move)
        san = self._push(move)
        return AppliedMove(
            uci=move.uci(),
            san=san,
            fen_after=self._board.fen(),
            is_capture=is_capture,
            is_check=self._board.is_check(),
            end=self.detect_end(),
        )

    # ----- Internals -------------------------------------------------------------------------

    def _parse(self, from_square: str, to_square: str, promotion: str | None) -> chess.Move:
        try:
            source = chess.parse_square(from_square)
            target = chess.parse_square(to_square)
        except ValueError as exc:
            raise InvalidMoveFormatError("Squares must be written like 'e2' or 'h8'.") from exc

        piece_type: chess.PieceType | None = None
        if promotion is not None:
            piece_type = PROMOTION_PIECES.get(promotion)
            if piece_type is None:
                raise InvalidMoveFormatError("Promotion piece must be one of q, r, b or n.")

        move = chess.Move(source, target, promotion=piece_type)
        if move in self._board.legal_moves:
            return move
        if piece_type is None and chess.Move(source, target, chess.QUEEN) in self._board.legal_moves:
            raise PromotionRequiredError("Choose a piece to promote to.")
        raise IllegalMoveError(f"{from_square}{to_square} is not a legal move.")

    def _push(self, move: chess.Move) -> str:
        board = self._board
        mover = to_color(board.turn)
        if board.is_en_passant(move):
            self._captured[mover].append("p")
        elif board.is_capture(move):
            captured = board.piece_at(move.to_square)
            if captured is not None:
                self._captured[mover].append(captured.symbol().lower())
        san = board.san_and_push(move)
        self._san_history.append(san)
        return san

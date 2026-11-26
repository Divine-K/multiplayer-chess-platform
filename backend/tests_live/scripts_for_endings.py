"""Move sequences that reach specific endings, written out or generated deterministically."""

import random
from functools import lru_cache

import chess

FOOLS_MATE = "f2f3 e7e5 g2g4 d8h4"
SCHOLARS_MATE = "e2e4 e7e5 f1c4 b8c6 d1h5 g8f6 h5f7"
# Sam Loyd's shortest known stalemate.
STALEMATE = "e2e3 a7a5 d1h5 a8a6 h5a5 h7h5 h2h4 a6h6 a5c7 f7f6 c7d7 e8f7 d7b7 d8d3 b7b8 d3h7 b8c8 f7g6 c8e6"
THREEFOLD = "g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1 f6g8"


def _natural_end(board: chess.Board) -> str | None:
    """The server's ending rules, in its order of precedence."""
    if board.is_checkmate():
        return "checkmate"
    if board.is_stalemate():
        return "stalemate"
    if board.is_insufficient_material():
        return "insufficient_material"
    if board.is_repetition(3):
        return "threefold_repetition"
    if board.is_fifty_moves():
        return "fifty_move_rule"
    return None


def random_game(seed: int) -> tuple[list[str], str, str]:
    """A complete legal game of random moves: (moves, result, reason)."""
    rng = random.Random(seed)
    board = chess.Board()
    while (reason := _natural_end(board)) is None:
        board.push(rng.choice(sorted(board.legal_moves, key=chess.Move.uci)))
    winner = "black_win" if board.turn == chess.WHITE else "white_win"
    result = winner if reason == "checkmate" else "draw"
    return [m.uci() for m in board.move_stack], result, reason


@lru_cache
def insufficient_material_game() -> tuple[str, ...]:
    """Prefer captures until too little material is left to mate."""
    for seed in range(2000):
        rng = random.Random(seed)
        board = chess.Board()
        while (reason := _natural_end(board)) is None:
            moves = sorted(board.legal_moves, key=chess.Move.uci)
            captures = [m for m in moves if board.is_capture(m)]
            board.push(rng.choice(captures or moves))
        if reason == "insufficient_material":
            return tuple(m.uci() for m in board.move_stack)
    raise RuntimeError("No insufficient-material game found")


@lru_cache
def fifty_move_game() -> tuple[str, ...]:
    """Quiet piece moves that never repeat a position three times, until the fifty-move rule."""
    for seed in range(200):
        rng = random.Random(seed)
        board = chess.Board()
        for uci in ("e2e4", "e7e5", "d2d3", "d7d6"):  # open lines so pieces have room
            board.push_uci(uci)
        while _natural_end(board) is None:
            quiet = []
            for move in sorted(board.legal_moves, key=chess.Move.uci):
                if board.is_zeroing(move):
                    continue
                board.push(move)
                if not board.is_checkmate() and not board.is_stalemate() and not board.is_repetition(2):
                    quiet.append(move)
                board.pop()
            if not quiet:
                break
            board.push(rng.choice(quiet))
        if _natural_end(board) == "fifty_move_rule":
            return tuple(m.uci() for m in board.move_stack)
    raise RuntimeError("No fifty-move game found")


@lru_cache
def bare_opponent_position() -> tuple[str, ...]:
    """A game in progress where the side *not* to move can no longer deliver mate.

    If the side to move then runs out of time, the result must be a draw.
    """
    for seed in range(2000):
        rng = random.Random(seed)
        board = chess.Board()
        while _natural_end(board) is None:
            if board.has_insufficient_material(not board.turn):
                return tuple(m.uci() for m in board.move_stack)
            moves = sorted(board.legal_moves, key=chess.Move.uci)
            captures = [m for m in moves if board.is_capture(m)]
            board.push(rng.choice(captures or moves))
    raise RuntimeError("No suitable position found")
